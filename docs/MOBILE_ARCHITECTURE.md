# Mobile extension architecture — Phase 0

Status: **DESIGN ONLY**, 8 November 2026. The Android source scaffold and gateway
README add no terminal runtime behavior. Every connection, broker, mobile feature
and operating-state transition below is **PLANNED**, requiring implementation and
validation in later phases. Current source evidence is in
[the repository audit](MOBILE_PHASE0_AUDIT.md).

```text
                 ANDROID COMPANION
             Kotlin / Android — SCAFFOLD
                        |
             FUTURE MOBILE TRANSPORT
          BLE + Local Wi-Fi — PLANNED
                        |
                FUTURE PI GATEWAY
                     PLANNED
                        |
              FUTURE COMMAND BROKER
                     PLANNED
                        |
              EXISTING ORCHESTRATOR
                      main.py
                        |
           +------------+------------+
           |                         |
       modules/                  services/
           |                         |
   Hardware / Input            AI / RAG / Data
           |
    Raspberry Pi + Pico
```

## Responsibilities and boundaries

| Layer | Responsibility | Boundary |
| --- | --- | --- |
| Existing terminal | Physical input, mode selection/execution, camera/microphone, speaker/earphone output, local and existing online inference, existing RAG, core privacy enforcement, storage and shutdown | Remains independently startable with `.venv/bin/python main.py` after existing provisioning. No new Android/gateway requirement, source relocation, algorithm change or startup-service change |
| Future broker — PLANNED | Normalize permitted mobile and physical requests, admit one operation, serialize resource ownership, mediate cancellation, track status/results and deduplication | Lives at the terminal execution boundary. Only execution owner invokes `run_mode()`. Must preserve profile checks, nested gesture sessions, processing policy and physical choices |
| Future Pi gateway — PLANNED | Authenticate, associate phones, validate protocol/capabilities/permissions, manage transports, forward permitted requests, return sanitized status/results | Owns no Pico reader, camera, microphone, TTS queue, mode worker or AI pipeline. Must not import/start another copy of main, dynamically import requested modules, or accept shell commands |
| Future Android app — PLANNED | Accessible user controls, discovery/pairing, explicitly authorized phone services, document selection/upload, preferences, connected-service presentation and local mobile state | No transfer of existing Pi AI/RAG processing into Android. Phone service permissions are separately granted; pairing alone grants none |

The Pi remains authoritative for release capabilities, policy, lifecycle and
operation outcome. The phone's connectivity indicator cannot certify that a mode
is available, a model installed, an action completed, or a route safe. Gateway
crashes must be contained from terminal execution; the exact future IPC/process
boundary still needs design and tests. No IPC implementation exists in Phase 0.

## Capability and connectivity matrix

"Conditional" means required software/model/hardware must already be provisioned.
Existing implementations were inspected; hardware validation was not performed
in this phase. Test-file references show software coverage, not field readiness.
No accuracy or latency claims are inferred from test presence. Current execution
results and limitations are in [the baseline](MOBILE_PHASE0_TEST_BASELINE.md).

| Capability | Existing terminal capability / implementation status | Terminal offline | Terminal online | Future Android dependency | Required hardware/model | Validation status / evidence |
| --- | --- | --- | --- | --- | --- | --- |
| Morse input | IMPLEMENTED, serial events and keyboard fallback | Yes, conditional | Same | None | Pico/USB/pyserial or TTY | `test_pico_firmware.py`, `test_button_prompts.py`, `test_core_regressions.py`; synthetic events; no attached Pico validation |
| OCR reading | IMPLEMENTED, Mode 1 | Conditional Tesseract; optional Surya | Configured Gemini, then local fallback | None | Camera/rpicam or USB, OpenCV, OCR engine/languages | OCR/guidance/small-text test files; representative camera accuracy still unverified |
| Voice assistant | IMPLEMENTED, Mode 3 | Conditional local STT + local LLM + TTS | Google recognition, configured AI fallback | None | Mic/arecord, language-specific Vosk or Sphinx, GGUF/llama-cpp-python, audio | Voice ask/follow-up and release tests; physical mic/audio/cloud not validated |
| AI question answering | IMPLEMENTED, Modes 2/3 and optional explanations | Conditional local model | Groq/OpenAI/Gemini sequential fallbacks | None | Typed/Morse/voice input; provisioned model or provider | `test_result_workflow.py`, core/release tests; no live-provider or answer-quality evaluation |
| RAG retrieval | IMPLEMENTED, lazy pipeline | Conditional local index/model; BM25/lexical degradation; direct GeminiAgent generation unavailable | Configured embedding, Pinecone and Cohere optional; public AI context path | None | Local embedding cache, model-compatible snapshots, optional FAISS/BM25 | Core/release index integrity and concurrent-write tests; no library regeneration or relevance benchmark |
| Translation | IMPLEMENTED, Mode 4 phrases and live | Conditional cached public phrase or installed local providers; exact phrasebook limited | Configured phrase services; Gemini live requires internet | None | en/hi/gu bundles, STT/TTS per language; mic/sounddevice for live | Translation product/session/live tests; arbitrary offline quality and live device audio unverified |
| Gesture recognition | IMPLEMENTED, Mode 5 | Conditional local classifier | Same recognition; invoked modes may need online services | None | Camera, MediaPipe classic/Tasks and task bundle when required | `test_gesture_product.py`; no hardware/user study; unsafe macOS Tasks opt-in remains restricted |
| Object detection | IMPLEMENTED, Mode 6 object/position announcements | Conditional local YOLO | Same; runtime download disabled by default | None | Camera, weights, Ultralytics | `test_object_detection_product.py`; no distance/path-safety validation |
| GPS functionality | IMPLEMENTED, Mode 7 gated off by default | Fresh hardware coordinates only, conditional | Address/route summary if mode/navigation explicitly enabled | None | Valid UART GPS fix, internet for geocoding/route | `GPSReleaseTests`; no pedestrian guidance, progress loop or field validation |
| Confidential output | IMPLEMENTED, per-result output selector / Mode 8 demo | Conditional local synthesis and verified routes | PUBLIC synthesis can use cloud; output selection independent of policy | None | Two distinct ALSA outputs/headset; unavailable privately on macOS | Release/result/TTS tests; one pygame test hangs locally; no physical isolation validation |
| Mathematics | IMPLEMENTED, Mode 9 local grammar plus labelled AI fallback | Conditional SymPy; typed input needs no mic | Unsupported word problems may use existing AI chain | None | SymPy; mic/STT only for voice | `test_math_solver_product.py`; software exact-result checks, no user/hardware study |
| Document synchronization | PLANNED; local text ingestion already exists, mobile sync does not | Future authenticated local transfer only | Same plus separately permitted connected services | Required for mobile-origin files | Future Wi-Fi adapter/conversion/staging | Not implemented/tested; current `index_file` accepts only text/Markdown up to 5 MiB |
| Phone notifications | PLANNED | Only future phone/local events within granted permissions | Connected phone services would need their own connectivity | Required | Phone and explicit service/OS permission | Not implemented/tested |
| Phone-assisted navigation | PLANNED | Availability undecided; no offline route promise | Future phone/provider availability dependent | Required | Phone sensors/location permission and separately validated routing | Not implemented/tested; does not enable terminal Mode 7 |
| Locally scheduled reminders | PLANNED | Intended local scheduling subject to persistence/lifecycle design | Internet must not be required for a supported local schedule | Ownership on phone/Pi remains undecided | Future scheduler/storage and output permission | Not implemented/tested |
| Emergency communication | PLANNED | No emergency delivery promise without a working communication path | Future phone/network/service dependent | Required for proposed phone relay | Phone service permission and available network | Not implemented/tested; pairing is no emergency-service guarantee |

## Proposed operating states — all PLANNED

These describe pairing plus public-internet reachability, separately from busy,
model availability, processing policy, and terminal health. They are not new
`app_mode` or `release_profile` settings. Local Wi-Fi is not proof of internet.

| State | Allowed future operations | Limits |
| --- | --- | --- |
| `STANDALONE_OFFLINE` | Existing physical/TTY functions with provisioned local dependencies | No gateway/phone needed. No cloud live translation, remote geocoding, or absent models; offline does not imply explicit PRIVATE/no persistence |
| `STANDALONE_ONLINE` | Existing terminal functions with current cloud-to-local policy | Internet does not enable disabled modes or unavailable hardware; local fallback stays conditional |
| `PAIRED_LOCAL` | Existing local functions plus future authorized BLE controls and local Wi-Fi transfers/status | Neither BLE nor LAN requires internet for supported local operations. Paired phone internet is not silently used as Pi connectivity or permission to export data |
| `PAIRED_ONLINE` | Same plus separately permitted connected services | Authentication, permissions, release profile, resource ownership and private processing restrictions still apply |

Pairing is authorization state, not proof of an active transport. A disconnected
paired phone leaves the Pi fully usable; the broker must report transport health
separately. Treat gateway/phone loss as loss of the optional control channel,
not a command to stop or restart the terminal. New phone commands require fresh
authorization/capabilities after reconnection; no blind replay.

## Preservation guarantees to implement and validate later

1. **Terminal-only startup:** preserve installer, entrypoint and systemd example;
   gateway must be optional. Current strict config and Pico/TTY startup gates
   remain real restrictions; mobile-only boot would require later explicit work.
2. **No Android attached:** retain every existing enabled function and physical
   control. No import, wait, handshake or authentication dependency on Android.
3. **No internet:** use only installed fallback engines/models and reachable
   trusted local services; honest unavailable errors for unsupported work.
4. **Gateway crash:** isolate transport failure; leave terminal execution owner,
   input and output alive. A running task must have a documented disconnect policy
   rather than being killed automatically or replayed after restart.
5. **Reconnection:** resynchronize capabilities, active request status and
   permission state. Cached results obey policy and expiry; reconnect never
   authorizes a new task by itself.
6. **Hardware priority/cancel:** physical input must remain responsive and retain
   mode-specific mappings. Reserve a cancellation control path which does not
   wait behind queued work; no second event consumer or Pico connection.
7. **Conflicting commands:** one execution authority and one active resource
   session; reject conflicting requests as BUSY. Nested gesture dispatch stays
   in that same session. Release resources before another conflicting task.
8. **Privacy and persistence:** capture policy before processing, inherit across
   threads/events, enforce independently of output route, prohibit unauthorized
   phone results, and preserve source/index assets. Logging, deduplication and
   reconnect caches must not persist PRIVATE content.

These are design requirements, not results demonstrated by this scaffold.

## Android foundation and permanent UI contract

Phase 0 contains only a blank native Kotlin activity, manifest, resources and
Gradle configuration/wrapper. No transport, permission prompt, command, login,
cloud call or fake connected-device demonstration exists. The later preferred
stack is Jetpack Compose, MVVM/Clean Architecture, Hilt, Coroutines/StateFlow,
Room, DataStore, Android BLE APIs and OkHttp/Retrofit. Introduce those dependencies
only as their later-phase responsibility is implemented; a blank activity does
not need their service/data layers. Build limits are documented in
[android-app/README.md](../android-app/README.md).

Permanent requirements for all later screens:

- Solid colors only, absolutely no gradients; high-contrast content.
- Square rectangular button corners, no rounded buttons.
- Minimal, intuitive controls without decorative clutter or unnecessary animation.
- Full TalkBack support, meaningful labels, state announcements and accessible
  focus order; no unlabeled icon-only operation or color-only state.
- Touch targets at least 48 dp, scalable text and usable layouts with large fonts.
- English, Hindi and Gujarati localization; future user strings in resources.

Phase 0's blank screen is not an accessibility or localization acceptance test.
The launcher label has en/hi/gu resources, but finished screens and native-language
review remain future work. No claim of TalkBack validation is made.
