"""Hardware-free real HTTP/UDS smoke, including a killed/restarted gateway process.

Run from the repository root: python3 scripts/smoke_gateway.py
Uses port 8765; refuses to run if occupied. No secrets appear in argv or output.
"""
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from gateway.command_broker import CommandBroker
from gateway.command_models import CommandRequest, CommandSource, CommandType, ModeCapability
from gateway.config import GatewaySettings
from gateway.ipc_server import IpcServer


def main():
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 8765))  # Never stop or reuse another listener.
    with tempfile.TemporaryDirectory(prefix="ba-smoke-", dir="/tmp") as directory:
        root = Path(directory)
        settings = GatewaySettings(ipc_directory=str(root / "ipc"), credential_directory=str(root / "auth"))
        env = {**os.environ, "PYTHONDONTWRITEBYTECODE": "1", "BLINDASSIST_HOST": "127.0.0.1",
               "BLINDASSIST_PORT": "8765", "BLINDASSIST_IPC_DIRECTORY": settings.ipc_directory,
               "BLINDASSIST_CREDENTIAL_DIRECTORY": settings.credential_directory}
        command = [sys.executable, "-m", "gateway.server"]
        subprocess.run([*command, "--init-credentials"], cwd=ROOT, env=env, check=True, capture_output=True, timeout=10)
        record = json.loads((root / "auth/credential.json").read_text())
        curl_config = root / "curl.conf"
        descriptor = os.open(curl_config, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        with os.fdopen(descriptor, "w") as stream:
            stream.write('header = "Authorization: Bearer ' + record["token"] + '"\n')
        invalid_config = root / "invalid.conf"
        descriptor = os.open(invalid_config, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        with os.fdopen(descriptor, "w") as stream:
            stream.write('header = "Authorization: Bearer invalid"\n')
        broker = CommandBroker({"1": ModeCapability("1", True)})
        server = IpcServer(broker, settings).start()
        gateway = None
        results = {}
        executed_requests = []

        def fake_handler(request):
            # Record real broker leases at the execution owner; no hardware operation.
            executed_requests.append(request.request_id)
            broker.finish(request.request_id)

        def http(path, *, data=None, invalid=False):
            args = ["curl", "-q", "--config", str(invalid_config if invalid else curl_config),
                    "--fail-with-body", "--silent", "--show-error", "--max-time", "4",
                    "--write-out", "\n%{http_code}"]
            if data is not None:
                body = root / "request.json"
                body.write_text(json.dumps(data))
                args += ["-H", "Content-Type: application/json", "--data-binary", "@" + str(body)]
            result = subprocess.run([*args, "http://127.0.0.1:8765" + path], capture_output=True, text=True, timeout=6)
            body, _, code = result.stdout.rpartition("\n")
            if result.returncode not in (0, 22) or not code.isdigit():
                raise RuntimeError("HTTP_SMOKE_FAILED")
            return int(code), json.loads(body)

        def start():
            logfile = (root / "server.log").open("ab")
            process = subprocess.Popen(command, cwd=ROOT, env=env, stdout=logfile, stderr=subprocess.STDOUT)
            logfile.close()
            try:
                deadline = time.monotonic() + 10
                while time.monotonic() < deadline:
                    if process.poll() is not None:
                        raise RuntimeError("GATEWAY_START_FAILED")
                    try:
                        if http("/api/v1/health")[0] == 200:
                            return process
                    except (RuntimeError, ValueError):
                        pass
                    time.sleep(0.05)
                raise RuntimeError("GATEWAY_START_TIMEOUT")
            except Exception:
                process.kill()
                process.wait(timeout=5)
                raise

        try:
            gateway = start()
            assert http("/api/v1/device/status")[1]["terminal"]["terminal_state"] == "IDLE"
            results["authenticated_status"] = 200
            assert http("/api/v1/device/status", invalid=True)[0] == 401
            results["invalid_credential"] = 401
            payload = {"request_id": "smoke-mode", "command_type": "START_MODE", "parameters": {"mode": "1"}}
            assert http("/api/v1/commands", data=payload)[0] == 202
            request = broker.take_next()
            assert request is not None
            assert http("/api/v1/device/status")[1]["terminal"]["terminal_state"] == "BUSY"
            busy, body = http("/api/v1/commands", data={**payload, "request_id": "busy"})
            assert busy == 409 and body["command"]["error_code"] == "TERMINAL_BUSY"
            results["busy"] = 409
            fake_handler(request)
            gateway.kill()
            gateway.wait(timeout=5)
            physical = CommandRequest("physical-smoke", CommandType.START_MODE, CommandSource.PHYSICAL_INPUT, {"mode": "1"})
            broker.submit(physical)
            assert broker.take_next() == physical
            fake_handler(physical)
            results["physical_dispatch_after_gateway_kill"] = "COMPLETED"
            gateway = start()
            code, body = http("/api/v1/commands", data=payload)
            assert code == 200 and body["command"]["state"] == "COMPLETED"
            assert broker.take_next() is None and executed_requests.count(request.request_id) == 1
            results["duplicate_after_gateway_restart"] = "COMPLETED_WITHOUT_REEXECUTION"
            cancellation_target = {**payload, "request_id": "cancel-target"}
            assert http("/api/v1/commands", data=cancellation_target)[0] == 202
            code, body = http("/api/v1/commands/cancel-target/cancel", data={"request_id": "cancel"})
            assert code == 200 and body["command"]["data"]["target_state"] == "CANCELLED"
            results["pending_cancel"] = "CANCELLED"
            server.close()
            assert http("/api/v1/device/status")[0] == 503
            assert http("/api/v1/health")[0] == 200
            results["terminal_unavailable"] = 503
            results["gateway_health_without_terminal"] = 200
            assert broker.get_status()["terminal_state"] == "IDLE"
        finally:
            if gateway is not None and gateway.poll() is None:
                gateway.terminate()
                try:
                    gateway.wait(timeout=7)
                except subprocess.TimeoutExpired:
                    gateway.kill()
                    gateway.wait(timeout=5)
            server.close()
            broker.close()
        print(json.dumps(results, indent=2))


if __name__ == "__main__":
    main()
