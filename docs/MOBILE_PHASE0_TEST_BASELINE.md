# Phase 0 validation baseline

Recorded 8 November 2026, Asia/Kolkata. This report deliberately retains existing
failures. Phase 0 adds documentation and an Android source scaffold, not terminal
runtime changes. **A clean terminal regression gate, Android APK build and
Raspberry Pi hardware readiness are not established.**

## Environment captured before validation/scaffolding

Initial commands: `pwd`, `git status --short`, `git branch --show-current`,
`git log -1 --format='%h %cs %s'`, `git ls-files`, `python3 --version`,
`git rev-parse HEAD`, `uname -sm`, `java -version`, `command -v gradle`,
`command -v sdkmanager`, `command -v adb`, plus static path/environment checks.

| Item | Observed value |
| --- | --- |
| Checkout | `/Users/daxpatel/Desktop/Collage/Reseach/BlindAssist/blindassistv2/blindterminalv2` |
| Initial HEAD | `0a4666ffe880a6cfb1d0d734459cea5035a3fc28` |
| Initial branch | `feature/android-phase0-foundation`, already existed; reused without reset/switch |
| Initial worktree | ` M .vscode/settings.json` only; user edit preserved and never staged |
| OS / architecture | macOS 26.0, Darwin arm64; not a Raspberry Pi |
| Active Python | Python 3.13.2, `/Library/Frameworks/Python.framework/Versions/3.13/bin/python3` |
| Python environment | Existing system interpreter; no active virtual environment; checkout `.venv` absent |
| Device settings | `config/settings.json` absent; not created or regenerated |
| Java | Java(TM) SE 17.0.12+8-LTS-286, 64-bit HotSpot; JAVA_HOME unset |
| Gradle / SDK tools | No `gradle`, `sdkmanager` or `adb` on PATH |
| SDK | ANDROID_HOME / ANDROID_SDK_ROOT unset; `~/Library/Android/sdk` and `/opt/android-sdk` absent; no project local.properties |
| Device models/data | Existing `data` and `models` dangling symlinks retained; no model provisioning performed |

Tracked file/link content fingerprints were captured **before tests** in a
temporary manifest, so existing dirty editor content could also be checked for
preservation. Raw logs, temporary runners and fingerprints stay outside the
repository under `/private/tmp/blindassist-phase0-*`; they are not deliverables
or committed runtime data. No dependency install, upgrade, new virtual environment,
system package installation, settings generation, device startup/service change,
index ingestion or model download was performed.

## Commands and outcomes

Python commands used `PYTHONDONTWRITEBYTECODE=1` to avoid changing the already
tracked bytecode. This does not change the installed dependencies. "Before" is
before Android/gateway scaffolding; "after" is after source scaffold creation.
All software commands below used the same macOS/system-Python environment.

| Command / check | Before | After | Hardware required / summary |
| --- | --- | --- | --- |
| `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests -v` | **BLOCKED/HUNG**, interrupted, exit 130 | Not repeated: same known hang, terminal source unchanged | Software suite; no hardware readiness result. Hung in existing pygame mock test described below |
| `PYTHONDONTWRITEBYTECODE=1 python3 /private/tmp/blindassist-phase0-regressions.py` | **FAIL**, exit 1; 286 run, 275 passed, 11 failed; 34.112 s | **FAIL**, exit 1; 286 run, 275 passed, same 11 failed; 35.267 s | Supplementary diagnostic suite, excludes exactly one known hanging test. Timings describe laptop test runs, not feature latency |
| `PYTHONDONTWRITEBYTECODE=1 python3 scripts/check_install_layout.py` | **PASS**, exit 0 | **PASS**, exit 0 | No hardware; installation layout and canonical/legacy config examples valid |
| `bash -n install.sh` | **PASS**, exit 0 | **PASS**, exit 0 | No hardware; shell syntax only |
| `python3 -m pip check` | **FAIL**, exit 1 | **FAIL**, exit 1, identical output | Existing dependency inconsistencies, listed below; no package changes |
| `PYTHONDONTWRITEBYTECODE=1 ./install.sh --check` | **PASS**, exit 0 | **PASS**, exit 0 | Installer read-only branch; no installation, model/config generation or capture |
| `.venv/bin/python selftest.py --profile device --vision --mic` | **NOT RUN** | **NOT RUN** | Requires configured Pi, camera/mic permission and prepared .venv; this host is macOS |
| `cd android-app` then `./gradlew :app:assembleDebug` | **NOT APPLICABLE**, no project | **BLOCKED / NOT RUN**, Android SDK absent | Complete wrapper/task configuration prepared; compilation/task execution not verified without SDK |
| `sh -n android-app/gradlew` | Not applicable | **PASS**, exit 0 | No hardware; official wrapper shell syntax |
| Android XML/resource/manifest inspection | Not applicable | **PASS**, five XML files parsed | No hardware; launcher, locales and no permissions/services/receivers checked. Not APK compilation or TalkBack validation |
| Gradle wrapper verification | Not applicable | **PASS** | Official JAR SHA-256 matches published checksum, ZIP integrity/main class checked, script executable, distribution hash pinned |
| `git check-ignore -- <representative paths>` | Not applicable | **PASS** | SDK-local settings, builds/APKs, signing material, gateway private upload/config/env paths ignored; source/wrapper paths remain trackable |
| Original tracked-file fingerprints | Snapshot captured | **PASS**, only `.gitignore` differs | All original terminal/config/firmware/vendor/model-link/asset bytes match starting state; editor edit also unchanged |
| `git diff --check` and scoped staged checks | Initial existing user edit retained | **PASS** for Phase 0 changes | No unrelated editor file or generated/runtime data staged |

Shell/layout commands were captured with individual subprocess exit codes;
`pip check` was not hidden by a later successful shell command. Source fingerprints
and local Markdown links were checked with temporary Python scripts; no new test
files were added to or used to repair the terminal suite.

### Ordinary discovery hang

The exact existing test is:

`test_core_regressions.RepairedDefectTests.test_tts_mp3_uses_music_channel_not_sound`

Pygame is installed on this host, so the test does not skip. It patches
`tts.pygame` with a default Mock, then calls `TTSManager._play_pygame()`. That
implementation loops while `pygame.mixer.music.get_busy()` is truthy; an
unconfigured Mock stays truthy and the mocked wait does not create a completion
condition. The log stopped at that test. The process was interrupted with SIGINT;
this is **not a passing test run**, and the full-suite pass count is unavailable.
No repository test, TTS source or installed package was edited to obtain green.

A temporary supplementary runner discovers the same suite and excludes only that
ID, without mocking additional dependencies or changing repository files. Both
runs completed with the same failure IDs. For reproducibility, the complete
temporary runner content is:

```python
from pathlib import Path
import sys
import unittest

root = Path.cwd()
sys.path.insert(0, str(root))
blocked = (
    "test_core_regressions.RepairedDefectTests."
    "test_tts_mp3_uses_music_channel_not_sound"
)
suite = unittest.defaultTestLoader.discover(str(root / "tests"))

def tests(suite):
    for item in suite:
        if isinstance(item, unittest.TestSuite):
            yield from tests(item)
        else:
            yield item

selected = []
for test in tests(suite):
    if test.id() == blocked:
        print("EXCLUDED documented pre-existing pygame mock hang: " + test.id(), flush=True)
    else:
        selected.append(test)
print("Running", len(selected), "existing tests without repository edits", flush=True)
result = unittest.TextTestRunner(verbosity=2).run(unittest.TestSuite(selected))
sys.exit(not result.wasSuccessful())
```

### Existing failures, identical before and after

These are exact failed method names; the class/file identifies each suite. The
assertion summaries are observations, not a complete root-cause diagnosis.

| Test file / class | Failed method | Observed assertion |
| --- | --- | --- |
| `test_core_regressions.RepairedDefectTests` | `test_voice_listen_is_hands_free` | Returned None rather than expected `hello there` |
| Same | `test_voice_recording_target_is_configurable` | Returned recording path did not meet configured-directory assertion |
| `test_ocr_guidance.CaptureTests` | `test_ready_captures_full_resolution_once` | Spoken capture message differed from expected `Reading now.` |
| Same | `test_rejected_still_ends_single_attempt` | Expected capture-failure wording absent |
| Same | `test_timeout` | Timeout message includes guidance beyond expected short string |
| `test_ocr_guidance.FramingTests` | `test_gate_requires_stability_and_limits_speech` | Stability/announcement assertion false |
| Same | `test_same_instruction_is_not_repeated_forever` | Three repetitions versus expected one |
| Same | `test_text_without_visible_paper_boundary_can_capture` | `left` rather than `ready` framing state |
| `test_ocr_small_text.OCRSmallTextTests` | `test_default_capture_uses_native_resolution_and_page_wide_focus` | Capture returned None rather than mocked image |
| Same | `test_sparse_cloud_result_on_full_page_runs_local_coverage_check` | Short cloud text rather than expected local body text |
| `test_processing_feedback.OCRFallbackFeedbackTests` | `test_online_failure_announces_local_fallback_and_reads_once` | Expected fallback announcement assertion false |

There were no reported errors or skips in the 286-test supplementary runs. The
excluded hanging test is additional to those 286. No failure was fixed or hidden
by changing terminal code, fixture expectations or dependency versions.

### Existing dependency inconsistencies

`python3 -m pip check` reported the same nine conflicts both times:

| Installed package | Required dependency | Installed dependency |
| --- | --- | --- |
| langchain-openai 1.2.1 | openai >=2.26.0,<3.0.0 | 1.109.1 |
| langchain-google-genai 4.2.2 | google-genai >=1.65.0,<2.0.0 | 2.26.0 |
| googletrans 4.0.0rc1 | httpx ==0.13.3 | 0.28.1 |
| langchain-community 0.4.1 | requests >=2.32.5,<3.0.0 | 2.31.0 |
| surya-ocr 0.20.0 | httpx >=0.27.0,<0.28 | 0.28.1 |
| typer 0.25.1 | click >=8.2.1 | 8.1.8 |
| opentelemetry-exporter-otlp-proto-grpc 1.41.1 | opentelemetry-exporter-otlp-proto-common ==1.41.1 | 1.42.1 |
| Same | opentelemetry-proto ==1.41.1 | 1.42.1 |
| Same | opentelemetry-sdk ~=1.41.1 | 1.42.1 |

Pip additionally warned that its user cache was not writable in this sandbox and
disabled that cache. That does not resolve or explain away these version
conflicts. This is a shared system environment, not a newly isolated image from
`requirements-test.txt` or a validated Raspberry Pi installation.

## CI, deployment and device validation boundary

`.github/workflows/tests.yml` targets Ubuntu, Python 3.11 and 3.13. It installs
`requirements-test.txt`, checks pip consistency/layout/installer syntax, then
executes unittest discovery. The local interpreter is on one of those Python
versions, but the operating system and pre-existing packages differ. GitHub
Actions was inspected, not triggered, and no CI result is inferred here.

`install.sh` permits Python 3.10–3.13; deployment docs use 3.11 as the Pi reference.
`deploy/blindassist.service.example` uses the existing main entrypoint and device
vision preflight, with audio/video/dialout groups. Neither was changed. The
required hardware command remains:

```bash
.venv/bin/python selftest.py --profile device --vision --mic
```

It accesses camera/microphone and was not executed on this Mac. Physical Pico,
headset isolation, camera/microphone operation, local model provisioning, live
providers, offline feature quality, GPS routing and user usability remain
unverified. `verify_install.py` was inspected statically, not run as a replacement
for regression or device testing. Existing startup instructions still apply;
the absence of local settings/models was not silently repaired by Phase 0.

Android SDK provisioning and a real `:app:assembleDebug` run remain required.
The wrapper was not executed to download the full distribution because no SDK
is available; only official wrapper files and published checksums were fetched.
The JDK-compatible toolchain and source configuration are described in
[the Android README](../android-app/README.md). No APK/emulator, TalkBack, touch,
large-font or native-language review result is claimed.

## Preservation and completion assessment

Content fingerprints cover all 3,436 initially tracked paths, treating symlinks
as link text rather than following removable storage. After scaffolding, the only
changed original file is the authorized additive `.gitignore`; all terminal
source, configuration examples, firmware, tracked bytecode/log/audio/images,
vendor files and model/data symlinks match the initial snapshot. `.vscode/settings.json`
still has precisely the user's initial edit. No runtime store or model tree was
created; the cache directory is empty. Temporary raw logs are not committed.

Phase 0 deliverables and design boundaries are prepared with explicit blocked/
failed validations. This is evidence of source preservation and stable observed
software failures, **not** proof of fully working terminal hardware or a passing
Android build. Phase 1 requires a new scoped request; remaining baseline issues
must stay visible when assessing later integration regressions.
