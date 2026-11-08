# Phase 2 local API contract — version 1.0

Base URL: `http://127.0.0.1:8765`. Bearer credentials go only in Authorization on
loopback. POST bodies require `application/json`; query strings, Origin headers,
unknown fields and caller-selected source/principal are rejected. No CORS,
Swagger/OpenAPI route, proxy trust, uploads or feature-result endpoint exists.
Responses use `Cache-Control: no-store`. Exactly six routes are defined.

| Method and path | Permission | Response |
| --- | --- | --- |
| GET `/api/v1/health` | Public loopback | `api_version`, `gateway_state: OK`, `terminal_checked: false` |
| GET `/api/v1/device/status` | GET_STATUS | `api_version`, `terminal` live broker metadata |
| GET `/api/v1/device/capabilities` | GET_CAPABILITIES | `api_version`, `gateway_authentication: LOCAL_BEARER`, `terminal` capabilities |
| POST `/api/v1/commands` | Command-specific, mode subset for START_MODE | `api_version`, `command` receipt |
| GET `/api/v1/commands/{request_id}` | GET_STATUS, own namespace | Current receipt or 404 |
| POST `/api/v1/commands/{request_id}/cancel` | CANCEL_OPERATION, own namespace | Cancellation command's receipt |

## Request schemas and tracking

```json
{"request_id":"scan-001","command_type":"START_MODE","parameters":{"mode":"1"}}
```

| command_type | Exact parameters |
| --- | --- |
| GET_STATUS | `{}` |
| GET_CAPABILITIES | `{}` |
| START_MODE | `{"mode":"1"}` — actual registry/profile and credential allowlist apply |
| CANCEL_OPERATION | `{"target_request_id":"scan-001"}` |

The cancel route takes `{"request_id":"cancel-001"}`. Its path identifies the
target; its body supplies a distinct retryable cancellation-command ID.
No remote prompts, virtual presses, privacy overrides or shutdown command exist.

Public IDs: 1–64 ASCII characters matching `[A-Za-z0-9][A-Za-z0-9._-]*`.
Internally: `gw:<16-hex-principal>:<public-id>`, within Phase 1's 96-character
limit. Source is forced to FUTURE_MOBILE_REQUEST. Cancel targets use the same
namespace. Other principals' and physical IDs cannot be queried/cancelled;
device status redacts those IDs. Own IDs are returned in public form.

Identical retained ID/content returns existing state; changed content gives
REQUEST_ID_CONFLICT. Rotation preserves principal identity. Gateway restart
preserves the live terminal ledger. Broker defaults: four pending, 128 retained,
15-second pending timeout, 300-second retention after terminal state. No durable
ledger or guarantee after expiry/terminal restart exists. Never claim crash-safe
exactly-once execution. GET status/capabilities use live snapshots without ledger
entries; submitted GET commands retain a snapshot in their receipt.

## State, errors and cancellation

Receipt: `request_id`, `state`, `error_code`, `mode`, `data` (metadata only).
PENDING/RUNNING/CANCEL_REQUESTED admission receipts return 202. Retained
COMPLETED/FAILED receipts return 200: inspect state/error_code. GET operation
returns 200 for any retained state, including FAILED/REJECTED. Rejected POSTs
use an error status while preserving the receipt.

| HTTP | Codes / meaning |
| --- | --- |
| 401 | UNAUTHORIZED: missing, invalid or duplicate bearer |
| 403 | FORBIDDEN: permission, peer, Host, Origin or query restriction |
| 400/422 | INVALID_REQUEST, UNSUPPORTED_COMMAND/PROTOCOL, UNKNOWN_MODE, MODE_DISABLED |
| 404 | UNKNOWN_OPERATION, NOT_FOUND |
| 409 | REQUEST_ID_CONFLICT, TERMINAL_BUSY, PHYSICAL_PRIORITY, CANCELLATION_UNSUPPORTED |
| 413 | REQUEST_TOO_LARGE, FRAME_TOO_LARGE |
| 500/502 | INTERNAL_ERROR / INVALID_IPC_RESPONSE |
| 503 | TERMINAL_UNAVAILABLE, BROKER_CLOSED, QUEUE_FULL, HISTORY_FULL, GATEWAY_BUSY, CREDENTIAL_UNAVAILABLE; insecure local configuration |
| 504 | COMMAND_TIMEOUT: transport/body deadline; REQUEST_TIMEOUT: pending work never started |

Non-receipt error: `{"api_version":"1.0","error":{"code":"UNAUTHORIZED"}}`.
Uvicorn can reject malformed or overloaded connections before the application's
JSON boundary; clients must also handle ordinary HTTP transport errors.
No response echoes input, secret or exception text. Health 200 implies nothing
about terminal readiness. Capability nulls remain unknown; module import is not
hardware validation. The broker's historical `authentication:
NOT_IMPLEMENTED_INTERNAL_ONLY` field describes Phase 1; the wrapper separately
identifies HTTP LOCAL_BEARER authentication.

Admission is not execution. Only the owner advances RUNNING/finishes handlers.
COMPLETED means the handler returned, not proof of feature accuracy/success.
No private result is stored or transferred. Pending modes can be cancelled;
current active modes advertise remote cancellation unsupported and retain their
physical stops. Cancellation-command COMPLETED must be read with
`data.target_state`; it does not imply that a running target stopped.
Transport timeout/disconnect has ambiguous outcome: query the same ID or retry
that exact ID/content within retention. Do not infer mode failure or silently
generate a fresh ID after transport loss.
