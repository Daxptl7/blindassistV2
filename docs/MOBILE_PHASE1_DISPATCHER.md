# Phase 1: internal dispatcher and input arbitration

Implemented 8 November 2026 in the existing checkout whose verified origin is
`https://github.com/Daxptl7/blindassistV2.git` (repository ID 1450023102).
The attachment named `Daxptl7/blindterminalv2`, which returned 404 via both public
and authenticated metadata checks. The user explicitly authorized this existing
`blindassistV2` checkout. No remote, repository location or V1 checkout was changed.
Starting commit: `5a8d8252297dce2cc8f2b197090eb9dc40bbc25d`.

This implements **internal Phase 1 only**. There is no BLE, Wi-Fi, HTTP, WebSocket,
Android remote control, pairing, authentication, document sync or new AI service.
Phase 0 documents remain historical design/baseline snapshots; this document
describes the implemented internal layer. Their proposed wire protocol is not
an active endpoint or the same schema as these Python command objects.

## Existing V2 components and preserved ownership

The audited paths match V2's actual checkout: `main.py` orchestrates the nine
entries in `MODE_MAP`; `_morse_serial_singleton` owns Pico USB serial and is shared
with voice. Mode handlers, modules, services, firmware, settings examples,
deployment/startup commands, models/vector data and Android files are unchanged.
All original `mode_*` function ASTs match the starting commit. See
[the Phase 0 audit](MOBILE_PHASE0_AUDIT.md) for per-mode dependency limitations.

The original `run_mode()` body is preserved as `_run_mode()` with one additional
failure flag. Its profile check, nested `session_active()` handling,
`processing_session(PUBLIC)`, safe failure speech and private-recording cleanup
remain in place. The `run_mode()` wrapper enforces the designated execution thread,
tracks nesting and routes top-level physical requests through admission. Nested
gesture actions retain the same top-level operation/session; they do not acquire
a second mode slot or deadlock on a non-reentrant mode lock.

## Broker modules and execution path

| Component | Implemented responsibility |
| --- | --- |
| `gateway/command_models.py` | Frozen typed commands, validated IDs/enums/exact parameter keys, detached/frozen input parameters, capability and receipt types |
| `gateway/operation_state.py` | Explicit lifecycle transitions; terminal request states cannot be overwritten |
| `gateway/command_broker.py` | Lock-protected submission, bounded admission/history, duplicate protection, status/capabilities, cancellation intent and shutdown; never executes a handler |
| `gateway/input_arbiter.py` | Pure persistent Morse-menu state fed events by main; no serial connection, queue reader or worker |
| `main.py` integration | Initializes broker after existing startup gates; arbitrates physical menu/input and pending internal requests; invokes existing runner on the owner thread; closes broker during existing shutdown |

```text
existing main startup / hardware initialization
  → optional internal broker initialization
  → existing input owner reads menu events
  → physical digit or admitted internal START_MODE
  → designated execution thread calls run_mode()
  → existing _run_mode(), MODE_MAP handler and privacy/session infrastructure
  → metadata-only lifecycle completion/failure
  → return to menu
```

Request submitters may run in other threads to query or enqueue internal test
requests. They cannot call `take_next()`, `finish()`, update capabilities, consume
cancellation signals, or invoke `run_mode()` as the execution owner. No mode
worker threads, second serial reader, microphone/camera owner or TTS manager were
introduced. `owns_active_request()` rejects a forged/different execution lease.

## Internal command contract

`CommandRequest(request_id, command_type, source, parameters={})` requires enum
instances, not arbitrary command/function strings. IDs are 1–96 characters,
matching `[A-Za-z0-9][A-Za-z0-9._:-]*`. Parameters are copied and exposed read-only.
No transcript, document, policy override, module/function name or shell payload
is accepted. Source is `PHYSICAL_INPUT` or `FUTURE_MOBILE_REQUEST`; these labels
are **not authentication**.

| CommandType | Parameters | Behavior |
| --- | --- | --- |
| `GET_STATUS` | `{}` | Completes with sanitized metadata snapshot; direct `get_status()` gives a fresh snapshot without a retained control request |
| `GET_CAPABILITIES` | `{}` | Completes with current capability snapshot; direct `get_capabilities()` also available |
| `START_MODE` | `{"mode": "1"}` (actual single-character registry entry) | PENDING after admission; only owner can claim RUNNING. Disabled/unknown modes rejected; current settings rechecked before execution |
| `CANCEL_OPERATION` | `{"target_request_id": "..."}` | Cancels unstarted pending mode; running-mode requests obey advertised cancellation support |

`CommandValidationError.code` reports malformed typed inputs without echoing
payloads. `CommandReceipt` contains request ID, state, safe error code, mode and
detached metadata. No mode return value or exception text is copied into it.

## Lifecycles and bounded history

Request states: IDLE, PENDING, RUNNING, COMPLETED, FAILED, CANCEL_REQUESTED,
CANCELLED and REJECTED. New records begin PENDING; the validator also permits
IDLE → PENDING for lifecycle callers. Required transitions are:

```text
PENDING → RUNNING / REJECTED / CANCELLED
RUNNING → COMPLETED / FAILED / CANCEL_REQUESTED
CANCEL_REQUESTED → CANCELLED / COMPLETED / FAILED
```

Terminal-wide status is separate: IDLE, BUSY, SHUTTING_DOWN or CLOSED. Admission
does not mean completion. COMPLETED for a mode means its synchronous handler
returned normally, including a valid `None`; it is not proof of OCR quality,
provider success, physical playback or user-task completion. A swallowed
feature-level failure cannot be inferred from its return value. Uncaught runner
failures become FAILED with `MODE_EXECUTION_FAILED`; private text is not retained.

Defaults: four pending mode requests, 128 total retained records, 15-second
pending deadline, 300-second retention **after** terminal state. Expiry uses
`time.monotonic()` and is swept on submission/status/claim/work waits. The live
menu checks at bounded blocking intervals, including during partial entry. No
request waits behind an active interactive mode: competing pending requests are
rejected when a mode is claimed; new requests while busy are rejected immediately.

An identical retained ID/source/type/parameters returns the existing record.
Changed content/source with that ID returns `REQUEST_ID_CONFLICT` without
overwriting it. Unexpired history is never evicted just to admit another request;
new records fail with `HISTORY_FULL`. The guarantee is at-most-once **within this
process and retention window**, not across expiry, broker replacement or crashes.
No persistent request database is created.

## Physical-first arbitration and compatibility

The original fallback still calls `MorseSerial.read_menu_digit(timeout=120)`.
When the broker is initialized, `_cooperative_menu_choice()` keeps one
`InputArbiter` alive for the entire menu invocation. Main alone reads
`serial.get_message()`, with a blocking 100 ms first read and bounded draining of
already-arrived events before considering internal work. Partial digits survive
poll boundaries; no repeated short `read_menu_digit()` calls are used.

- Five RAW dot/dash presses select the same digits 0–9. Configured menu gap is
  clamped to 2–30 seconds, default five; a pause longer than the gap clears the
  partial command. Exact boundary behavior and interleaved LETTER events are tested.
- READY clears partial symbols; BACKSPACE edits; raw-event precedence and
  LETTER-only legacy firmware remain supported. Button 3 followups alone do not
  select a menu mode. Firmware and physical mappings are unchanged.
- A completed physical digit wins over queued simulated work. An in-progress
  digit holds its input priority until completion/edit/reset/gap expiry. A
  physical selection can displace queued mobile work with `PHYSICAL_PRIORITY`.
- TTY input uses `select()` on the same stdin owner and preserves the existing
  keyboard helper. Complete ready lines have priority. Unsubmitted characters
  hidden by canonical TTY buffering are not observable; no keyboard raw-mode
  manipulation or promise of partial-TTY-line priority is made.
- Digit 0 still uses the existing five-second double-press confirmation or TTY
  confirmation. The broker cannot request shutdown. During confirmation it does
  not execute modes; confirmed shutdown cancels pending broker work.
- Active mode input ownership is unchanged. Voice recording stop counts,
  translation triple-click exit, gesture/object stops and audio prompts all run
  inside the existing handlers. The menu never consumes serial while they run.

Single-active-mode admission covers MODE_EXECUTION, CAMERA, MICROPHONE, PICO_INPUT
and AUDIO_OUTPUT conservatively. It does not create individual hardware probes or
resource managers. Legacy asynchronous TTS/provider work may outlive a handler;
their existing routing, queues, deadlines and locks remain authoritative. This
phase does not certify physical cleanup or forcibly kill native/model calls.

## Cancellation, privacy and failure isolation

Pending requests can be cancelled before execution and become CANCELLED. Current
V2 mode capabilities all advertise `cancellation_supported=False`: they have
mode-specific physical stops, not a common broker-safe whole-mode cancellation
adapter. An active `CANCEL_OPERATION` therefore returns
`CANCELLATION_UNSUPPORTED`, leaving the operation RUNNING. It never injects button
events, ends a recording as a substitute for cancelling a mode, or claims success.

The broker state machine supports a cooperative adapter's CANCEL_REQUESTED/event
and owner-confirmed CANCELLED, demonstrated only with test doubles. No actual
mode adapter was invented. A cancellation request may instead finish COMPLETED
or FAILED. Closing the broker cancels pending work, signals active cancellation
intent and keeps availability SHUTTING_DOWN until the owner settles execution.

No policy field is granted by admission. Existing PUBLIC entry and nested PRIVATE
processing contexts, allow_cloud/allow_persistence flags, result output choices,
TTS routing and storage restrictions remain intact. Earphones still do not imply
private processing. Generic broker records never contain sensitive handler results,
transcripts, document text or exception messages. Status logs do not echo payloads.

Initialization failure retains the original standalone menu. Runtime admission
failure disables/closes the optional broker; a partial physical digit already
being entered is preserved by that menu's existing arbiter. Physical history
exhaustion also disables the optional layer and retains physical operation rather
than evicting protected IDs. Failures after a handler ran never replay it.
Existing strict configuration, input-device and release-preflight gates remain.

See [test results](MOBILE_PHASE1_TEST_RESULTS.md) for actual outcomes and
[the Phase 2 handoff](MOBILE_PHASE1_HANDOFF.md) for remaining boundaries.
