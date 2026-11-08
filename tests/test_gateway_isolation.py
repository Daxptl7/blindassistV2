import os
from pathlib import Path
import subprocess
import sys
import unittest
from unittest import mock

from gateway.ipc_client import IpcClient
from gateway_support import GatewayFixture
from test_mobile_dispatch_regression import controller


class TerminalIntegrationTests(unittest.TestCase):
    def test_disabled_by_default_and_failure_preserves_physical_dispatch(self):
        terminal = controller()
        broker = terminal._initialize_command_dispatcher()
        self.addCleanup(broker.close)
        with mock.patch.dict(os.environ, {"BLINDASSIST_IPC_ENABLED": "0"}):
            terminal._initialize_terminal_ipc()
        self.assertIsNone(terminal._terminal_ipc_server)
        with mock.patch.dict(os.environ, {"BLINDASSIST_IPC_ENABLED": "1"}), \
                mock.patch("gateway.ipc_server.IpcServer.start", side_effect=OSError("private sentinel")):
            terminal._initialize_terminal_ipc()
        self.assertIs(terminal._command_broker, broker)
        terminal.run_mode("1")
        terminal.MODE_MAP["1"].assert_called_once()
        self.assertNotIn("private sentinel", str(terminal.logger.mock_calls))


class IsolationTests(GatewayFixture, unittest.TestCase):
    def test_actual_terminal_hook_uses_existing_broker_and_only_owner_executes(self):
        terminal = controller()
        terminal._command_broker = self.broker
        self.server.close()
        with mock.patch.dict(os.environ, {"BLINDASSIST_IPC_ENABLED": "1",
                                          "BLINDASSIST_IPC_DIRECTORY": self.settings.ipc_directory}):
            terminal._initialize_terminal_ipc()
        self.addCleanup(terminal._close_terminal_ipc)
        self.assertIs(terminal._terminal_ipc_server.broker, self.broker)
        self.submit()
        terminal.MODE_MAP["1"].assert_not_called()
        terminal._execute_broker_request(self.broker.take_next())
        terminal.MODE_MAP["1"].assert_called_once()
        terminal._close_terminal_ipc()
        terminal.run_mode("1")
        self.assertEqual(terminal.MODE_MAP["1"].call_count, 2)

    def test_gateway_imports_do_not_initialize_terminal_or_hardware(self):
        code = '''
import importlib.abc, sys
class DenyHardware(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname.split('.')[0] in {'main', 'modules', 'services', 'serial', 'cv2', 'picamera2',
                                      'pygame', 'pyttsx3', 'pyaudio', 'sounddevice', 'speech_recognition'}:
            raise RuntimeError('HARDWARE_IMPORT_FORBIDDEN')
sys.meta_path.insert(0, DenyHardware())
import gateway.api, gateway.server, gateway.ipc_client
assert 'gateway.ipc_server' not in sys.modules
assert 'gateway.command_broker' not in sys.modules
'''
        result = subprocess.run([sys.executable, "-c", code], cwd=Path(__file__).resolve().parents[1],
                                capture_output=True, text=True, timeout=15)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_gateway_client_disconnect_does_not_cancel_active_mode(self):
        self.submit()
        request = self.broker.take_next()
        self.ipc = IpcClient(self.settings)
        self.assertEqual(self.ipc.request("STATUS", self.principal)["terminal_state"], "BUSY")
        self.assertFalse(self.broker.cancellation_event(request.request_id).is_set())
        self.server.close()
        self.assertEqual(self.broker.get_status()["terminal_state"], "BUSY")
        self.broker.finish(request.request_id)
        self.assertEqual(self.broker.get_status()["terminal_state"], "IDLE")
