# Phase 2 validation results

8 November 2026, macOS arm64, Python 3.13.2. Installed gateway libraries were
FastAPI 0.127.0, Pydantic 2.12.5, Uvicorn 0.40.0 and httpx 0.28.1. No packages
were installed/upgraded to mask existing environment problems. Socket checks
needed execution outside the workspace sandbox, which rejects local socket bind.
All real traffic stayed on loopback/Unix sockets; handlers and hardware were
simulated. This is not physical Raspberry Pi integration validation.

## Actual commands and outcomes

| Check | Result |
| --- | --- |
| `python3 -m unittest discover -s tests -p "test_gateway_*.py" -v` | **42/42 pass** (final external-cache run 7.735 s unittest time; supervisor 9.694 s) |
| `python3 scripts/smoke_gateway.py` | **Pass**, actual `python3 -m gateway.server` subprocess, port 8765, curl and real UDS/broker |
| `python3 -m unittest discover -s tests -p test_mobile_dispatch_regression.py -q` | **25/25 pass**, existing controller/physical/privacy regression tests |
| `python3 -m unittest discover -s tests -v` | **Blocked by existing pygame mock hang**, before and after; stopped at 60 s (60.197/60.282 s supervisor elapsed) |
| Diagnostic discovery excluding only the known hanging test | Before: **345 run, 334 pass, 11 fail** (33.635 s). Final: **387 run, 376 pass, same 11 fail** (33.052 s). No errors/new failures |
| `python3 -m compileall -q gateway tests` | **Pass**, run together with main.py and smoke script using external bytecode prefix |
| `python3 scripts/check_install_layout.py` | **Pass** before and after |
| `bash -n install.sh` | **Pass** before and after |
| `python3 -m pip check` | **Fail before and after**, same nine existing conflicts |
| `git diff --check` / scoped preservation checks | **Pass**; only authorized Phase 2 changes, original editor modification preserved |

Final gateway coverage: API 11, authentication/settings 8, command forwarding 7,
IPC 12, isolation/terminal hook 4. Tests cover real socket/broker status and
capabilities, strict JSON/types/limits, missing/invalid/duplicate authentication,
rotation, file permissions/symlinks, command/mode allowlists, namespacing,
duplicate/conflicting IDs, owner-only execution, busy/disabled/unknown modes,
pending cancellation, unsupported active cancellation, malformed peer responses,
absolute partial-frame deadlines, bounded workers/admission, stale/live socket
handling, bounded shutdown, no private result/error echo, no browser/remote peer,
and import guards that forbid main, feature services and hardware libraries.

The real subprocess smoke used temporary 0600 credential/curl files and printed
no token. Results: authenticated status **200**, invalid bearer **401**, busy
**409**, pending cancel **CANCELLED**, terminal unavailable **503**, gateway-only
health **200**. After killing the gateway, the existing broker accepted and
completed a physical request. Restarting the gateway and retrying the original
mobile ID returned COMPLETED with exactly one recorded owner-side fake handler
execution. The smoke terminated its own processes and removed temporary files.
It did not start `main.py`, use real devices or test phone pairing.

## Reproducible diagnostic exception

The default suite hangs at:
`test_core_regressions.RepairedDefectTests.test_tts_mp3_uses_music_channel_not_sound`.
No existing test was disabled/edited to hide it. The supplementary runner was
`/private/tmp/blindassist-phase0-regressions.py`; its only exclusion is that exact
test ID. Equivalent reproduction from the root, without repository edits:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 - <<'PY'
import unittest
blocked = 'test_core_regressions.RepairedDefectTests.test_tts_mp3_uses_music_channel_not_sound'
def flatten(suite):
    for item in suite:
        if isinstance(item, unittest.TestSuite):
            yield from flatten(item)
        else:
            yield item
suite = unittest.defaultTestLoader.discover('tests')
selected = unittest.TestSuite(t for t in flatten(suite) if t.id() != blocked)
result = unittest.TextTestRunner(verbosity=2).run(selected)
raise SystemExit(not result.wasSuccessful())
PY
```

The same 11 failures, before and after:

- `test_core_regressions.RepairedDefectTests`: `test_voice_listen_is_hands_free`,
  `test_voice_recording_target_is_configurable`.
- `test_ocr_guidance.CaptureTests`: `test_ready_captures_full_resolution_once`,
  `test_rejected_still_ends_single_attempt`, `test_timeout`.
- `test_ocr_guidance.FramingTests`: `test_gate_requires_stability_and_limits_speech`,
  `test_same_instruction_is_not_repeated_forever`,
  `test_text_without_visible_paper_boundary_can_capture`.
- `test_ocr_small_text.OCRSmallTextTests`:
  `test_default_capture_uses_native_resolution_and_page_wide_focus`,
  `test_sparse_cloud_result_on_full_page_runs_local_coverage_check`.
- `test_processing_feedback.OCRFallbackFeedbackTests`:
  `test_online_failure_announces_local_fallback_and_reads_once`.

Existing dependency conflicts: langchain-openai/openai,
langchain-google-genai/google-genai, googletrans/httpx,
langchain-community/requests, surya-ocr/httpx, typer/click, and three
opentelemetry-exporter-otlp-proto-grpc dependencies (proto-common, proto, sdk).
Gateway/test dependencies were added to their own requirements group; no existing
terminal requirements or system packages were rewritten. CI consumes the updated
test requirements, but hosted CI was not run or claimed green.

## Artifacts, preservation and unvalidated checks

Baseline logs: `/private/tmp/blindassist-phase2-before-{full,diagnostic,layout,shell,pip}.log`.
Full post-change/auxiliary logs use `blindassist-phase2-after-*.log`; final
gateway/diagnostic/compile logs use `blindassist-phase2-final-*.log`.
Supervisor results: `blindassist-phase2-baseline.json`,
`blindassist-phase2-validation.json`, `blindassist-phase2-final.json` in that
temporary directory. These local artifacts are not repository deliverables.
Command wrappers set `PYTHONDONTWRITEBYTECODE=1`; final compilation used
`PYTHONPYCACHEPREFIX=/private/tmp/blindassist-phase2-pycache` and
`python3 -m compileall -q gateway tests main.py scripts/smoke_gateway.py`.

SHA-256/symlink fingerprints of all 3470 original tracked paths were checked
against the pre-edit snapshot. Changes to existing files are limited to main.py,
test requirements, the controller test harness and gateway README. All other
original bytes/links, including the user's dirty `.vscode/settings.json`, remain
unchanged. AST comparison confirms the only altered original main functions are
main, shutdown and dispatcher disable; every existing mode handler is identical.

Not validated: actual Pi/Pico/serial ownership, physical camera/mic/TTS, live
private processing, installed systemd behavior, phone transport, LAN/TLS security,
hardware benchmarks or crash-durable deduplication. No Android/BLE/file-transfer
work was started. The local software contract is ready for further integration;
hardware and baseline release gates remain open.
