# Android companion: Phase 0 repository audit

Audited 8 November 2026 against terminal revision
`0a4666ffe880a6cfb1d0d734459cea5035a3fc28`. This is a static source audit plus
the software checks in [the baseline report](MOBILE_PHASE0_TEST_BASELINE.md).
It establishes no new hardware, cloud-provider, accuracy or latency validation.
The terminal remains the primary product; all mobile integration is **PLANNED**.

## Checkout and inspection boundary

The local checkout is named `blindterminalv2`; the supplied upstream project is
`Daxptl7/blindterminalv1`. Work uses this local checkout without cloning,
relocating, renaming, or changing its remote configuration. The requested branch
`feature/android-phase0-foundation` already existed. Initial status contained
only ` M .vscode/settings.json`; that user edit is excluded from Phase 0 commits.

Initial inspection used `pwd`, `git status --short`, `git branch --show-current`,
`git log -1 --format='%h %cs %s'`, and `git ls-files`. There were 3,436 tracked
paths, including 3,284 under the existing `llama.cpp/` vendor tree. The application
lives at the repository root: `main.py`, `modules/`, `services/`, `config/`,
`tests/`, `scripts/`, `deploy/`, `docs/`, and `pico_firmware/`. Other existing
content includes `audio/`, `.planning/`, Python backups, package manifests, and
legacy assets. `gateway/` and `android-app/` were absent. No vendor work is needed.

All requested audit files were found and inspected: README, CLAUDE, CHANGES,
main, selftest, verify_install, installer, canonical settings example,
config_loader, morse, morse_serial, ai_query, voice, tts, ocr, confidential_mode,
privacy_policy, translator, live_translator, gesture_control, object_detection,
gps_navigator, math_solver, processing_feedback, all five service implementations,
Pico firmware, deployment/button/readiness docs, CI and all three requested
requirements files. Additional relevant sources are `translation_controls.py`,
`ocr_guidance.py`, the tests and installation-layout checker. Discovery used
source text/AST, without importing `main.py`. The existing test suite itself does
import `main`, which is a separate, explicitly executed validation step.

## Central execution authority

`main.py` reads settings at import, sets up logging, and calls
`_safe_import(module_name, alias)` for feature modules. That helper stores either
the module/alias or `None` in `_modules`; `_has()` guards feature entry. Optional
import failure degrades individual functions rather than necessarily terminating
the entire application. Core configuration/privacy imports remain dependencies.
Importing this file can create threads, inspect audio devices, and open serial;
a gateway must never import it merely to discover capabilities.

`_morse_serial_singleton` is constructed once by the orchestrator and supplied
to `voice.set_morse_serial()`. `MODE_MAP` maps digits to handlers. `run_mode()`
checks `enabled_modes` before invocation, enters `processing_session(PUBLIC)`
for ordinary mode entry, handles mode exceptions and clears private recordings
on exit. Nested gesture dispatch detects `session_active()` and preserves the
current session. This is synchronous execution, without a global broker lock.
Calling `run_mode()` from arbitrary threads would bypass the present single
menu caller and is unsafe.

`main()` validates configuration strictly. With `release_profile == "device"`,
it runs `selftest.py --profile device --vision` with a 90-second subprocess
timeout before continuing. It currently requires Pico input or a TTY; mobile-only
startup is not supported. `_get_menu_choice()` blocks up to 120 seconds for a
Pico Morse digit, or uses blocking TTY `input()` through `_keyboard_input()`.
Three consecutive empty selections stop the application. Digit 0 asks for
confirmation; it exits BlindAssist, not an operating-system power-off command.

`shutdown()` is idempotent, stops speech, closes AI clients, queues goodbye,
waits up to 10 seconds for speech, shuts down TTS and closes the Pico reader.
SIGINT/SIGTERM invoke it only when `main.py` is executed as the entry script.

Other blocking work includes button submenus (default 15 seconds after prompts),
Morse text entry (90-second idle window in the shared helper), recording
(180-second manual backstop by default), output selection, model loads,
camera loops, network calls, and synchronous local mathematics. There is no
universal mode cancellation interface. `processing_feedback.run_with_feedback()`
polls cancellation every 50 ms, bounds outstanding workers with two semaphore
slots, and defaults to a 90-second caller deadline. It cannot forcibly kill a
non-cooperative thread; a cancelled provider may finish later while retaining its
slot. Its result box is private to that operation, preventing late playback by
the caller. Hardware-resource cleanup still requires verification.

**PLANNED integration:** introduce a request-arbitration boundary in the main
loop around menu selection and immediately before `run_mode()`. A future input
adapter must make the blocking menu interruptible while preserving Morse state,
timeouts and physical control semantics. Only that execution owner may admit a
mode request. Requests cannot safely be inserted solely after a blocking
`_get_menu_choice()` call, nor executed from a gateway thread/process. See
[the handoff](MOBILE_PHASE0_HANDOFF.md); this phase changes no orchestrator code.

## Nine modes and their real constraints

Unless explicitly called inside an internal private policy, modes start PUBLIC:
cloud and persistence are permitted. Completed-result audio selection is not a
private-processing switch. Speaker prompts remain public; local engines/models
and a usable audio stack must be installed for offline operation. Default
`enabled_modes` is `1,2,3,4,5,6,8,9`; Mode 7 is excluded. The example has
`app_mode: device`, `release_profile: development`, `navigation_enabled: false`.
These are template/default values, not evidence of a provisioned release device.

| Mode / entry in main.py | Dependencies and hardware | Online and local alternatives | Privacy, audio, cancellation and missing dependencies |
| --- | --- | --- | --- |
| 1 `mode_ocr_scan()` | `ocr.open_camera()`, `scan_and_read()`, `ocr_guidance`; OpenCV/Pillow, CSI camera via rpicam or USB camera; Tesseract executable/languages | Configured Gemini-first OCR in auto mode, then local multipass Tesseract; Surya only when explicitly selected/enabled with its dependencies/weights. Optional AI explanation and RAG ingestion | Policy blocks cloud OCR in private sessions. Normal OCR can be indexed after reading; earphone selection does not prohibit this. Result/explanation each choose audio output; failed routing cancels content. Three Button 3 presses cancel guided capture/processing; camera released in `finally`. Missing camera/engine gives spoken failure, not a fabricated page |
| 2 `mode_morse_type()` | `_morse_type_sentence()`, Pico `type_word()` or keyboard/`morse.MORSE_CODE_DICT`, `ai_query.ask_ai()` | Groq → OpenAI within shared first-tier budget → Gemini → installed llama.cpp Python model; missing RAG does not necessarily prevent general answers | Per-letter/word speaker feedback; answer uses `_deliver_result()`. PUBLIC typing echoes content. PRIVATE API policy restricts AI to local processing. Double Button 3 submits; long press edits; idle timeout returns accumulated text. Processing uses cancellable wrapper. Missing AI reports unavailable |
| 3 `mode_voice_ask()` | `voice.listen()`, microphone/arecord, `ai_query`; local Vosk per language, optional Sphinx; TTS | Google recognition first when configured/allowed, then available local recognition; same AI fallback as Mode 2 | PUBLIC source recordings retained/pruned; private temporary recordings removed. Three Button 3 presses finish ordinary recording (four-second inter-press rule); TTY Enter/backstop without Pico. Button 1 interrupts answer playback and opens follow-up; Button 2/choice timeout leaves follow-up loop. Fresh output selection per answer, recent conversation in memory. Missing voice/AI aborts with message |
| 4 `mode_translate()` / `_translate_once()` | `translator.translate_ex()`, `TranslationButtons`, voice or Morse; `LiveTranslator.run_live()` for continuous audio; microphone/output streams for live | English/Hindi/Gujarati in six phrase directions: validated public cache, configured providers reordered cloud-first, then installed IndicTrans2/Argos/trusted local LibreTranslate, exact phrasebook last. Live uses Gemini audio and has no local equivalent | Private phrase requests skip cloud/untrusted Libre and persistent cache; trusted LAN service is distinct from internet. Triple Button 3 within five seconds exits at every translated stage; single/double Button 3 actions delayed to resolve exit. TTY `333` exits menus. Phrase results choose output; live uses configured stream without per-result selection and refuses private processing. Missing local bundles limit arbitrary offline translation; unavailable live module/service reports failure |
| 5 `mode_gesture()` | `gesture.detect_gesture()`, MediaPipe classic Hands or Tasks bundle, OpenCV/USB or rpicam camera | Local landmark/classifier pipeline; selected action may invoke another online-capable mode | Button 1 captures stable shape, Button 2 previews, Button 3/fist leaves; TTY alternatives. Camera loop ends before nested `run_mode()` for OCR/voice/object/GPS, then gesture can resume. Missing backend/model/camera yields actionable message. macOS Tasks backend has explicit unsafe opt-in guard. Status speech uses shared TTS; no mobile camera owner permitted |
| 6 `mode_object_detection()` | `objdetect.prepare_model()`, `run_detection()` / `stream_detect()`, Ultralytics YOLO weights, camera | Local YOLO, temporal stability and horizontal-position announcements; `yolo_allow_download` defaults false | Spoken detections use `_speak()` rather than the completed-result selector; PRIVATE context would enforce private TTS. Button 3 or TTY Enter stops; default 120-second limit. Missing weights/camera abort with explicit failure. No measured distance, path clearance, or pedestrian safety guarantee |
| 7 `mode_gps()` | `gps.get_location()`, UART GPS on separate port, pyserial/pynmea2; voice mic only for route destination | Fresh valid NMEA coordinates locally; public reverse geocoding/destination lookup via Nominatim and route summary via OSRM require internet | Default disabled mode plus `navigation_enabled: false`. Device mode raises `NoGPSFix`; explicit simulation labels coordinates. Private output uses coordinates without cloud geocoding and blocks routes. Location/menu/network operations lack a universal mobile cancel. Optional destination confirmation; route needs hardware fix. No live turn loop/rerouting or validated pedestrian routing. Missing GPS is not replaced with fake location |
| 8 `mode_confidential_demo()` | `confidential_mode.speak_with_privacy_check()`, `tts`, two verified distinct ALSA output routes | Output selector and local speech can work offline if provisioned; PUBLIC synthesis may use configured gTTS | Audio test only; does not select PRIVATE processing. Button 1 earphones, Button 2 speaker, unanswered prompt cancels. Missing privacy module/earphones prevents private playback. Private route intentionally unavailable on macOS |
| 9 `mode_math_solver()` | `mathsolver.solve()` / `sanitize_ai_answer()`, SymPy; Morse or voice input | Exact local arithmetic, roots, percentages, averages, one-variable polynomial equations and determinants; unsupported word problems may use explicitly labelled AI fallback | Strict AST allow-list; grammar/input/degree/matrix limits. Invalid inputs do not go to AI. Explicit context excludes unrelated RAG for fallback. Results choose output; voice/Morse and AI cancellation as above. Local solve is synchronous, without general interrupt adapter. Missing SymPy/solver is announced |

## Morse/Pico connection and event ownership

Firmware `pico_firmware/main.py` uses GP0/GP1/GP2, default active-high pull-down
inputs, debounced nonblocking `ButtonController.update()` polling every 5 ms.
The controls are preserved: Button 1 dot, Button 2 dash, Button 3 space/send/edit.

| Event | Actual producer/meaning |
| --- | --- |
| `READY` | Firmware startup; host clears pending menu symbols |
| `RAW:1`, `RAW:2`, `RAW:3` | Debounced press edge, including a later-held press |
| `LETTER:<character>` | Letter/digit lookup after 1,500 ms symbol gap; `?` for unknown code; pending letter flushed on space/confirm |
| `WORD_SPACE` | Short Button 3 single click after 500 ms double-click window |
| `BACKSPACE` | Button 3 held at least 400 ms, once per hold; clears firmware partial symbol buffer |
| `CONFIRM` | Two short Button 3 clicks inside 500 ms; flushes pending letter |

`MorseSerial` opens 115200 baud, one-second serial read timeout, one background
`_read_loop()` and one destructive-consumption `message_queue`. Port discovery
actually checks Pico VID/description **before** a configured existing path, then
generic tty candidates; a comment claiming configured-port priority is stale.
Reconnect closes dead handle, rediscovers nodes and backs off from 0.5 to 5
seconds, consolidating errors every 30 seconds. Main does not wire the optional
`on_state_change` callback, so automatic spoken reconnection status is not proven.

Menu `read_menu_digit()` counts five RAW dot/dash presses, ignoring interleaved
decoded letters. Default five-second symbol gap is clamped 2–30 seconds; the main
call has a 120-second overall deadline. `LETTER`-only legacy digits work until a
RAW symbol has been observed. `type_word()` builds text from LETTER/space/edit,
resets idle timeout on edits, and submits on CONFIRM. `wait_for_confirm()` uses
a five-second shutdown window. Ordinary submenus drain stale events before
speaking, preserve choices during the prompt, and wait after speech. The 1.8-second
settling interval avoids delayed firmware letters becoming voice input.

Consumers are the current main-menu/mode helper, voice's shared handle, result
selector and mode-specific watchers. Translation wraps the same handle in
`TranslationButtons` and exposes a local queue; it does not open another port.
`voice._get_serial()` can lazily open its own connection for standalone use if
none was injected. This fallback is not permission for a gateway to do likewise.
Two serial readers steal bytes, and competing consumers of the same queue steal
events. Even one port therefore needs exclusive, state-aware consumer ownership.
Existing mode-scoped watchers are not a general event subscription mechanism.

`_button3_stop_signal()` normally counts three presses with four-second gaps;
it accounts for CONFIRM as evidence of two clicks. A comment still describes an
older blocking firmware; the inspected firmware is nonblocking. Translation
uses its distinct triple-RAW exit window instead. Do not normalize these mappings
in a mobile adapter or change firmware in this phase.

## Audio output versus data-processing privacy

`tts._get_manager()` lazily creates one `TTSManager`, a 32-item queue and one
worker. `_Utterance` snapshots text, language, output device and policy at enqueue.
The worker re-enters `processing_session(item.policy)`; thread-local defaults
cannot erase the caller's policy. Queue insertion waits at most one second;
blocking speech defaults to 120 seconds, routed result speech to 300 seconds.
Stop/flush and completion errors propagate through the public APIs. gTTS uses
explicit connect/read timeouts and failure backoff; offline synthesis uses
pyttsx3/native speech. Public playback may fall back to system default output.

`require_private_output()` demands an enumerated ALSA output distinct from the
speaker. Private/named-earphone playback retries only on that route and raises
`AudioRoutingError` if unavailable. macOS cannot establish this private route.
`speak_document_with_privacy_check()` chunks results (default 600 characters),
asks **after processing**, and uses per-utterance devices. PRIVATE/NORMAL return
strings here mean earphones/speaker only; a timeout means no result playback.
Live translation has separate sounddevice streams, outside the TTS result queue.

`ProcessingPolicy` in `privacy_policy.py` is immutable:
`PUBLIC = (private=False, allow_cloud=True, allow_persistence=True)` and
`PRIVATE = (True, False, False)`. ContextVar tokens restore enclosing state;
`session_thread()` copies context to worker threads. `PrivateAudio` also enters
PRIVATE policy, but ordinary `run_mode()` starts PUBLIC and the current UI has
no private-processing question. Private calls restrict OCR/STT/AI/embedding,
reranking/vector cloud calls and persistence; private voice uses temporary files
and cleanup. This is not a claim that temporary storage never touches disk or
that OS encryption/third-party behavior has been validated. `PrivateLogFilter`
redacts logs while in private context; context propagation must cover every new
worker and handler. No phone may silently downgrade policy or export private
content. Do not equate earphone playback with local processing or no retention.

## AI, retrieval, ingestion and storage

`ai_query.ask_ai()` performs sequential Groq/OpenAI fallback, then Gemini, then
the installed local llama-cpp-python model. PRIVATE calls bypass RAG/cloud and
use the local model with supplied context. Offline inference is serialized by
a nonblocking lock. With no explicit context, public calls lazily construct
`get_rag_pipeline()` and retrieve up to three context chunks. An existing library
with no supporting result causes abstention; no usable pipeline can still yield
a general answer. `RAGPipeline.ask_question()` instead calls `GeminiAgent`
directly; that agent has no local generator and returns unavailable when offline
or private. These paths must not be described as identical offline services.

| Component | Confirmed implementation |
| --- | --- |
| `Embedder` | Default local `all-MiniLM-L6-v2`, local-files-only SentenceTransformer loading, usual dimension 384 (queried from model); configured Gemini model/dimension from `GEMINI_EMBEDDING_MODEL` / `GEMINI_EMBEDDING_DIMENSION`, default 768. Bounded 512-entry cache keyed by model identity/text |
| Embedding fallback | Gemini initialization can select local if initialization is unavailable. Once cloud space is active, request failure/privacy denial returns empty vector; it does **not** switch to local vectors in that index. `index_identity` hashes provider/model/dimension. Cached public cloud vectors are not evidence of private-session network use |
| `VectorStore` | In-memory FAISS `IndexFlatL2` or NumPy cosine fallback; BM25Okapi if installed, RRF with constant 60, lexical overlap when no dense results. Metadata filtering. Optional Pinecone is explicit `vector_store_type: pinecone`, policy/key gated, model namespace; retains local committed data on cloud failure |
| `Retriever` | Fetches `max(3*k,10)` candidates, optional permitted Cohere `rerank-v3.5`, otherwise candidate order; adds source labels from tags. No measured ranking quality established |
| Persistence | `data_directory()` defaults to checkout `runtime/`. Active indexes: `runtime/vector_store/<index_identity>/snapshot.json`, previous snapshot, `.write.lock`; original sources: `runtime/vector_store/sources/<source_id>.json`. Other configured roots resolve relative to repository. Legacy `data`/`models` symlinks are not required for new state |
| Integrity | Batch checks exact row/text/tag/dimension alignment and finite values, stable text/tag hashes, thread lock plus fcntl writer lock, fsync/atomic snapshot replace and previous-generation recovery. Model/dimension mismatch refuses incompatible load/write. FAISS rebuilt from snapshots; `index.faiss` and JSON/NumPy names remain legacy paths. Pickle is never loaded |
| `RAGPipeline.index_document()` | Policy blocks persistent indexing. Recursive boundary chunks default 500 characters, overlap parameter 50 used for hard slicing rather than guaranteed overlap everywhere. Source JSON archived before embedding; failed embeddings may leave source archive but no committed vector batch. Identical source/tags give stable IDs |
| `index_file()` | Only `.txt`, `.md`, `.text`, at most 5 MiB, regular files; UTF-8 with invalid bytes ignored. Infers standard/subject/chapter tags. Markdown images may be described by Gemini; remote URLs/path escapes skipped. Private policy blocks cloud description and persistent indexing. Not a PDF/image-upload parser |

A **PLANNED** Android document adapter must authenticate the sender, bind content
to policy before reading/conversion, validate file type/size, stage in a confined
directory, sanitize names/image paths, and explicitly convert PDF to supported
text with provenance and limits in a later phase. It must not pass an uploaded
path directly to `index_file()`, expose arbitrary host paths, promise PDF support
today, or regenerate existing indexes. Model-space changes require separate,
explicitly validated ingestion; Phase 0 performs none.

## Documentation discrepancies and repository hygiene

| Existing statement | Source-level finding for this checkout |
| --- | --- |
| README/CLAUDE: all modules are isolated and never import each other; nested `Blindterminal/` paths | Shared imports exist (`privacy_policy`, `tts`, `config_loader`, gesture's object camera helper); the application is rooted here. Preserve actual dependencies rather than refactoring to match the old prose |
| README/embedder docstrings: automatic per-request cloud-to-local embedding fallback | Active cloud embedding identity is retained on failure; README's disk FAISS/NumPy description predates snapshot persistence |
| CHANGES: racing AI providers, Mode 7 labelled Translate, earlier `bone_device` and config claims | `ask_ai()` now sequential; Translate is Mode 4; wired earphones replace the old bone name. Defaults are canonical example plus code, not historical device settings |
| CHANGES: malformed settings always degrade to defaults | Missing file/JSON read errors can return defaults non-strictly; `validate_settings()` errors propagate, and `main()` requires strict configuration |
| Readiness review: 164 tests, reproduced unsafe GPS/audio/index behavior | Explicitly a dated baseline before later fixes. Current source has protections described above. Its old counts and failures are not current test results or proof that all release gates are closed |
| Button/voice comments describe blocking older Pico firmware or double-click live stop | Current firmware nonblocking; Mode 4 uses `TranslationButtons` triple-press exit. Mode-specific controls remain authoritative |

Before Phase 0, tracked artifacts already included 20 WAV files, five application
JPEG/PNG files, 20 `.pyc` files, `.DS_Store`, `logs/main.log`, backup Python files,
and a noncanonical `config/settings.` path. These are hygiene concerns, not new
deliverables; their contents/history were not copied into this audit. Existing
CHANGES reports historical credential exposure: that report is not independently
verified here, and no secret value was printed. Ignoring a path cannot untrack
history. No cleanup, history rewrite or credential operation is authorized here.
`data` and `models` are currently dangling symlinks; they remain untouched.
`config/settings.json` and `.venv` are absent locally; nothing was generated.

Existing ignore rules cover canonical settings, `.env`, Python environments,
models_local, runtime/cache/log/audio/images, and node_modules. Phase 0 adds only
Android/gateway development-artifact/secret patterns, preserving earlier rules.
See the baseline and handoff for actual failures and unverified hardware gates.
