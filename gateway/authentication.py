"""Explicit local provisioning; bearer secrets are never printed or logged."""
from dataclasses import dataclass
import hmac
import json
import os
from pathlib import Path
import re
import secrets
import stat
import tempfile

from .command_models import CommandType
from .config import private_directory
from .errors import GatewayError

COMMANDS = frozenset(command.value for command in CommandType)


@dataclass(frozen=True)
class Principal:
    principal_id: str
    allowed_commands: frozenset
    allowed_modes: frozenset

    def authorize(self, command, parameters=None):
        if command not in self.allowed_commands:
            raise GatewayError("FORBIDDEN", 403)
        if command == "START_MODE" and (parameters or {}).get("mode") not in self.allowed_modes:
            raise GatewayError("FORBIDDEN", 403)


class CredentialStore:
    def __init__(self, directory):
        self.directory = Path(directory)
        self.path = self.directory / "credential.json"

    def _read(self):
        try:
            private_directory(self.directory)
            descriptor = os.open(self.path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
            with os.fdopen(descriptor, "rb") as stream:
                info = os.fstat(stream.fileno())
                if (not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid()
                        or stat.S_IMODE(info.st_mode) != 0o600 or info.st_nlink != 1):
                    raise ValueError
                raw = stream.read(8193)
            if len(raw) > 8192:
                raise ValueError
            record = json.loads(raw)
            if set(record) != {"schema_version", "principal_id", "token", "allowed_commands", "allowed_modes"}:
                raise ValueError
            if type(record["schema_version"]) is not int or record["schema_version"] != 1:
                raise ValueError
            if not isinstance(record["principal_id"], str) or not re.fullmatch(r"[0-9a-f]{16}", record["principal_id"]):
                raise ValueError
            if not isinstance(record["token"], str) or not re.fullmatch(r"[A-Za-z0-9_-]{43}", record["token"]):
                raise ValueError
            for key, allowed in (("allowed_commands", COMMANDS), ("allowed_modes", set("123456789"))):
                if not isinstance(record[key], list) or any(not isinstance(item, str) or item not in allowed for item in record[key]):
                    raise ValueError
            return record
        except (OSError, ValueError, TypeError, KeyError, GatewayError):
            raise GatewayError("CREDENTIAL_UNAVAILABLE", 503) from None

    def provision(self, *, rotate=False):
        private_directory(self.directory, create=True)
        old = self._read() if rotate else None
        record = old or {"schema_version": 1, "principal_id": secrets.token_hex(8),
                         "allowed_commands": sorted(COMMANDS), "allowed_modes": list("123456789")}
        record["token"] = secrets.token_urlsafe(32)
        descriptor, temporary = tempfile.mkstemp(prefix=".credential-", dir=self.directory)
        try:
            with os.fdopen(descriptor, "w") as stream:
                os.fchmod(stream.fileno(), 0o600)
                json.dump(record, stream)
                stream.flush()
                os.fsync(stream.fileno())
            if rotate:
                os.replace(temporary, self.path)
            else:
                # Atomic no-overwrite publication; another provisioner cannot replace a credential.
                os.link(temporary, self.path)
        except OSError:
            raise GatewayError("CREDENTIAL_PROVISION_FAILED", 503) from None
        finally:
            Path(temporary).unlink(missing_ok=True)

    def authenticate(self, headers):
        values = [value for key, value in headers if key.lower() == b"authorization"]
        if len(values) != 1 or len(values[0]) > 128:
            raise GatewayError("UNAUTHORIZED", 401)
        try:
            scheme, token = values[0].decode("ascii").split(" ")
        except (ValueError, UnicodeError):
            raise GatewayError("UNAUTHORIZED", 401) from None
        record = self._read()
        if scheme.lower() != "bearer" or not hmac.compare_digest(token, record["token"]):
            raise GatewayError("UNAUTHORIZED", 401)
        return Principal(record["principal_id"], frozenset(record["allowed_commands"]),
                         frozenset(record["allowed_modes"]))
