import json
import os
from pathlib import Path
import tempfile
import unittest

from gateway.authentication import CredentialStore
from gateway.config import GatewaySettings
from gateway.errors import GatewayError


class AuthenticationTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.store = CredentialStore(Path(self.temporary.name) / "credentials")
        self.store.provision()

    def headers(self):
        token = json.loads(self.store.path.read_text())["token"]
        return [(b"authorization", ("Bearer " + token).encode())]

    def test_random_secret_and_permissions(self):
        self.assertEqual(self.store.path.stat().st_mode & 0o777, 0o600)
        self.assertEqual(self.store.directory.stat().st_mode & 0o777, 0o700)
        other = CredentialStore(Path(self.temporary.name) / "other")
        other.provision()
        self.assertNotEqual(self.headers(), [(b"authorization", ("Bearer " + other._read()["token"]).encode())])
        self.store.authenticate(self.headers()).authorize("START_MODE", {"mode": "1"})

    def test_missing_wrong_duplicate_and_malformed_credentials(self):
        for headers in ([], [(b"authorization", b"Bearer wrong")], self.headers() * 2,
                        [(b"authorization", b"Bearer x y")], [(b"authorization", b"Bearer \xff")]):
            with self.subTest(kind=len(headers)), self.assertRaises(GatewayError) as error:
                self.store.authenticate(headers)
            self.assertEqual(error.exception.code, "UNAUTHORIZED")

    def test_rotation_preserves_identity_and_revokes_old_secret(self):
        old = self.headers()
        identity = self.store.authenticate(old).principal_id
        self.store.provision(rotate=True)
        self.assertEqual(self.store.authenticate(self.headers()).principal_id, identity)
        with self.assertRaises(GatewayError):
            self.store.authenticate(old)

    def test_initialization_never_overwrites_existing_secret(self):
        old = self.headers()
        with self.assertRaises(GatewayError):
            self.store.provision()
        self.assertEqual(old, self.headers())

    def test_allowlist(self):
        record = self.store._read()
        record.update(allowed_commands=["GET_STATUS", "START_MODE"], allowed_modes=["1"])
        self.store.path.write_text(json.dumps(record))
        principal = self.store.authenticate(self.headers())
        for command, parameters in (("SHUTDOWN", {}), ("CANCEL_OPERATION", {}), ("START_MODE", {"mode": "2"})):
            with self.assertRaises(GatewayError) as error:
                principal.authorize(command, parameters)
            self.assertEqual(error.exception.status, 403)

    def test_rejects_insecure_file_and_directory_and_symlink(self):
        self.store.path.chmod(0o644)
        with self.assertRaises(GatewayError):
            self.store.authenticate(self.headers())
        self.store.path.chmod(0o600)
        self.store.directory.chmod(0o755)
        with self.assertRaises(GatewayError):
            self.store.authenticate(self.headers())
        self.store.directory.chmod(0o700)
        original = self.store.path.with_suffix(".old")
        self.store.path.rename(original)
        self.store.path.symlink_to(original)
        with self.assertRaises(GatewayError):
            self.store.authenticate(self.headers())

    def test_missing_credential_is_fail_closed(self):
        self.store.path.unlink()
        with self.assertRaises(GatewayError) as error:
            self.store.authenticate([(b"authorization", b"Bearer wrong")])
        self.assertEqual(error.exception.status, 503)

    def test_settings_reject_non_loopback_and_invalid_bounds(self):
        for settings in ({"host": "0.0.0.0"}, {"host": "192.168.1.2"}, {"host": "localhost"},
                         {"port": True}, {"port": 0}, {"ipc_timeout": float("nan")},
                         {"max_connections": 0}, {"ipc_directory": "relative"},
                         {"ipc_directory": "/" + "x" * 110}):
            with self.subTest(settings=list(settings)), self.assertRaises(GatewayError):
                GatewaySettings(**settings)
        self.assertEqual(GatewaySettings().port, 8765)
        self.assertEqual(GatewaySettings(host="::1").host, "::1")


if __name__ == "__main__":
    unittest.main()
