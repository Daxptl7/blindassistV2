"""Optional terminal-owned UDS bridge to the existing thread-safe broker API."""
from dataclasses import asdict
import fcntl
import os
from pathlib import Path
import socket
import stat
import threading
import time

from .config import private_directory
from .errors import GatewayError
from .ipc_protocol import VERSION, REQUEST_LIMIT, RESPONSE_LIMIT, IpcRequest, receive_frame, send_frame


class IpcServer:
    def __init__(self, broker, settings):
        self.broker, self.settings = broker, settings
        self._stop = threading.Event()
        self._lock = threading.Lock()
        self._connections = set()
        self._workers = set()
        self._slots = threading.BoundedSemaphore(settings.max_connections)
        self._listener = self._thread = self._lease = self._identity = None

    def start(self):
        if self._listener is not None or self._stop.is_set():
            raise GatewayError("IPC_ALREADY_STARTED", 503)
        directory = private_directory(self.settings.ipc_directory, create=True)
        path = Path(self.settings.socket_path)
        try:
            descriptor = os.open(directory / "server.lock", os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW | os.O_NONBLOCK, 0o600)
            self._lease = os.fdopen(descriptor, "rb")
            info = os.fstat(descriptor)
            if (not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid()
                    or stat.S_IMODE(info.st_mode) != 0o600 or info.st_nlink != 1):
                raise GatewayError("INSECURE_SOCKET", 503)
            fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
            if path.exists() or path.is_symlink():
                info = path.lstat()
                if not stat.S_ISSOCK(info.st_mode) or info.st_uid != os.getuid():
                    raise GatewayError("INSECURE_SOCKET", 503)
                with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as probe:
                    probe.settimeout(self.settings.ipc_timeout)
                    try:
                        probe.connect(str(path))
                    except ConnectionRefusedError:
                        if path.lstat().st_ino != info.st_ino:
                            raise GatewayError("INSECURE_SOCKET", 503)
                        path.unlink()
                    else:
                        raise GatewayError("IPC_ALREADY_STARTED", 503)
            self._listener = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            self._listener.bind(str(path))
            info = path.lstat()
            self._identity = (info.st_dev, info.st_ino)
            path.chmod(0o600)
            self._listener.listen(self.settings.max_connections)
            self._listener.settimeout(0.1)
            self._thread = threading.Thread(target=self._accept, name="terminal-ipc", daemon=True)
            self._thread.start()
            return self
        except (OSError, GatewayError) as error:
            self.close()
            if isinstance(error, GatewayError):
                raise
            raise GatewayError("IPC_START_FAILED", 503) from None

    def _dispatch(self, request):
        if self.broker.get_status()["terminal_state"] in {"CLOSED", "SHUTTING_DOWN"}:
            raise GatewayError("TERMINAL_UNAVAILABLE", 503)
        if request.action == "STATUS":
            data = self.broker.get_status()
        elif request.action == "CAPABILITIES":
            data = self.broker.get_capabilities()
        elif request.action == "OPERATION":
            receipt = self.broker.get_operation(request.prefix + request.payload["request_id"])
            if receipt is None:
                raise GatewayError("UNKNOWN_OPERATION", 404)
            data = asdict(receipt)
        else:
            data = asdict(self.broker.submit(request.command()))
        return request.public_metadata(data)

    def _accept(self):
        while not self._stop.is_set():
            try:
                connection, _ = self._listener.accept()
            except socket.timeout:
                continue
            except OSError:
                break
            if not self._slots.acquire(blocking=False):
                # Close overflow immediately; do not block the accept loop writing to a slow peer.
                connection.close()
                continue
            with self._lock:
                if self._stop.is_set():
                    connection.close()
                    self._slots.release()
                    break
                worker = threading.Thread(target=self._serve, args=(connection,), daemon=True)
                self._connections.add(connection)
                self._workers.add(worker)
                worker.start()

    def _serve(self, connection):
        deadline = time.monotonic() + self.settings.ipc_timeout
        try:
            try:
                value = receive_frame(connection, REQUEST_LIMIT, deadline, require_eof=True)
                data = self._dispatch(IpcRequest.parse(value))
                response = {"protocol_version": VERSION, "ok": True, "data": data}
            except GatewayError as error:
                response = {"protocol_version": VERSION, "ok": False, "error_code": error.code}
            except TimeoutError:
                response = {"protocol_version": VERSION, "ok": False, "error_code": "COMMAND_TIMEOUT"}
            except OSError:
                return
            except Exception:
                response = {"protocol_version": VERSION, "ok": False, "error_code": "INTERNAL_ERROR"}
            # A fixed error frame gets a short, separate write budget after a read deadline.
            send_frame(connection, response, RESPONSE_LIMIT,
                       max(deadline, time.monotonic() + 0.05) if not response["ok"] else deadline)
        except (OSError, GatewayError):
            pass
        finally:
            connection.close()
            with self._lock:
                self._connections.discard(connection)
                self._workers.discard(threading.current_thread())
            self._slots.release()

    def close(self):
        self._stop.set()
        if self._listener is not None:
            self._listener.close()
        with self._lock:
            workers = list(self._workers)
            for connection in self._connections:
                try:
                    connection.shutdown(socket.SHUT_RDWR)
                except OSError:
                    pass
        deadline = time.monotonic() + self.settings.ipc_timeout + 0.2
        for thread in [self._thread, *workers]:
            if thread is not None and thread is not threading.current_thread():
                thread.join(max(0, deadline - time.monotonic()))
        path = Path(self.settings.socket_path)
        if self._identity is not None:
            try:
                info = path.lstat()
                if (info.st_dev, info.st_ino) == self._identity:
                    path.unlink()
            except FileNotFoundError:
                pass
            self._identity = None
        if self._lease is not None:
            self._lease.close()
            self._lease = None
        # Deliberately never close the broker or touch any terminal resource.
