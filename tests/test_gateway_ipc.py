import json
import socket
import struct
import time
import unittest

from gateway.errors import GatewayError
from gateway.ipc_protocol import decode_json, receive_frame, RESPONSE_LIMIT, VERSION
from gateway.ipc_server import IpcServer
from gateway_support import GatewayFixture


class IpcTests(GatewayFixture, unittest.TestCase):
    def raw(self, data):
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as connection:
            connection.settimeout(1)
            connection.connect(self.settings.socket_path)
            connection.sendall(data)
            connection.shutdown(socket.SHUT_WR)
            return receive_frame(connection, RESPONSE_LIMIT, time.monotonic() + 1)

    def frame(self, value):
        raw = json.dumps(value).encode()
        return struct.pack("!I", len(raw)) + raw

    def test_real_status_capabilities_and_restrictive_socket(self):
        self.assertEqual(self.ipc.request("STATUS", self.principal)["terminal_state"], "IDLE")
        self.assertEqual(len(self.ipc.request("CAPABILITIES", self.principal)["modes"]), 3)
        self.assertEqual((self.root / "ipc/terminal.sock").stat().st_mode & 0o777, 0o600)
        self.assertEqual((self.root / "ipc").stat().st_mode & 0o777, 0o700)

    def test_trailing_frame_never_submits(self):
        message = {"protocol_version": VERSION, "action": "SUBMIT", "principal_id": self.principal,
                   "payload": {"request_id": "one", "command_type": "START_MODE", "parameters": {"mode": "1"}}}
        response = self.raw(self.frame(message) + b"extra")
        self.assertEqual(response["error_code"], "INVALID_FRAME")
        self.assertEqual(self.broker.get_status()["retained_request_count"], 0)

    def test_size_truncation_duplicate_and_version_errors(self):
        for data, code in ((struct.pack("!I", 4097), "FRAME_TOO_LARGE"),
                           (struct.pack("!I", 20) + b"{}", "INVALID_FRAME"),
                           (struct.pack("!I", 13) + b'{"x":1,"x":2}', "INVALID_REQUEST"),
                           (self.frame({"protocol_version": "2", "action": "STATUS", "principal_id": self.principal,
                                        "payload": {}}), "UNSUPPORTED_PROTOCOL")):
            with self.subTest(code=code):
                self.assertEqual(self.raw(data)["error_code"], code)

    def test_bad_json_and_nonfinite_values(self):
        for raw in (b'{"x":NaN}', b'{"x":Infinity}', b'\xff', b'{"x":1,"x":2}'):
            with self.assertRaises(GatewayError):
                decode_json(raw)

    def test_live_socket_not_replaced(self):
        inode = (self.root / "ipc/terminal.sock").stat().st_ino
        with self.assertRaises(GatewayError):
            IpcServer(self.broker, self.settings).start()
        self.assertEqual((self.root / "ipc/terminal.sock").stat().st_ino, inode)
        self.assertEqual(self.ipc.request("STATUS", self.principal)["terminal_state"], "IDLE")

    def test_stop_is_bounded_with_partial_client_and_does_not_close_broker(self):
        connection = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.addCleanup(connection.close)
        connection.connect(self.settings.socket_path)
        connection.sendall(b"\x00")
        start = time.monotonic()
        self.server.close()
        self.assertLess(time.monotonic() - start, 1)
        self.assertEqual(self.broker.get_status()["terminal_state"], "IDLE")
        with self.assertRaises(GatewayError) as error:
            self.ipc.request("STATUS", self.principal)
        self.assertEqual(error.exception.status, 503)

    def test_stale_socket_can_restart_and_regular_file_is_preserved(self):
        self.server.close()
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as stale:
            stale.bind(self.settings.socket_path)
        replacement = IpcServer(self.broker, self.settings).start()
        replacement.close()
        path = self.root / "ipc/terminal.sock"
        path.write_text("preserve")
        with self.assertRaises(GatewayError):
            IpcServer(self.broker, self.settings).start()
        self.assertEqual(path.read_text(), "preserve")

    def test_unknown_action_and_untrusted_source_rejected(self):
        for action, payload in (("SHUTDOWN", {}), ("SUBMIT", {"request_id": "x", "command_type": "GET_STATUS",
                                "parameters": {}, "source": "PHYSICAL_INPUT"})):
            with self.assertRaises(GatewayError):
                self.ipc.request(action, self.principal, payload)

    def test_client_slots_are_bounded(self):
        for _ in range(self.settings.max_connections):
            self.ipc._slots.acquire()
        with self.assertRaises(GatewayError) as error:
            self.ipc.request("STATUS", self.principal)
        self.assertEqual(error.exception.code, "GATEWAY_BUSY")


if __name__ == "__main__":
    unittest.main()
