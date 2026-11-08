"""Real socket and broker fixture; mode execution remains owned by the test thread."""
import json
from pathlib import Path
import tempfile

from gateway.authentication import CredentialStore
from gateway.command_broker import CommandBroker
from gateway.command_models import ModeCapability
from gateway.config import GatewaySettings
from gateway.ipc_client import IpcClient
from gateway.ipc_server import IpcServer


class GatewayFixture:
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="ba-", dir="/tmp")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.settings = GatewaySettings(ipc_directory=str(self.root / "ipc"),
                                        credential_directory=str(self.root / "auth"), ipc_timeout=0.3)
        self.store = CredentialStore(self.settings.credential_directory)
        self.store.provision()
        record = json.loads(self.store.path.read_text())
        self.principal = record["principal_id"]
        self.headers = {"Authorization": "Bearer " + record["token"]}
        self.broker = CommandBroker({mode: ModeCapability(mode, mode != "9") for mode in "129"})
        self.addCleanup(self.broker.close)
        self.server = IpcServer(self.broker, self.settings).start()
        self.addCleanup(self.server.close)
        self.ipc = IpcClient(self.settings)

    def submit(self, identifier="request-1", mode="1", **changes):
        payload = {"request_id": identifier, "command_type": "START_MODE", "parameters": {"mode": mode}}
        payload.update(changes)
        return self.ipc.request("SUBMIT", self.principal, payload)
