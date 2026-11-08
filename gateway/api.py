"""Loopback HTTP boundary. Imports no terminal, broker server, or hardware modules."""
import asyncio
import ipaddress

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from pydantic import ValidationError
from starlette.exceptions import HTTPException
from starlette.responses import JSONResponse

from .authentication import CredentialStore
from .config import GatewaySettings
from .errors import GatewayError, broker_status
from .ipc_client import IpcClient
from .ipc_protocol import decode_json, public_id
from .schemas import CancellationSubmission, CommandSubmission

API_VERSION = "1.0"


def error_response(code, status):
    headers = {"WWW-Authenticate": "Bearer"} if status == 401 else None
    return JSONResponse({"api_version": API_VERSION, "error": {"code": code}}, status_code=status, headers=headers)


class LocalBoundary:
    """Limits admission and body bytes before framework parsing or IPC work."""
    def __init__(self, app, settings, store):
        self.app, self.settings, self.store = app, settings, store
        self.active = 0

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        admitted = False
        started = False

        async def safe_send(message):
            nonlocal started
            if message["type"] == "http.response.start":
                started = True
                message["headers"] = list(message.get("headers", [])) + [
                    (b"cache-control", b"no-store"), (b"x-content-type-options", b"nosniff")]
            await send(message)

        try:
            peer = scope.get("client")
            try:
                loopback = peer and ipaddress.ip_address(peer[0]).is_loopback
            except ValueError:
                loopback = False
            if not loopback:
                raise GatewayError("FORBIDDEN", 403)
            headers = scope.get("headers", [])
            hosts = [value for key, value in headers if key.lower() == b"host"]
            allowed = {"127.0.0.1", "localhost", "[::1]", self.settings.host}
            allowed |= {f"{host}:{self.settings.port}" for host in list(allowed)}
            if len(hosts) != 1 or hosts[0].decode("latin-1").lower() not in allowed:
                raise GatewayError("FORBIDDEN", 403)
            if scope.get("query_string") or any(key.lower() == b"origin" for key, _ in headers):
                raise GatewayError("FORBIDDEN", 403)
            if self.active >= self.settings.max_connections:
                raise GatewayError("GATEWAY_BUSY", 503)
            self.active += 1
            admitted = True
            if not (scope["path"] == "/api/v1/health" and scope["method"] == "GET"):
                principal = self.store.authenticate(headers)
                scope.setdefault("state", {})["principal"] = principal
            lengths = [value for key, value in headers if key.lower() == b"content-length"]
            try:
                if len(lengths) > 1 or (lengths and (int(lengths[0]) < 0 or int(lengths[0]) > self.settings.max_body_bytes)):
                    raise GatewayError("REQUEST_TOO_LARGE", 413)
            except ValueError:
                raise GatewayError("INVALID_REQUEST", 422) from None
            body = bytearray()
            async with asyncio.timeout(self.settings.body_timeout):
                while True:
                    message = await receive()
                    if message["type"] == "http.disconnect":
                        return
                    if message["type"] != "http.request":
                        raise GatewayError("INVALID_REQUEST", 422)
                    chunk = message.get("body", b"")
                    if len(body) + len(chunk) > self.settings.max_body_bytes:
                        raise GatewayError("REQUEST_TOO_LARGE", 413)
                    body.extend(chunk)
                    if not message.get("more_body", False):
                        break
            if scope["method"] == "POST":
                types = [value for key, value in headers if key.lower() == b"content-type"]
                if len(types) != 1 or types[0].split(b";", 1)[0].strip().lower() != b"application/json":
                    raise GatewayError("INVALID_REQUEST", 422)
            elif body:
                raise GatewayError("INVALID_REQUEST", 422)
            scope.setdefault("state", {})["bounded_body"] = bytes(body)

            async def replay():
                return {"type": "http.request", "body": bytes(body), "more_body": False}

            await self.app(scope, replay, safe_send)
        except GatewayError as error:
            if not started:
                await error_response(error.code, error.status)(scope, receive, safe_send)
        except TimeoutError:
            if not started:
                await error_response("COMMAND_TIMEOUT", 504)(scope, receive, safe_send)
        except Exception:
            if not started:
                await error_response("INTERNAL_ERROR", 500)(scope, receive, safe_send)
        finally:
            if admitted:
                self.active -= 1


def create_app(settings=None, *, client=None, store=None):
    settings = settings or GatewaySettings.load()
    client = client or IpcClient(settings)
    store = store or CredentialStore(settings.credential_directory)
    app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)
    app.router.redirect_slashes = False
    app.add_middleware(LocalBoundary, settings=settings, store=store)

    @app.exception_handler(GatewayError)
    async def gateway_error(request, error):
        return error_response(error.code, error.status)

    @app.exception_handler(RequestValidationError)
    async def validation_error(request, error):
        return error_response("INVALID_REQUEST", 422)

    @app.exception_handler(HTTPException)
    async def http_error(request, error):
        return error_response("NOT_FOUND" if error.status_code == 404 else "INVALID_REQUEST", error.status_code)

    async def forward(request, action, permission, payload=None):
        principal = request.state.principal
        principal.authorize(permission, (payload or {}).get("parameters"))
        return await asyncio.to_thread(client.request, action, principal.principal_id, payload)

    def parse(request, schema):
        try:
            return schema.model_validate(decode_json(request.state.bounded_body))
        except (ValidationError, ValueError, TypeError):
            raise GatewayError("INVALID_REQUEST", 422) from None

    async def submit(request, payload):
        receipt = await forward(request, "SUBMIT", payload["command_type"], payload)
        status = (broker_status(receipt.get("error_code")) if receipt["state"] == "REJECTED"
                  else 202 if receipt["state"] in {"PENDING", "RUNNING", "CANCEL_REQUESTED"} else 200)
        return JSONResponse({"api_version": API_VERSION, "command": receipt}, status_code=status)

    @app.get("/api/v1/health")
    async def health():
        return {"api_version": API_VERSION, "gateway_state": "OK", "terminal_checked": False}

    @app.get("/api/v1/device/status")
    async def status(request: Request):
        return {"api_version": API_VERSION, "terminal": await forward(request, "STATUS", "GET_STATUS")}

    @app.get("/api/v1/device/capabilities")
    async def capabilities(request: Request):
        return {"api_version": API_VERSION, "gateway_authentication": "LOCAL_BEARER",
                "terminal": await forward(request, "CAPABILITIES", "GET_CAPABILITIES")}

    @app.post("/api/v1/commands")
    async def commands(request: Request):
        return await submit(request, parse(request, CommandSubmission).model_dump())

    @app.get("/api/v1/commands/{request_id}")
    async def operation(request_id: str, request: Request):
        if not public_id(request_id):
            raise GatewayError("INVALID_REQUEST", 422)
        return {"api_version": API_VERSION, "command": await forward(
            request, "OPERATION", "GET_STATUS", {"request_id": request_id})}

    @app.post("/api/v1/commands/{request_id}/cancel")
    async def cancel(request_id: str, request: Request):
        if not public_id(request_id):
            raise GatewayError("INVALID_REQUEST", 422)
        cancellation = parse(request, CancellationSubmission)
        return await submit(request, {"request_id": cancellation.request_id, "command_type": "CANCEL_OPERATION",
                                      "parameters": {"target_request_id": request_id}})

    return app
