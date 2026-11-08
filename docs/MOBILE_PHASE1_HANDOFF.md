# Phase 1 → Phase 2 handoff

8 November 2026. Internal dispatcher implemented in the user-confirmed
`Daxptl7/blindassistV2` checkout, starting at
`5a8d8252297dce2cc8f2b197090eb9dc40bbc25d`.
All transports/authentication/phone behavior below remain **PLANNED**.
No Phase 2 implementation or network listener was added.

Read [the implemented dispatcher](MOBILE_PHASE1_DISPATCHER.md) and
[the test report](MOBILE_PHASE1_TEST_RESULTS.md). The Phase 0 architecture/protocol
remain design references rather than implemented pairing/wire contracts.

## Existing integration to use

`main._initialize_command_dispatcher()` initializes `CommandBroker` on the
terminal's designated execution thread after existing configuration, device
preflight and input-device gates. The main loop owns queue consumption and
calls existing mode execution. Future gateway initialization should receive a
broker reference through explicit application wiring; do not import `main.py`
from a server worker, start a second terminal, or initialize its hardware.

The gateway may call `submit()`, `get_status()`, `get_capabilities()` and
`get_operation(request_id)` from a transport thread. It must not call
`take_next()`, `finish()`, `update_capabilities()`, `cancellation_event()` or
`run_mode()`: these belong to the execution owner. The broker contains no mode
handler callbacks and never starts an execution worker.

Example **internal Python use**, not a network request or working mobile feature:

```python
from gateway.command_models import CommandRequest, CommandSource, CommandType

receipt = broker.submit(CommandRequest(
    request_id="associated-client-example:request-001",
    command_type=CommandType.START_MODE,
    source=CommandSource.FUTURE_MOBILE_REQUEST,
    parameters={"mode": "1"},
))
# PENDING is admission, not successful OCR. Main alone claims and invokes it.
status = broker.get_operation(receipt.request_id)
```

## Request and status contract

| Operation | Exact internal parameters | Notes for future adapter |
| --- | --- | --- |
| `GET_STATUS` | `{}` | Receipt caches a detached metadata snapshot. Direct `get_status()` returns current terminal state, active mode/ID, pending count, last START_MODE state and retained count |
| `GET_CAPABILITIES` | `{}` | Modes come from actual MODE_MAP/profile; module import availability is separate from unknown dependency/model/hardware/validation status |
| `START_MODE` | `{"mode": "1"}` | One-character actual registry entry; no prompts or input steps are skipped. No remote text, PDF, arbitrary function, shell or policy parameters |
| `CANCEL_OPERATION` | `{"target_request_id": "..."}` | Can cancel PENDING work. Current active modes advertise cancellation unsupported; physical controls remain the actual running-mode stop interface |

IDs: 1–96 characters, `[A-Za-z0-9][A-Za-z0-9._:-]*`. Command/source fields are
Python enum instances. Typed-construction errors expose `CommandValidationError.code`;
they do not echo input text. Unknown keys are rejected. Receipt fields:
`request_id`, `state`, `error_code`, `mode`, `data` (metadata only).

The internal `START_MODE` vocabulary is not the Phase 0 proposed `RUN_MODE` wire
schema. An eventual versioned adapter must explicitly translate its allow-list,
validate types/bounds and reject everything else. Phase 1 has no protocol version,
session nonce, network credentials or authenticated principal in its model.

## Duplicate, queue and error handling

The broker deduplicates global request IDs plus exact retained request content,
including source. Identical retries return existing state; changed content gives
`REQUEST_ID_CONFLICT`. Defaults: four pending modes, 128 retained requests,
15-second pending deadline, 300-second terminal-state retention. Unexpired records
are not evicted to make capacity; `HISTORY_FULL` rejects new records. No persistent
ledger or cross-restart/expiry exactly-once promise exists.

A future authenticated adapter must namespace IDs by its verified association
inside the length limit, preserve them across approved transport failover, and
authorize every target/status read. The caller's `device_id`/source text is not
trusted namespace or authentication. Never allow a phone to choose
`PHYSICAL_INPUT`. Unauthenticated traffic must not fill the broker's history;
rate limiting and bounded protocol parsing belong before submission.

| Code | Meaning / safe action |
| --- | --- |
| `INVALID_REQUEST_ID`, `INVALID_COMMAND`, `INVALID_SOURCE`, `INVALID_PARAMETERS`, `INVALID_MODE`, `INVALID_TARGET`, `INVALID_REQUEST` | Typed request validation failed; do not execute or echo payloads |
| `UNKNOWN_MODE`, `MODE_DISABLED` | Registry/profile denies requested mode; refresh permitted capabilities, never force-enable GPS/navigation |
| `TERMINAL_BUSY` | Current operation owns execution; no hidden mode queue behind it |
| `QUEUE_FULL`, `HISTORY_FULL` | Bounded capacity exhausted; do not create unlimited new retry IDs |
| `PHYSICAL_PRIORITY` | Pending simulated work displaced by an actual physical selection |
| `REQUEST_TIMEOUT` | Work never started before its monotonic pending deadline |
| `REQUEST_ID_CONFLICT` | Retained ID reused with different content/source |
| `UNKNOWN_OPERATION` | Cancel target absent/expired/not a mode operation |
| `CANCELLATION_UNSUPPORTED` | No safe active-mode cancellation adapter; request is not a successful cancellation |
| `MODE_EXECUTION_FAILED`, `INTERRUPTED` | Owner observed handler failure or shutdown/interrupt; no exception content exposed |
| `BROKER_CLOSED` | Optional internal layer stopped; physical standalone path remains authoritative |

Do not infer business success from COMPLETED/None, physical device readiness from
module imports, cancellation from an ACK, or operation failure from transport
loss. Query current operation state after reconnect. Admission and result content
disclosure are distinct responsibilities; this broker never stores feature results.

## Ownership, privacy and authentication boundaries

- Pi owns Pico, mode registry, camera, microphone, TTS/output choices, processing
  policy and lifecycle. Gateway owns no hardware and consumes no serial events.
- Main menu preserves partial Morse digits and physical priority; active modes
  retain their real prompts/stops. A gateway must not manufacture virtual presses
  or start a second consumer to answer mode prompts remotely.
- Authentication/association, TLS or authenticated BLE, replay protection,
  revocation, device credentials and permission scopes must be designed and tested
  before any endpoint exists. Source enums alone establish none of these.
- Enforce permissions separately for status, mode control, cancellation, result
  disclosure and any later phone services. Public network exposure cannot reuse
  internal `get_status()`/`get_operation()` without filtering by authority.
- Do not grant cloud/persistence permission through dispatcher parameters.
  Explicit private session propagation and result disclosure need a reviewed
  execution-owner adapter if later exposed remotely. Earphones remain an output
  selection after processing, independent of local-only data processing.
- Keep raw requests, transcripts, documents, results, exceptions and credentials
  out of logs and deduplication storage. The broker holds only bounded metadata.
- Gateway loss must not restart main or cancel physical use. If admission fails,
  Phase 1 disables the optional broker and retains physical operation; a future
  gateway must detect CLOSED/unavailable and avoid executing work on its own.

## Required later validation and readiness

All 59 new Phase 1 software tests passed. The final supplementary suite has the
same 11 baseline failures and excludes the same existing pygame hang; `pip check`
still has nine conflicts. Phase 1 is a software foundation, not a clean-device
release or proof of physical operation. See exact commands/results in the report.

Before enabling authenticated communication, keep these gates visible: resolve
the known baseline issues in a separate scope; test adversarial parsing/auth and
cross-transport duplicates; fail gateway/reconnect while a physical mode owns
input; verify busy/cancel races, partial Morse, nested gesture dispatch, profile
restrictions, private sinks and earphone disconnects; validate on the configured
Pi with permitted camera/microphone use. Existing native work may survive caller
cancellation, so do not advertise a universal hard stop without a tested adapter.

Android source remains the Phase 0 blank scaffold. Its SDK build and hardware/
TalkBack checks remain pending. No pairing, phone screen, synchronization,
notification, reminder or navigation extension is implied by this handoff.
Stop here until a separately scoped Phase 2 request.
