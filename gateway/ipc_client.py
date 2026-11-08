"""The gateway's only terminal interface. Never starts or closes the terminal."""
import os
from pathlib import Path
import socket
import stat
import threading
import time

from .config import private_directory
from .errors import GatewayError
from .ipc_protocol import VERSION, REQUEST_LIMIT, RESPONSE_LIMIT, send_frame, receive_frame


class IpcClient:
    def __init__(self, settings):
        self.settings = settings
        self._slots = threading.BoundedSemaphore(settings.max_connections)

    def request(self, action, principal_id, payload=None):
        if not self._slots.acquire(blocking=False):
            raise GatewayError("GATEWAY_BUSY", 503)
        try:
            try:
                private_directory(self.settings.ipc_directory)
                info = Path(self.settings.socket_path).lstat()
                if (not stat.S_ISSOCK(info.st_mode) or info.st_uid != os.getuid()
                        or stat.S_IMODE(info.st_mode) != 0o600):
                    raise GatewayError("INSECURE_SOCKET", 503)
                deadline = time.monotonic() + self.settings.ipc_timeout
                with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as connection:
                    connection.settimeout(self.settings.ipc_timeout)
                    connection.connect(self.settings.socket_path)
                    send_frame(connection, {"protocol_version": VERSION, "action": action,
                                           "principal_id": principal_id, "payload": payload or {}},
                               REQUEST_LIMIT, deadline)
                    connection.shutdown(socket.SHUT_WR)
                    try:
                        response = receive_frame(connection, RESPONSE_LIMIT, deadline, require_eof=True)
                    except GatewayError as error:
                        if error.code == "COMMAND_TIMEOUT":
                            raise
                        raise GatewayError("INVALID_IPC_RESPONSE", 502) from None
            except (TimeoutError, socket.timeout):
                raise GatewayError("COMMAND_TIMEOUT", 504) from None
            except OSError:
                raise GatewayError("TERMINAL_UNAVAILABLE", 503) from None
            if (not isinstance(response, dict) or response.get("protocol_version") != VERSION
                    or type(response.get("ok")) is not bool):
                raise GatewayError("INVALID_IPC_RESPONSE", 502)
            if response["ok"]:
                if set(response) != {"protocol_version", "ok", "data"} or not isinstance(response["data"], dict):
                    raise GatewayError("INVALID_IPC_RESPONSE", 502)
                return response["data"]
            # Only fixed protocol error codes may cross into the public error response.
            codes = {"INVALID_REQUEST": 400, "UNSUPPORTED_PROTOCOL": 400, "UNSUPPORTED_COMMAND": 422,
                     "UNKNOWN_OPERATION": 404, "TERMINAL_UNAVAILABLE": 503, "IPC_BUSY": 503,
                     "COMMAND_TIMEOUT": 504, "FRAME_TOO_LARGE": 413, "INVALID_FRAME": 400,
                     "INTERNAL_ERROR": 500}
            code = response.get("error_code")
            if not isinstance(code, str) or code not in codes or set(response) != {"protocol_version", "ok", "error_code"}:
                raise GatewayError("INVALID_IPC_RESPONSE", 502)
            raise GatewayError(code, codes[code])
        finally:
            self._slots.release()
