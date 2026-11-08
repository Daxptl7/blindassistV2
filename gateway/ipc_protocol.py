"""Bounded versioned JSON frames. One request per connection, terminated by EOF."""
from dataclasses import dataclass
import json
import re
import socket
import struct
import time

from .command_models import CommandRequest, CommandSource, CommandType, CommandValidationError
from .errors import GatewayError

VERSION = "1.0"
REQUEST_LIMIT = 4096
RESPONSE_LIMIT = 65536


def public_id(value):
    return isinstance(value, str) and re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,63}", value) is not None


def decode_json(raw):
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError
            result[key] = value
        return result

    def invalid_constant(_):
        raise ValueError

    try:
        return json.loads(raw.decode("utf-8"), object_pairs_hook=pairs, parse_constant=invalid_constant)
    except (ValueError, UnicodeError, RecursionError):
        raise GatewayError("INVALID_REQUEST") from None


def read_exact(connection, size, deadline):
    parts = bytearray()
    while len(parts) < size:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise GatewayError("COMMAND_TIMEOUT", 504)
        connection.settimeout(remaining)
        chunk = connection.recv(size - len(parts))
        if not chunk:
            raise GatewayError("INVALID_FRAME")
        parts.extend(chunk)
    return bytes(parts)


def receive_frame(connection, limit, deadline, *, require_eof=False):
    size = struct.unpack("!I", read_exact(connection, 4, deadline))[0]
    if not 1 <= size <= limit:
        raise GatewayError("FRAME_TOO_LARGE", 413)
    value = decode_json(read_exact(connection, size, deadline))
    if require_eof:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise GatewayError("COMMAND_TIMEOUT", 504)
        connection.settimeout(remaining)
        if connection.recv(1):
            raise GatewayError("INVALID_FRAME")
    return value


def send_frame(connection, value, limit, deadline):
    raw = json.dumps(value, separators=(",", ":"), allow_nan=False).encode()
    if len(raw) > limit:
        raise GatewayError("FRAME_TOO_LARGE", 413)
    remaining = deadline - time.monotonic()
    if remaining <= 0:
        raise GatewayError("COMMAND_TIMEOUT", 504)
    connection.settimeout(remaining)
    connection.sendall(struct.pack("!I", len(raw)) + raw)


def validate_command(payload):
    if not isinstance(payload, dict) or set(payload) != {"request_id", "command_type", "parameters"}:
        raise GatewayError("INVALID_REQUEST", 422)
    if not public_id(payload["request_id"]):
        raise GatewayError("INVALID_REQUEST", 422)
    try:
        command = CommandType(payload["command_type"])
    except (ValueError, TypeError):
        raise GatewayError("UNSUPPORTED_COMMAND", 422) from None
    try:
        request = CommandRequest(payload["request_id"], command, CommandSource.FUTURE_MOBILE_REQUEST,
                                 payload["parameters"])
        if command == CommandType.CANCEL_OPERATION and not public_id(request.parameters["target_request_id"]):
            raise ValueError
    except (CommandValidationError, TypeError, ValueError):
        raise GatewayError("INVALID_REQUEST", 422) from None
    return request


@dataclass(frozen=True)
class IpcRequest:
    action: str
    principal_id: str
    payload: dict

    @property
    def prefix(self):
        return f"gw:{self.principal_id}:"

    @classmethod
    def parse(cls, value):
        if not isinstance(value, dict) or set(value) != {"protocol_version", "action", "principal_id", "payload"}:
            raise GatewayError("INVALID_REQUEST")
        if value["protocol_version"] != VERSION:
            raise GatewayError("UNSUPPORTED_PROTOCOL")
        principal = value["principal_id"]
        action, payload = value["action"], value["payload"]
        if not isinstance(principal, str) or not re.fullmatch(r"[0-9a-f]{16}", principal):
            raise GatewayError("INVALID_REQUEST")
        if not isinstance(action, str) or action not in {"STATUS", "CAPABILITIES", "SUBMIT", "OPERATION"}:
            raise GatewayError("UNSUPPORTED_COMMAND")
        if not isinstance(payload, dict):
            raise GatewayError("INVALID_REQUEST")
        if action == "SUBMIT":
            validate_command(payload)
        elif action == "OPERATION":
            if set(payload) != {"request_id"} or not public_id(payload["request_id"]):
                raise GatewayError("INVALID_REQUEST")
        elif payload:
            raise GatewayError("INVALID_REQUEST")
        return cls(action, principal, payload)

    def command(self):
        checked = validate_command(self.payload)
        parameters = dict(checked.parameters)
        if checked.command_type == CommandType.CANCEL_OPERATION:
            parameters["target_request_id"] = self.prefix + parameters["target_request_id"]
        return CommandRequest(self.prefix + checked.request_id, checked.command_type,
                              CommandSource.FUTURE_MOBILE_REQUEST, parameters)

    def public_metadata(self, value):
        if isinstance(value, dict):
            return {key: (item[len(self.prefix):] if isinstance(item, str) and item.startswith(self.prefix)
                          else None if item is not None else None)
                    if key in {"request_id", "active_request_id", "target_request_id"}
                    else self.public_metadata(item) for key, item in value.items()}
        if isinstance(value, list):
            return [self.public_metadata(item) for item in value]
        return value
