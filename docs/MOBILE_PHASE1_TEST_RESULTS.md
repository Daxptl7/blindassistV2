# Phase 1 test results and preservation record

Recorded 8 November 2026, Asia/Kolkata. **59 new tests pass; the existing baseline
still has 11 failures and a hanging pygame test. No hardware validation is claimed.**

## Repository and environment

| Item | Verified value |
| --- | --- |
| Target authorized by user | Existing `Daxptl7/blindassistV2`, repository ID 1450023102 |
| Origin fetch/push | `https://github.com/Daxptl7/blindassistV2.git`, unchanged |
| Naming discrepancy | Attachment's `Daxptl7/blindterminalv2` returned 404 publicly and with available gh authentication; user explicitly confirmed this checkout |
| Baseline HEAD | `5a8d8252297dce2cc8f2b197090eb9dc40bbc25d` |
| Working directory | `/Users/daxpatel/Desktop/Collage/Reseach/BlindAssist/blindassistv2/blindterminalv2` |
| Branch | New `feature/android-phase1-dispatcher`, based on Phase 0 feature branch; no main-branch edits |
| Initial dirty path | `.vscode/settings.json`; untouched and excluded from commits |
| OS / architecture | macOS 26.0 / Darwin arm64; not a Raspberry Pi |
| Interpreter | Python 3.13.2, `/Library/Frameworks/Python.framework/Versions/3.13/bin/python3` |
| Environment | Existing system Python, no active/check-out .venv; no dependency/environment modifications |
| Local device setup | No `config/settings.json` generated; existing model/data symlinks preserved; no configured test Pi |

Initial inspection ran `pwd`, `git remote -v`, `git status --short`,
`git branch --show-current`, `git log -1 --format='%h %cs %s'`,
`python3 --version` and static source/AST inspection. All mandatory source paths
exist in this V2 checkout. Phase 0's five documents are available. The new gateway
package is hardware-independent; main was not imported merely to inspect it.

Tracked-file content/link fingerprints were recorded before validation for
3,457 paths, including the user's existing editor edit. Baseline and after logs,
supervisors, diagnostic runner and manifests reside under
`/private/tmp/blindassist-phase1-*`; raw logs are not committed.

## Commands and actual results

Python tests used `PYTHONDONTWRITEBYTECODE=1` so existing tracked bytecode was not
changed. `compileall` used `PYTHONPYCACHEPREFIX=/private/tmp/blindassist-phase1-pycache`
so its explicit compilation outputs also remained outside the repository.

| Command | Before Phase 1 | Final result |
| --- | --- | --- |
| `python3 -m unittest tests.test_command_broker -v` | New tests absent | **PASS**, 19 tests, exit 0 |
| `python3 -m unittest tests.test_input_arbiter -v` | New tests absent | **PASS**, 10 tests, exit 0 |
| `python3 -m unittest tests.test_operation_state -v` | New tests absent | **PASS**, 5 tests, exit 0 |
| `python3 -m unittest tests.test_mobile_dispatch_regression -v` | New tests absent | **PASS**, 25 tests, exit 0 |
| All four new test modules together | Not applicable | **PASS**, 59 tests, exit 0 |
| `python3 -m unittest discover -s tests -v` | **BLOCKED/HUNG**, terminated at 60 seconds, exit -15 | Same existing hang after integration; terminated at 60 seconds, exit -15. Not a passing full-suite run |
| `python3 /private/tmp/blindassist-phase0-regressions.py` | **FAIL**, 286 run: 275 pass, 11 fail, exit 1 | **FAIL**, final 345 run: 334 pass, same 11 fail, exit 1. Excludes exactly one known hang; no other exclusions |
| `python3 -m compileall -q main.py gateway tests` | Not needed for absent new code | **PASS**, external cache prefix, exit 0 |
| `python3 scripts/check_install_layout.py` | **PASS**, exit 0 | **PASS**, exit 0 |
| `bash -n install.sh` | **PASS**, exit 0 | **PASS**, exit 0 |
| `python3 -m pip check` | **FAIL**, exit 1, nine existing conflicts | **FAIL**, exit 1, byte-identical output |
| `git diff --check` and staged scope checks | Existing editor edit retained | **PASS** for Phase 1 changes |
| `git diff --stat`, `git status --short` | Recorded initial checkout | Reviewed against baseline; only authorized files committed, user edit remains unstaged |
| `.venv/bin/python selftest.py --profile device --vision --mic` | Not run | **NOT RUN**: no configured Pi/.venv/camera/mic test permission in this Mac environment |

The final supplementary run's unittest-reported duration was 32.827 seconds;
baseline was 33.172 seconds. These are laptop suite timings, not feature latency
or a performance result. An earlier integration run covered 341 tests (before
four additional failure-isolation tests) with the same 11 failures. The final
345-test comparison and four module-specific runs cover the final code.

## Existing failures and full-suite blocker

Ordinary discovery stalls in unchanged
`test_core_regressions.RepairedDefectTests.test_tts_mp3_uses_music_channel_not_sound`.
With pygame installed, its unconfigured mock `music.get_busy()` stays truthy in
the existing playback loop. No test or TTS implementation was patched to conceal
it. A temporary subprocess supervisor stopped ordinary discovery with SIGTERM
after 60 seconds before and after integration; this was not a device shutdown.

The supplementary runner recursively discovers the actual tests, excludes only
that exact test ID, and executes the remaining suite. Its complete source is
reproducible from [the Phase 0 baseline](MOBILE_PHASE0_TEST_BASELINE.md#ordinary-discovery-hang).
It does not modify repository tests, dependencies or providers. The exact failed
IDs below match before/after; there were no reported errors/skips in those runs.

| Test module / class | Pre-existing failed method |
| --- | --- |
| `test_core_regressions.RepairedDefectTests` | `test_voice_listen_is_hands_free` |
| Same | `test_voice_recording_target_is_configurable` |
| `test_ocr_guidance.CaptureTests` | `test_ready_captures_full_resolution_once` |
| Same | `test_rejected_still_ends_single_attempt` |
| Same | `test_timeout` |
| `test_ocr_guidance.FramingTests` | `test_gate_requires_stability_and_limits_speech` |
| Same | `test_same_instruction_is_not_repeated_forever` |
| Same | `test_text_without_visible_paper_boundary_can_capture` |
| `test_ocr_small_text.OCRSmallTextTests` | `test_default_capture_uses_native_resolution_and_page_wide_focus` |
| Same | `test_sparse_cloud_result_on_full_page_runs_local_coverage_check` |
| `test_processing_feedback.OCRFallbackFeedbackTests` | `test_online_failure_announces_local_fallback_and_reads_once` |

Existing pip conflicts were unchanged: langchain-openai/openai,
langchain-google-genai/google-genai, googletrans/httpx,
langchain-community/requests, surya-ocr/httpx, typer/click, and three
opentelemetry-exporter-otlp-proto-grpc requirements (exporter common, proto, SDK).
Pip also disables its unwritable sandbox user cache. No installation or upgrade
was performed; neither unit tests nor this report certify that system environment
as a deployable Pi image. CI still targets Ubuntu Python 3.11/3.13; no CI workflow
was changed or claimed executed.

## New test coverage and limits

- **Models/lifecycle (5):** exact typed parameters, immutable caller input,
  safe validation errors, required transitions, terminal-state protection and
  cancellation intent versus actual cancellation.
- **Broker (19):** admission, unknown/disabled modes, busy isolation, owner-only
  execution, duplicate/conflicting IDs, bounded queue/history, pending expiry,
  physical priority, changed profile before claim, failure recovery, pending
  cancellation, unsupported active cancellation, cooperative test-double signals,
  shutdown and concurrent submit/status access.
- **Input arbiter (10):** all digits including 0, partial state across many polls,
  timing boundary/expiry, READY/backspace, ignored Button 3 followups, legacy
  LETTER-only firmware, raw precedence and hardware-independent imports.
- **Dispatch regression (25):** actual main-loop/dispatcher function bodies with
  hardware initialization excluded by AST, fake Pico/TTY and handlers. Covers
  standalone startup/shutdown confirmation, idle simulated request, partial
  Morse priority, single input owner, nested gesture dispatch, private policy/
  return isolation, profile checks, no duplicate execution, broker init/runtime/
  completion failures, history exhaustion, error-speech failure and thread guard.

The regression harness compiles selected functions directly from the current
`main.py`, rather than importing its hardware-initializing top-level code. It
uses real privacy contexts and broker classes with hardware/feature doubles.
The existing supplementary suite also exercises real main runner/service code
with its existing mocks. These tests establish software behavior, not real camera,
microphone, Pico timing, earphone isolation, model accuracy or network-provider
availability. Cancellation of active V2 modes through the broker remains
explicitly unsupported; their unchanged physical controls require device testing.

`tests/__init__.py` is a necessary addition: initial inspection found an unrelated
installed `site-packages/tests/__init__.py` shadowing the local namespace. The local
package makes the four requested `python3 -m unittest tests.test_*` commands resolve
to this repository without changing the Python environment.

## File scope and preservation

New files (13):

- `gateway/__init__.py`, `command_models.py`, `operation_state.py`,
  `command_broker.py`, `input_arbiter.py`: pure internal dispatch package.
- `tests/__init__.py`, `test_command_broker.py`, `test_input_arbiter.py`,
  `test_operation_state.py`, `test_mobile_dispatch_regression.py`: test package
  resolution and the four requested suites.
- `docs/MOBILE_PHASE1_DISPATCHER.md`, `MOBILE_PHASE1_TEST_RESULTS.md`,
  `MOBILE_PHASE1_HANDOFF.md`: implementation, results and future handoff.

Modified existing implementation file: **`main.py` only**, for optional broker
initialization/cleanup, designated execution and nested-call guard, retained
runner failure metadata and cooperative main-menu arbitration. No mode handler
was rewritten. Content fingerprints and source AST comparisons confirm every
other initially tracked file/link retains its starting content, including all
`modules/`, `services/`, firmware, configs, deploy files, Phase 0 artifacts,
Android/model/vendor assets, tracked bytecode/logs and the user's editor edit.

No secrets, real documents/transcripts, runtime logs, generated bytecode, data
stores, model assets or hardware configuration were added to commits. No endpoint,
transport or phone capability was implemented. Physical/offline/online quality
and clean full-suite/dependency gates remain explicit limitations for later work.
