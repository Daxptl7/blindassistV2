import asyncio
import json
from unittest import mock
import unittest

from fastapi.testclient import TestClient

from gateway.api import create_app, LocalBoundary
from gateway_support import GatewayFixture


class ApiTests(GatewayFixture, unittest.TestCase):
    def setUp(self):
        super().setUp()
        self.app = create_app(self.settings)
        self.http = TestClient(self.app, base_url="http://127.0.0.1", client=("127.0.0.1", 12345))
        self.http.__enter__()
        self.addCleanup(self.http.__exit__, None, None, None)

    def post(self, identifier="one", **changes):
        payload = {"request_id": identifier, "command_type": "START_MODE", "parameters": {"mode": "1"}}
        payload.update(changes)
        return self.http.post("/api/v1/commands", headers=self.headers, json=payload)

    def test_exactly_six_routes_health_and_authentication(self):
        self.assertEqual(len(self.app.routes), 6)
        health = self.http.get("/api/v1/health")
        self.assertEqual(health.status_code, 200)
        self.assertFalse(health.json()["terminal_checked"])
        for path in ("/api/v1/device/status", "/api/v1/device/capabilities", "/api/v1/commands/one"):
            self.assertEqual(self.http.get(path).status_code, 401)
            self.assertEqual(self.http.get(path, headers={"Authorization": "Bearer wrong"}).status_code, 401)
        self.assertEqual(self.http.get("/docs", headers=self.headers).status_code, 404)
        self.assertEqual(self.http.get("/openapi.json", headers=self.headers).status_code, 404)

    def test_real_status_capabilities_and_no_cache(self):
        response = self.http.get("/api/v1/device/status", headers=self.headers)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["terminal"]["terminal_state"], "IDLE")
        self.assertEqual(response.headers["cache-control"], "no-store")
        capabilities = self.http.get("/api/v1/device/capabilities", headers=self.headers).json()
        self.assertEqual(capabilities["gateway_authentication"], "LOCAL_BEARER")
        self.assertIsNone(capabilities["terminal"]["modes"][0]["hardware_validated"])

    def test_acceptance_is_not_completion_and_conflicts_are_explicit(self):
        response = self.post()
        self.assertEqual(response.status_code, 202)
        self.assertEqual(response.json()["command"]["state"], "PENDING")
        self.assertEqual(self.post(parameters={"mode": "2"}).status_code, 409)
        request = self.broker.take_next()
        self.assertEqual(self.post("busy").json()["command"]["error_code"], "TERMINAL_BUSY")
        self.broker.finish(request.request_id)
        self.assertEqual(self.post().status_code, 200)
        self.assertEqual(self.http.get("/api/v1/commands/one", headers=self.headers).json()["command"]["state"], "COMPLETED")

    def test_cancel_uses_separate_id_and_reports_target_state(self):
        self.post()
        result = self.http.post("/api/v1/commands/one/cancel", headers=self.headers, json={"request_id": "cancel-one"})
        self.assertEqual(result.status_code, 200)
        self.assertEqual(result.json()["command"]["data"]["target_state"], "CANCELLED")
        self.assertIsNone(self.broker.take_next())
        unknown = self.http.post("/api/v1/commands/missing/cancel", headers=self.headers, json={"request_id": "cancel-missing"})
        self.assertEqual(unknown.status_code, 404)

    def test_forbidden_allowlist_before_ipc(self):
        record = self.store._read()
        record.update(allowed_commands=["GET_STATUS", "START_MODE"], allowed_modes=["2"])
        self.store.path.write_text(json.dumps(record))
        self.assertEqual(self.post().status_code, 403)
        self.assertEqual(self.http.get("/api/v1/device/capabilities", headers=self.headers).status_code, 403)
        self.assertEqual(self.broker.get_status()["retained_request_count"], 0)

    def test_strict_requests_have_no_payload_echo_or_submission(self):
        for changes in ({"request_id": "gw:other:one"}, {"request_id": 7}, {"source": "PHYSICAL_INPUT"},
                        {"command_type": "SHUTDOWN"}, {"parameters": {"mode": 1}},
                        {"parameters": {"mode": "1", "prompt": "PRIVATE_SENTINEL"}},
                        {"parameters": None}):
            with self.subTest(keys=list(changes)):
                response = self.post(**changes)
                self.assertEqual(response.status_code, 422)
                self.assertNotIn("PRIVATE_SENTINEL", response.text)
        self.assertEqual(self.broker.get_status()["retained_request_count"], 0)

    def test_malformed_duplicate_json_and_oversized_body(self):
        headers = {**self.headers, "Content-Type": "application/json"}
        for raw in ('{"request_id":"a","request_id":"b"}', '{"x":NaN}', '{broken'):
            self.assertIn(self.http.post("/api/v1/commands", headers=headers, content=raw).status_code, (400, 422))
        self.assertEqual(self.http.post("/api/v1/commands", headers=headers, content="x" * 4097).status_code, 413)
        self.assertEqual(self.http.post("/api/v1/commands", headers=self.headers, content="{}").status_code, 422)

    def test_remote_peer_browser_origin_host_query_and_duplicate_authorization_rejected(self):
        with TestClient(self.app, base_url="http://127.0.0.1", client=("192.168.1.8", 3)) as remote:
            self.assertEqual(remote.get("/api/v1/health").status_code, 403)
        for headers, path in (({**self.headers, "Origin": "https://example.org"}, "/api/v1/device/status"),
                              ({**self.headers, "Host": "evil.example"}, "/api/v1/device/status"),
                              (self.headers, "/api/v1/device/status?token=PRIVATE_SENTINEL")):
            self.assertEqual(self.http.get(path, headers=headers).status_code, 403)
        duplicate = list(self.headers.items()) * 2
        self.assertEqual(self.http.get("/api/v1/device/status", headers=duplicate).status_code, 401)

    def test_terminal_unavailable_does_not_change_gateway_health(self):
        self.server.close()
        self.assertEqual(self.http.get("/api/v1/device/status", headers=self.headers).status_code, 503)
        self.assertEqual(self.http.get("/api/v1/health").status_code, 200)
        self.assertEqual(self.broker.get_status()["terminal_state"], "IDLE")

    def test_internal_exception_is_sanitized(self):
        with mock.patch("gateway.ipc_client.IpcClient.request", side_effect=RuntimeError("PRIVATE_SENTINEL")):
            response = self.http.get("/api/v1/device/status", headers=self.headers)
        self.assertEqual(response.status_code, 500)
        self.assertNotIn("PRIVATE_SENTINEL", response.text)

    def test_http_boundary_deadline_chunked_limit_and_concurrency(self):
        async def run():
            from dataclasses import replace
            settings = replace(self.settings, body_timeout=0.05, max_connections=1)
            entered, release = asyncio.Event(), asyncio.Event()

            async def downstream(scope, receive, send):
                entered.set()
                await release.wait()
                await send({"type": "http.response.start", "status": 200, "headers": []})
                await send({"type": "http.response.body", "body": b"{}"})

            boundary = LocalBoundary(downstream, settings, self.store)
            scope = {"type": "http", "client": ("127.0.0.1", 1), "path": "/api/v1/health", "method": "GET",
                     "headers": [(b"host", b"127.0.0.1")], "query_string": b""}

            async def body():
                return {"type": "http.request", "body": b""}

            messages = []
            async def send(value):
                messages.append(value)

            first = asyncio.create_task(boundary(dict(scope), body, send))
            await entered.wait()
            await boundary(dict(scope), body, send)
            self.assertEqual(messages[0]["status"], 503)
            release.set()
            await first
            messages.clear()

            async def stalled():
                await asyncio.sleep(0.2)

            await boundary(dict(scope), stalled, send)
            self.assertEqual(messages[0]["status"], 504)
            messages.clear()

            async def oversized_chunk():
                return {"type": "http.request", "body": b"x" * 4097, "more_body": True}

            await boundary(dict(scope), oversized_chunk, send)
            self.assertEqual(messages[0]["status"], 413)
        asyncio.run(run())
