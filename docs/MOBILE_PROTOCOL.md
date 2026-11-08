# Proposed mobile protocol 1.0 — DESIGN ONLY

All messages, transports, commands, security exchanges and limits in this document
are **PLANNED**. Phase 0 implements no parser, broker, BLE service, HTTP endpoint,
WebSocket, pairing, authentication or command dispatch. Capability names do not
advertise current mobile support. See [architecture](MOBILE_ARCHITECTURE.md).

## Transport responsibilities

| Future transport | Responsibilities | Restrictions |
| --- | --- | --- |
| BLE | Nearby discovery, secure association, capability summary, short commands, ACKs, connection status and small events | No documents/images or unbounded result text. Negotiate MTU, explicit framing/reassembly, message length, timeout, flow control and authenticated session before use |
| Local Wi-Fi | Authenticated API requests, document/PDF/image transfer, larger synchronization payloads and WebSocket events | TLS and authenticated sessions even on a private LAN; no unauthenticated discovery-to-command shortcut. Bulk transfer requires separate size/type/quota/digest checks |

Supported local operations must work without public internet. BLE presence or a
shared Wi-Fi network is not authorization. BLE bonding alone is insufficient
application authentication. Large results available over Wi-Fi may have only
status on BLE; failover cannot silently leak them or force Pi cloud processing.
Specific GATT UUIDs, endpoint paths, certificate provisioning, BLE cryptographic
handshake and upload framing remain later design decisions requiring review.

## Envelope and field schema

Use UTF-8 JSON objects with strict types and bounded nesting. The following table
is the normative proposed schema; no executable schema is added in Phase 0.

| Field | Proposed type and rule |
| --- | --- |
| `protocol_version` | Required string `"1.0"`; major/minor semantics below |
| `request_id` | Required UUID string, generated per new request. Responses/events about an operation repeat its ID. A PAIR exchange also gets an ID |
| `device_id` | Required opaque stable sender ID established by authenticated association, never an IMEI, serial port path, API key or a trusted self-assertion |
| `message_type` | Required enum `PAIR`, `CAPABILITY`, `STATUS`, `REQUEST`, `ACK`, `RESULT`, `ERROR`, `CANCEL` |
| `command` | Required field: allow-listed string for REQUEST; echoed for operation responses; otherwise null. No module/function names, shell code or arbitrary host paths |
| `parameters` | Required bounded object, empty when unused; validated against the message-specific fields below |
| `timestamp` | Required RFC 3339 UTC string. Diagnostic ordering/freshness hint; never the sole replay defense or authoritative deadline clock |
| `status` | Required enum `proposed`, `ready`, `idle`, `busy`, `accepted`, `running`, `cancelling`, `succeeded`, `failed`, `cancelled`, `rejected`, `unknown`, as allowed by message type |
| `error` | Required null or `{ "code": string, "message": string, "retryable": boolean }`; sanitized human message, no stack trace/content/credentials |
| `session_id` | Required for associated traffic; unpredictable handshake-bound session ID; null only for pre-auth PAIR |
| `sequence` | Required nonnegative session-scoped integer with authenticated integrity and replay window; PAIR starts at 0 and uses fresh nonces/proof |

After authentication, transport/session identity must agree with `device_id`.
All security-relevant fields are integrity-protected. A forwarding gateway must
preserve authenticated phone principal separately from its own Pi identity.
Receiving Pi identity is bound to the channel/session; a broker API must validate
that the association targets this Pi. No caller-supplied target can select a
different host or hardware resource.

Initial proposed control-message cap is 4,096 encoded bytes; result/event cap
16 KiB over Wi-Fi, with negotiated smaller BLE limits. Larger content uses a
separately authorized transfer reference, not unbounded JSON or a host pathname.
Parameters have at most four nested levels; reject duplicate JSON keys,
NaN/Infinity, invalid encoding, oversized fields and trailing non-JSON payloads.
These limits are design defaults requiring device/transport testing.

## Message-specific payloads

All fields below are members of `parameters`. Reject unknown command parameters;
negotiate extension fields explicitly rather than silently ignoring them.

| Type | Parameters / allowed status | Authorization and outcome |
| --- | --- | --- |
| `PAIR` | `stage` enum (`init`, `challenge`, `proof`, `complete`, `revoke`), fresh `nonce`, handshake-specific opaque proof/public-key fields; `proposed`/`ready` | Only bounded association exchange before authentication; explicit physical-user approval required. The final reviewed crypto protocol must specify exact stage schemas. No feature request accepted during this exchange; revocation requires authenticated authority/local recovery |
| `CAPABILITY` | `modes` list of `{id, enabled, available, reason_code}`, `transports`, `supported_versions`, `operating_state`, `privacy_constraints`, `limits`, `capability_revision`; `ready` | Authenticated read scope. Compute on Pi using profile/installed dependencies, separate implementation from availability. Must not reveal keys, paths or private documents. Future phone service grants listed separately |
| `STATUS` | `operating_state`, `terminal_state` enum (`idle`, `busy`, `stopping`, `unavailable`), `active_request_id` or null, `operation_state` when queried, `event_sequence`, `resource_state`; `idle`/`busy`/`running`/`cancelling`/`unknown` | Authenticated read scope; operation details only to permitted principal. No raw transcript/result content by default |
| `REQUEST` | Per-command schema below; `proposed` | Validate authentication, permission, profile, capability revision, policy, resources, identity and bounds before admission |
| `ACK` | `ack_scope` enum (`transport`, `broker`), `received_type`; `accepted` or `rejected` | Transport ACK confirms validated receipt only. Broker ACK means request admitted and tracked, not successful execution |
| `RESULT` | `outcome` bounded structured object or authorized expiring transfer reference; optional `source`/`partial` flags; `succeeded` or `cancelled` | Exactly one terminal operation outcome. Remote result disclosure needs separate permission/policy even if a phone initiated the task. Cancellation has no fabricated result |
| `ERROR` | `received_type`, optional `operation_state`; `failed` for admitted task failure, `rejected` for non-admission | Non-null `error`. Unauthorized callers receive minimal errors without learning device state. Failure cannot imply that all resources have been released |
| `CANCEL` | `target_request_id` UUID, short allow-listed `reason`; `proposed` | Its own fresh envelope request ID. Only current owner/authorized local control can cancel. Idempotent; final target status still required |

Proposed initial command vocabulary for later implementation, **not active**:

| Command | Required parameters | Constraints |
| --- | --- | --- |
| `GET_CAPABILITIES` | `{}` | Returns CAPABILITY; no dynamic imports or hardware opening |
| `GET_STATUS` | Optional `target_request_id` UUID | Returns STATUS; unknown/expired target is `unknown`, not proof of failure |
| `RUN_MODE` | `mode` single-character enum `1`–`9`, `capability_revision` string, `processing_policy` enum `automatic_public`/`private_local`, `result_delivery` enum `terminal_only`/`phone_if_permitted` | Existing profile still governs. Phone cannot force-enable GPS/navigation, change provider order or bypass physical output choice. Until all interactive steps have safe adapters, advertise these mode commands unavailable |

Additional semantic parameters, remote text inputs, file ingestion, shutdown,
configuration changes, phone services and arbitrary feature commands are **not**
part of this initial allow-list. In particular, `RUN_MODE` alone cannot answer
the existing blocking voice/Morse/output prompts; defining an interactive-session
adapter and permissions is later work. Pairing does not grant `RUN_MODE` access.

Example **illustration only**, not an endpoint or working request:

```json
{
  "protocol_version": "1.0",
  "request_id": "c6446539-9ad9-478c-8ec8-2345ac71604b",
  "device_id": "associated-phone-example",
  "message_type": "REQUEST",
  "command": "RUN_MODE",
  "parameters": {
    "mode": "1",
    "capability_revision": "example-revision",
    "processing_policy": "automatic_public",
    "result_delivery": "terminal_only"
  },
  "timestamp": "2026-11-08T10:00:00Z",
  "status": "proposed",
  "error": null,
  "session_id": "example-session-placeholder",
  "sequence": 1
}
```

## Admission, execution and cancellation

Proposed operation lifecycle:

```text
validated receipt → transport ACK
                    |
              broker admission
               /           \
          rejected       broker ACK accepted → running → succeeded / failed
                                               |
                                           cancelling → cancelled
```

REQUEST receipt, admission, running, result delivery and resource release are
different events. The broker is the sole execution admission authority. An
accepted request is tracked before invoking terminal execution. Reject a new
conflicting request as BUSY; do not queue unbounded physical-resource work.
Physical stop/cancel has priority and must use the current terminal input owner.
Read-only status and cancel remain serviceable while a long task runs.

Cancellation acknowledgement means cancellation requested, not that a native
model/network call has stopped. Mark `cancelled` only after late outputs are
suppressed and a safe resource state established. If abandoned work persists,
retain a busy/unavailable resource indication and reject conflicting work until
safe reuse. Existing `run_with_feedback()` bounds workers but is not a general
hard-kill solution. Do not wait behind the blocked menu to acknowledge cancel.

## Failure, retries, reconnection and failover

| Condition | Proposed handling |
| --- | --- |
| Unknown type / unsupported command | Reject `UNKNOWN_MESSAGE_TYPE` / `UNSUPPORTED_COMMAND`; no fallback execution |
| Invalid or excessive input | `INVALID_INPUT` / `PAYLOAD_TOO_LARGE`; bounded parsing before hardware or file access |
| Missing/invalid authentication | `AUTH_REQUIRED` / `AUTH_FAILED`, rate limit, no task/status disclosure; never downgrade to insecure transport |
| Authenticated but unauthorized action | `PERMISSION_DENIED`; gateway and broker both enforce scope; phone OS grants remain separate |
| Disabled/unavailable mode or stale capability revision | `CAPABILITY_UNAVAILABLE` / `CAPABILITY_CHANGED`; refresh capabilities, no automatic retry into a different mode |
| Busy terminal | `BUSY`, current permissible status only; client retains intent for explicit retry rather than auto-starting later |
| Transport receipt timeout | Query status using the same request ID before deciding to retry. Proposed ACK target 3 s; not a measured latency guarantee |
| Operation timeout | `TIMEOUT`; per-command monotonic deadline distinct from ACK timeout. Do not infer failure merely from a disconnected phone |
| Duplicate request | Key by authenticated principal + Pi identity + request ID across BLE/Wi-Fi. Same normalized command/payload returns existing state or permitted cached outcome without executing twice. Different payload under same ID gives `REQUEST_ID_CONFLICT` |
| Reconnection | Authenticate/resume securely, exchange current capability revision, active IDs and last event sequence; query status for unresolved tasks. Expired result is `unknown`/unavailable; never automatically replay side effects |
| Version mismatch | `PROTOCOL_MISMATCH` with supported versions after permitted authentication; incompatible major rejected before admission. Minor extension requires negotiated support |
| BLE/Wi-Fi failover | Reauthenticate/bind the new channel to the same association, preserve request ID and operation ownership, get current status, deduplicate centrally; never execute a second copy or reroute confidential content |
| Gateway/Pi restart | New session ID invalidates old session sequence space. If execution history is unavailable, return `unknown`; require reconciliation/user decision before a new ID can repeat a potentially completed operation |
| Resource or output failure | Sanitized `RESOURCE_UNAVAILABLE` / `OUTPUT_UNAVAILABLE`; no public playback fallback for private content. Phone result delivery cannot silently substitute for selected terminal output |

Deduplication needs a bounded metadata ledger independent of transport. Proposed
retention is the active lifetime plus ten minutes of completed request metadata;
advertise actual retention in CAPABILITY. Persist no PRIVATE text/audio/results
for deduplication; metadata must be minimized and separately reviewed. Without
durable execution history, exactly-once behavior across process/device restarts
is **not guaranteed**. No restart may transform uncertain status into success.
Timestamp clock skew is handled during authenticated session establishment;
nonce/session/sequence integrity plus operation IDs provide replay resistance.

## Security and permission requirements

- Authenticate association with on-device user approval and an established,
  reviewed challenge/proof design; protect against nearby impersonation, replay,
  unauthorized pairing and downgrade. Never transmit long-lived secrets in
  discovery advertisements, QR logs or plain JSON examples.
- Use TLS with authenticated Pi identity for LAN APIs/events and application
  authentication over BLE. Bootstrap trust during approved association; do not
  disable certificate validation for local addresses. Document revocation,
  phone loss, credential rotation and local recovery before enabling pairing.
- Keep phone credentials in Android Keystore-backed storage and Pi credentials
  in owner-restricted storage. No credentials in repository, APK resources,
  ordinary preferences, debug dumps or runtime logs.
- Separate scopes for status, mode control, remote result access, upload,
  notification/location access and emergency communication. Deny by default;
  validate both app-level authority and phone OS permission.
- Carry immutable processing policy into execution, worker threads, events,
  staging, result caches and speech. PRIVATE content must not be exported merely
  because pairing is authenticated; explicitly define any future permission.
- Bound clients, requests, frame reassembly, transfers and storage. Upload staging
  must confine paths and check size, type and content digest; PDF conversion is
  PLANNED and absent from current `RAGPipeline.index_file()`.
- Use sanitized codes/counts for diagnostics. No private transcripts, documents,
  request bodies or credentials in telemetry. Source prompts are untrusted data.

All security properties require later threat review and negative tests. No
service is listening, and no security property is claimed implemented here.
