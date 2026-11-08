# Phase 2 → Phase 3 handoff

8 November 2026. Implemented in the user-confirmed local `Daxptl7/blindassistV2`
checkout on `feature/android-phase2-gateway`. Origin was empty; the user explicitly
authorized current local source. No push, migration, service installation or
Android feature work occurred. Read [architecture](MOBILE_PHASE2_GATEWAY.md),
[API](MOBILE_PHASE2_API.md), [security](MOBILE_PHASE2_SECURITY.md) and
[actual tests](MOBILE_PHASE2_TEST_RESULTS.md). Earlier phase documents remain
historical; this implemented API/IPC is the Phase 2 contract.

## Delivered modules

| Files | Responsibility |
| --- | --- |
| `gateway/config.py`, `authentication.py`, `errors.py` | Loopback-only settings, private rotating credentials, allowlists, safe errors |
| `gateway/ipc_protocol.py`, `ipc_client.py`, `ipc_server.py` | Typed bounded versioned UDS bridge to existing broker |
| `gateway/api.py`, `schemas.py`, `server.py` | Six HTTP routes, strict boundary, independent server entry point |
| `main.py` | Opt-in IPC startup/cleanup, existing execution owner retained |
| `requirements-gateway.txt`, `requirements-test.txt` | Optional runtime dependencies and HTTP test dependencies |
| `gateway/settings.example.json`, `deploy/blindassist-gateway.service.example` | Operator-reviewed examples; no installation/enabling |
| Five `tests/test_gateway_*.py` files and `tests/gateway_support.py` | Real broker/socket tests, fake handlers, hardware/import/lifecycle isolation |
| `tests/test_mobile_dispatch_regression.py` | Existing AST harness updated for optional helpers/global |
| `scripts/smoke_gateway.py` | Real Uvicorn subprocess, curl, UDS, broker and gateway crash/restart smoke |
| `gateway/README.md`, five `docs/MOBILE_PHASE2_*.md` files | Current setup, contract, security, evidence and handoff |

The gateway owns only IpcClient; main owns IpcServer and CommandBroker. Only main
claims/finishes modes. IPC requires explicit `BLINDASSIST_IPC_ENABLED=1`, matching
private directory and same UID. Gateway absence/death never closes the broker,
cancels physical work or starts a second terminal. Existing input/config gates
remain required. There is no Android-to-device working product claim.

## Readiness and outstanding gates

Local authenticated clients can read actual broker status/capabilities, submit
approved commands, inspect state and cancel pending work. Deduplication survives
gateway restart within live-broker retention. All 42 Phase 2 tests and the real
loopback smoke pass. Diagnostic comparison finds no new failures; default-suite
hang, 11 baseline failures and nine environment conflicts remain documented.

The local software interface is ready for subsequent design, with these limits:

- Validate actual Pi/Pico startup with IPC disabled/enabled, gateway kill during
  real modes, partial Morse priority, physical stops, camera/mic/TTS ownership,
  private processing and offline use. Current evidence uses fake handlers.
- Review/test the optional service and shared `/run` provisioning on Linux.
  No systemd service was exercised on this macOS host.
- Resolve the existing suite/environment problems separately before release.
- Design encrypted authenticated phone pairing, consent and revocation before
  any network exposure. A loopback bearer credential is not a LAN design.
- Preserve stable principal/request IDs on reconnect. Treat transport loss as
  ambiguous and respect finite retention; no persistent exactly-once guarantee.
- Active modes currently reject remote cancellation and require device input.
  Any later input/private-result adapter belongs at the execution-owner boundary.

Android UI, BLE, Wi-Fi file transfer, reminders, navigation, notifications and
document synchronization remain outside Phase 2. No later phase was started.
