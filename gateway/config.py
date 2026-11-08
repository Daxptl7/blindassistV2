"""Hardware-free local settings and restrictive filesystem checks."""
from dataclasses import dataclass
import ipaddress
import json
import math
import os
from pathlib import Path
import stat

from .errors import GatewayError


def private_directory(path, *, create=False):
    path = Path(path)
    if create:
        path.mkdir(mode=0o700, parents=True, exist_ok=True)
    info = path.lstat()
    if (not stat.S_ISDIR(info.st_mode) or info.st_uid != os.getuid()
            or stat.S_IMODE(info.st_mode) != 0o700):
        raise GatewayError("INSECURE_DIRECTORY", 503)
    return path


@dataclass(frozen=True)
class GatewaySettings:
    host: str = "127.0.0.1"
    port: int = 8765
    ipc_directory: str = f"/tmp/blindassist-ipc-{os.getuid()}"
    credential_directory: str = str(Path(__file__).resolve().parents[1] / "runtime/mobile-gateway")
    ipc_timeout: float = 2.0
    body_timeout: float = 2.0
    max_connections: int = 8
    max_body_bytes: int = 4096

    def __post_init__(self):
        try:
            if not ipaddress.ip_address(self.host).is_loopback:
                raise ValueError
            if type(self.port) is not int or not 1 <= self.port <= 65535:
                raise ValueError
            for value in (self.ipc_timeout, self.body_timeout):
                if isinstance(value, bool) or not math.isfinite(value) or not 0.05 <= value <= 30:
                    raise ValueError
            if type(self.max_connections) is not int or not 1 <= self.max_connections <= 32:
                raise ValueError
            if type(self.max_body_bytes) is not int or not 256 <= self.max_body_bytes <= 4096:
                raise ValueError
            for path in (self.ipc_directory, self.credential_directory):
                if not isinstance(path, str) or not Path(path).is_absolute():
                    raise ValueError
            if len(os.fsencode(self.socket_path)) > 100:
                raise ValueError
        except (ValueError, TypeError):
            raise GatewayError("INVALID_SETTINGS") from None

    @property
    def socket_path(self):
        return str(Path(self.ipc_directory) / "terminal.sock")

    @classmethod
    def load(cls, filename=None):
        values = {}
        if filename:
            try:
                content = Path(filename).read_bytes()
                if len(content) > 8192:
                    raise ValueError
                values = json.loads(content)
                if not isinstance(values, dict):
                    raise ValueError
            except (OSError, ValueError):
                raise GatewayError("INVALID_SETTINGS") from None
        for key in ("host", "port", "ipc_directory", "credential_directory"):
            value = os.environ.get("BLINDASSIST_" + key.upper())
            if value is not None:
                if key == "port":
                    try:
                        value = int(value)
                    except ValueError:
                        raise GatewayError("INVALID_SETTINGS") from None
                values[key] = value
        try:
            return cls(**values)
        except TypeError:
            raise GatewayError("INVALID_SETTINGS") from None
