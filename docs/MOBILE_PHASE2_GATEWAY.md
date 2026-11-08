# Phase 2 local communication gateway

8 November 2026. Authorized checkout:
`/Users/daxpatel/Desktop/Collage/Reseach/BlindAssist/blindassistv2/blindterminalv2`.
Origin: `https://github.com/Daxptl7/blindassistV2.git`, repository ID 1450023102.
The remote was empty (commits API 409); the user explicitly authorized using the
current local source. Start: `39583585fb570ca30e6586ddc47d817a79be454b`.
Branch: `feature/android-phase2-gateway`. No push or migration occurred.

## Verified architecture

```text
local client -> FastAPI gateway process (loopback only)
 -> IpcClient -> private Unix socket -> IpcServer inside terminal process
 -> existing CommandBroker.submit / get_status / get_capabilities / get_operation
 -> existing terminal menu owner claims work -> run_mode -> existing MODE_MAP
```

`main.py` owns the Pico singleton and all mode execution. Its registry contains
OCR, Morse, Voice Ask, translation, gesture, object detection, GPS, confidential
processing and math. Existing `modules/` and `services/` retain camera, voice,
TTS/audio, privacy policy, AI and RAG ownership. No feature module, handler,
firmware, device configuration or existing terminal service was changed.
See the [Phase 1 contract](MOBILE_PHASE1_HANDOFF.md).

Only optional IPC startup in `main`, cleanup in `shutdown`/dispatcher disable,
two helpers and one global were added to the orchestrator. Imports occur inside
the opt-in helper; terminal IPC needs only standard Python libraries. The
terminal does not need FastAPI/Pydantic/Uvicorn. The server calls only public
thread-safe broker methods, never `take_next`, `finish`, `run_mode`, hardware
handlers or serial readers. Interactive modes still use actual physical input.
Closing IPC never closes the broker or terminal resources.

## Local setup

These are operator instructions; no environments/services were installed here:

```bash
python3 -m venv runtime/gateway-venv
runtime/gateway-venv/bin/python -m pip install -r requirements-gateway.txt
runtime/gateway-venv/bin/python -m gateway.server --init-credentials
runtime/gateway-venv/bin/python -m gateway.server
```

Provisioning creates private `runtime/mobile-gateway/credential.json`, prints no
token and never overwrites an existing credential. Missing/insecure credentials
fail startup. Use the same interpreter with `--rotate-credentials` for rotation.
Protected requests re-read credentials; rotation needs no restart.

The operator independently sets `BLINDASSIST_IPC_ENABLED=1` before normal terminal
startup to enable IPC. Existing config/input preflight still applies. Without
opt-in the terminal stays standalone and protected HTTP calls return 503.
`GET /api/v1/health` checks only the gateway process.

`python3 -m gateway.server --settings gateway/config.local.json` accepts a
gateway-only JSON file based on `gateway/settings.example.json`. Overrides:
`BLINDASSIST_HOST`, `BLINDASSIST_PORT`, `BLINDASSIST_IPC_DIRECTORY`,
`BLINDASSIST_CREDENTIAL_DIRECTORY`. Host must be a literal loopback address.
Both processes need the same UID and IPC directory. The terminal reads only
IPC opt-in/directory; HTTP settings do not configure terminal modes/privacy.
Use short absolute socket paths, at most 100 encoded bytes.

## IPC and resource limits

Default: `/tmp/blindassist-ipc-<uid>/terminal.sock`. Owned directory must be 0700;
socket and exclusive server lease file use 0600. Symlinks, wrong ownership,
unexpected files and insecure permissions fail closed. Live sockets are
preserved. An owned stale socket is removed only after connection refusal under
the exclusive lease. Shutdown removes only the server's own socket inode.

Protocol version `1.0`: four-byte network-order frame length, then UTF-8 JSON,
one request per connection with write EOF. Requests/responses are limited to
4096/65536 bytes. Exact envelope fields: `protocol_version`, `action`,
`principal_id`, `payload`. Actions: STATUS, CAPABILITIES, SUBMIT, OPERATION.
Unknown actions/keys, duplicate JSON keys, nonfinite numbers, trailing bytes and
invalid types are rejected before broker submission. Only approved Phase 1
command fields can enter the broker. The socket trusts same-UID local adapters.

Defaults: eight concurrent HTTP requests/IPC workers, two-second body and IPC
deadlines, bounded backlogs, two-second HTTP keepalive. Socket reads use absolute
deadlines including EOF. A fixed error frame can get an additional 50 ms write
budget. Overflow IPC connections close immediately. No automatic command retries,
mode execution, terminal spawning or broker shutdown occur in the client.

## Deployment and failure isolation

`deploy/blindassist-gateway.service.example` is uninstalled and has no install
target or terminal Requires/BindsTo/PartOf relationship. It uses a non-root UID,
restrictive umask, read-only service filesystem and private devices. Review
account/paths before use. No service was installed, started or enabled.

The existing terminal example uses `PrivateTmp=true`. Separate services must
use a shared `/run/blindassist-gateway` directory, owned by the terminal UID,
0700, explicitly configured in both environments and provisioned before terminal
startup. `/run` is ephemeral; operator boot tooling must recreate it. Do not
assume both services see the same `/tmp`. The gateway service deliberately does
not own/remove the terminal's runtime directory on shutdown.

Gateway restart reconnects to the same live broker; gateway death never stops
physical use. HTTP/UDS communication needs no Internet; mode processing retains
existing online/offline policy. Disable terminal IPC independently when removing
the gateway. See [security](MOBILE_PHASE2_SECURITY.md) and [tests](MOBILE_PHASE2_TEST_RESULTS.md).
