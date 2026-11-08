# Phase 0 → Phase 1 handoff

Prepared 8 November 2026. Phase 0 is a repository audit, design contracts, gateway
README and blank Android source project only. **All interfaces/files/changes
proposed below are PLANNED. No dispatcher or mobile connection is implemented.**

Read [the audit](MOBILE_PHASE0_AUDIT.md),
[architecture/capabilities](MOBILE_ARCHITECTURE.md),
[protocol](MOBILE_PROTOCOL.md) and
[validation baseline](MOBILE_PHASE0_TEST_BASELINE.md) before Phase 1 work.
Terminal source baseline is `0a4666ffe880a6cfb1d0d734459cea5035a3fc28`.

## Verified constraints to preserve

- `main.py` is the execution owner: `_safe_import()` fills `_modules`,
  `MODE_MAP` selects all nine handlers, `run_mode()` enforces `enabled_modes`
  and processing context. No feature module, gateway or Android callback may
  become a second execution authority.
- `_morse_serial_singleton` owns the Pico USB connection. Voice gets that handle
  through `set_morse_serial()`. Translation wraps the same handle, and active
  mode watchers consume events from the existing queue. Queue reads consume
  events; they are not broadcast subscriptions. Do not add another port reader
  or let gateway/status polling consume that queue.
- `_get_menu_choice()` blocks on a 120-second menu-digit read or TTY `input()`.
  `_select_with_buttons()` speaks before its button-response window. Modes also
  block for input, model loads, OCR/network work, recording and output selection.
  Calling a broker only after menu input will not give timely mobile control.
- Existing `main()` rejects startup without strict configuration and Pico/TTY
  input, and may run device preflight. A phone connection currently cannot make
  a terminal with no physical/TTY input start. Preserve standalone behavior;
  defer any proposed mobile-only boot change to separately scoped work.
- Mode 5 ends gesture camera use before nested `run_mode()` for a selected
  action. Nested execution inherits the active processing session. A simple
  non-reentrant lock around every `run_mode()` call could deadlock this path.
- Public completed-result output choice happens **after** processing. Button 1
  earphones / Button 2 speaker is independent of `ProcessingPolicy`. Internal
  PRIVATE policy prohibits cloud/persistence and requires verified private audio;
  ordinary terminal UI modes enter PUBLIC. Do not advertise earphones as local-only.
- Default enabled modes omit 7, and navigation is additionally disabled. No
  mobile capability may override those restrictions. GPS is a gated location/
  route-summary implementation, not validated live pedestrian guidance.
- Existing source/model indexes remain in place. New state uses configured
  `data_directory()` (default `runtime`) and model-specific vector snapshots;
  current text ingestion accepts `.txt`, `.md`, `.text` up to 5 MiB, not PDFs.

## Recommended dispatcher integration point — documentation only

Introduce an admission boundary in `main()` around mode selection and before
`run_mode()`, owned by the same terminal execution thread. Adapt menu waiting to
permit broker wakeups while retaining partial Morse symbols, deadline behavior,
stale-event draining and physical shutdown confirmation. Do not poll a second
queue consumer on the Pico to make the menu interruptible.

A future transport worker may authenticate and submit a normalized request to
a bounded broker. The broker reports admission/status without invoking modes
from transport threads. The execution owner chooses the next permitted action
and uses `run_mode()`; nested gesture actions stay within the current resource
session. Unsupported interactive mode requests should remain unavailable until
the corresponding input adapter can preserve all physical choices and timeouts.

Separate resource arbitration and cancellation from the network transport.
Evaluate a process boundary for crash isolation: the gateway must be able to
restart without restarting main, importing main, or dropping physical control.
IPC authentication, OS permissions, framing and lifecycle are not settled here.
Phase 1 need not expose a real transport to test the broker with fake clients.

## Proposed broker interface — PLANNED

This is a conceptual contract, not executable Python or an implemented API:

| Interface | Inputs | Expected behavior |
| --- | --- | --- |
| `submit(request, principal)` | Validated request ID, source (`physical`/`mobile`), command, typed parameters, immutable policy, monotonic deadline, permission scope | Recheck profile/capabilities and principal; deduplicate centrally; return admission/rejection. One active conflicting operation, bounded waiting metadata. No direct hardware access |
| `take_next()` | Execution-owner-only call | Return one admitted action after physical-priority arbitration, or wait interruptibly. Only the main execution owner can take/execute |
| `cancel(target_id, principal)` | Bound operation and authorized requester | Signal current session; acknowledge intent promptly through control path independent of task queue. Preserve mode-specific physical stops |
| `status(target_id, principal)` | Optional ID and authorized requester | Sanitized idle/busy/running/cancelling/terminal outcome; resource readiness independent of result availability |
| `publish(outcome)` | Execution-owner outcome, request ID and policy | Exactly one terminal outcome; suppress abandoned/late outputs. Export results only under separate permitted disclosure rules |
| `close()` | Terminal lifecycle | Stop admission, cancel/settle sessions, release gateway/broker resources without blocking or changing existing hardware shutdown |

Use states `accepted → running → succeeded/failed` or `cancelling → cancelled`,
with separate resource-cleanup readiness. The proposed connectivity states are
`STANDALONE_OFFLINE`, `STANDALONE_ONLINE`, `PAIRED_LOCAL`, `PAIRED_ONLINE`;
they neither replace existing `app_mode`/`release_profile` nor choose privacy.
Protocol request IDs survive transport failover; new session IDs prevent replay.
No claim of exactly-once execution across reboot without durable history.

## Shared resources and current cancellation

| Resource/operation | Existing ownership / cancellation | Phase 1 risk and required behavior |
| --- | --- | --- |
| Pico events | One serial reader, active menu/mode queue consumer; main/voice watchers and TranslationButtons | No duplicate consumption, stale choice or remapping. A priority cancellation path must coordinate with the current mode, not steal events |
| Camera | OCR CameraManager or gesture/object capture; gesture releases before nested mode | Camera index settings are not a lock. Reject concurrent owners and prove release on cancel/error before next request |
| Microphone | Ordinary voice uses arecord; live translation uses sounddevice input | Recording stop is not necessarily mode cancel. Avoid overlap, drain TTS before voice, preserve Enter and backstop behavior |
| TTS / audio | Lazy singleton queue with per-utterance device/policy; stop/flush APIs; live stream separate | No gateway playback queue. Coordinate live output and normal TTS; never reroute private content publicly after failure |
| OCR / AI work | `run_with_feedback()` polls stop, deadline and two-slot semaphore; models can remain running after caller cancels | Cancellation must suppress late results, preserve context and track pending resource work; do not claim hard interruption or admit conflicting work early |
| Voice mode | Three Button 3 presses finish recording; Button 1 interrupts answer for follow-up | Preserve four-second inter-press rule, spoken recording cues, conversation context and fresh output choices |
| Translation | Triple Button 3 within five seconds exits menus/capture/work/speech/live; resolved single/double actions delayed | Retain TranslationButtons as active consumer. Do not replace with ordinary voice stop counting. TTY `333` menu exit remains |
| Gesture / object loops | Gesture Button 3/fist leaves; object Button 3/Enter/120-second default stops | Preserve callbacks, stop events, camera finally cleanup and gesture nested execution |
| GPS / local math | Synchronous calls; no universal cooperative cancellation adapter | Advertise limitations honestly and design bounded cancellation before accepting remote jobs that need it |

## Privacy and result handling requirements

Create policy before capture/transcription/ingestion; never infer it from the
selected audio endpoint or connectivity state. Keep it through `session_thread`
and queued utterances. A transport/broker should not pass arbitrary caller-created
policy objects directly to hardware; validate requested policy against granted
scope and Pi availability. Refuse unfulfillable private operations, never retry
them publicly.

PRIVATE data must not enter cloud APIs, RAG persistence, translation caches,
logs, phone event feeds or deduplication/result caches without a separately
defined, permitted policy. Existing private voice recordings are temporary files,
not a memory-only storage guarantee. Ensure cleanup for errors/disconnect/shutdown
and evaluate OS encryption/retention separately. Phone result presentation is
distinct from terminal earphone playback and needs explicit disclosure authority.

## Suggested new files for a later Phase 1

These paths are proposals only; create none as part of Phase 0:

- `gateway/protocol.py`: pure data validation, no main/hardware imports.
- `gateway/command_broker.py`: admission, identity/deduplication and status,
  with execution-owner interface and no transport-specific feature execution.
- `gateway/terminal_session.py`: resource/cancellation context, only if needed
  after choosing in-process versus IPC execution boundary.
- `tests/test_mobile_protocol.py`, `tests/test_mobile_broker.py`,
  `tests/test_mobile_orchestrator.py`: synthetic principal/transport/resource
  tests that do not open physical devices.

Any future edits to `main.py` must be a separately authorized, narrowly reviewed
Phase 1 integration. No move of modules/services, second serial reader, firmware,
provider-policy, index/model, deployment service or startup-command change follows
automatically from this document. Active BLE/Wi-Fi requires its own later scope.

## Required Phase 1 regression and acceptance work

1. Preserve this phase's honest baseline: ordinary discovery currently hangs on
   one pygame mock, and the supplementary suite has existing failures. Do not
   replace that record with a green isolated broker test. Reconcile those issues
   in separately scoped work before claiming a clean regression/release gate.
2. Run existing install-layout, installer syntax/check, dependency consistency
   and complete applicable regression workflows. Compare exact failures and
   skipped tests, not only totals; do not install/upgrade dependencies silently.
3. Test physical-only startup/use with gateway absent, gateway crash/restart,
   phone loss/reconnect, internet loss and local-only operation with provisioned
   fakes first, then the configured Pi and explicit hardware permission.
4. Exercise every mode's actual blocking stages, physical cancel mapping,
   timeout, input disconnect and cleanup. Prove one Pico reader/consumer owner,
   one camera/mic session, nested gesture dispatch and no late playback.
5. Reject unauthenticated/unauthorized/oversized/unknown requests, disabled GPS,
   stale capabilities, duplicate/conflicting IDs, busy admissions and replay;
   test identical request IDs across fake BLE/Wi-Fi/reconnection.
6. Instrument private capture → processing → speech/result/log/storage sinks,
   context inheritance and result-disclosure permissions. Unplug earphone
   before/during playback on real Pi; no public fallback may receive content.
7. Confirm existing snapshots/models/source archives remain unchanged except
   explicitly authorized test fixtures in temporary directories. Test failed
   and interrupted ingestion before extending document adapters.
8. Build the Android scaffold with its real `./gradlew :app:assembleDebug` after
   SDK provisioning; add TalkBack, large-font, square-button and en/hi/gu checks
   when screens exist. A source/XML check is not an Android build.

## Readiness decision

The execution boundaries and design contracts provide a concrete starting point
for a separately requested Phase 1. There is no authorization here to begin it.
Hardware release readiness, Android APK build and clean terminal regression/
dependency gates are **not established**. Resolve the baseline hang/failures and
validate the configured Pi as appropriate before presenting an integration as
regression-clean or device-ready. Phase 0 makes no runtime repair to hide those
conditions.
