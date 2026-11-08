# Phase 2 security and privacy

This is a local development transport, not phone pairing, TLS or LAN exposure.
The bind address must be literal loopback; actual peer/Host are checked, proxy
claims ignored, Origin/query parameters rejected, browser UI/CORS absent.
An encrypted authenticated association design is required before phone/network
access. Plaintext bearer testing must stay on loopback.

## Credentials and authorization

`python3 -m gateway.server --init-credentials` explicitly creates the configured
private `credential.json` (default `runtime/mobile-gateway/credential.json`).
Schema: version 1, random 16-hex principal ID, `secrets.token_urlsafe(32)` token,
`allowed_commands`, `allowed_modes`. No token is printed or hardcoded. Initial
publication never overwrites an existing credential. Directory/file ownership
must match the process UID with exactly 0700/0600 permissions. Symlink,
nonregular and hardlinked files fail closed; reads are bounded. Runtime files
are Git-ignored. Never put credentials in tracked examples or reports.

Rotate with `--rotate-credentials` using the same settings/interpreter. A 0600
temporary file is atomically replaced; principal/allowlists remain stable.
Protected requests re-read the file, so the old token fails subsequent
authentication without restart. In-flight authenticated requests may finish.
Deleting the file revokes new protected requests (503); terminal use continues.
Missing/insecure credentials fail server startup. Rotation is not a transaction
with the in-memory request ledger.

Authorization is an explicit subset of GET_STATUS, GET_CAPABILITIES, START_MODE,
CANCEL_OPERATION plus a START_MODE subset. The initial mode allowlist is 1–9;
the actual broker still rejects unknown/disabled registry entries. Operators
may restrict lists in the private file while preserving 0600. Authorization
occurs before IPC. Headers use `hmac.compare_digest`; malformed/duplicate bearer
values fail. Request bodies cannot choose identity or physical source. Stable
principal namespaces prevent cross-principal/physical query or cancellation.

Avoid placing tokens in curl arguments/history. A temporary private curl config
can read the local credential without printing it (default directory example):

```bash
python3 - <<'PY'
import json, os
from pathlib import Path
directory = Path('runtime/mobile-gateway')
record = json.loads((directory / 'credential.json').read_text())
fd = os.open(directory / 'curl.conf', os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
with os.fdopen(fd, 'w') as stream:
    stream.write('header = "Authorization: Bearer ' + record['token'] + '"\n')
PY
curl -q --config runtime/mobile-gateway/curl.conf -fsS http://127.0.0.1:8765/api/v1/device/status
```

Delete this extra secret copy after testing and regenerate it after rotation.
The automated smoke uses temporary 0600 configs, prints only outcomes and removes
them. Never paste tokens into issue reports or logs.

## Local trust, limits and privacy

The 0700 directory/0600 socket isolate IPC from other unprivileged UIDs. Both
processes use the same dedicated UID. That UID and root are trusted: account
compromise exposes its socket and credential. IPC principal_id is a trusted
local adapter field, not an independent bearer-authenticated boundary. No shell,
Python evaluation, arbitrary paths, device shutdown, document deletion or remote
configuration operations exist.

HTTP/IPC enforce bounded bodies/frames, exact schemas, duplicate/nonfinite JSON
rejection, deadlines and bounded concurrency. HTTP also limits incomplete header
events and keepalive. An authenticated user can fill the finite ledger, which
fails closed. No comprehensive account rate limiter or durable anti-replay store
exists. This is not production pairing or multi-user RBAC.

Gateway access logs are disabled. New terminal IPC logs are generic lifecycle
messages. Public errors are static codes; provisioners print no secrets.
Standard Uvicorn lifecycle logs contain process/address metadata. Gateway logs
and responses contain no raw requests, documents, voice transcripts, private
prompts, OCR answers or handler results. Existing terminal logging was not
redesigned in this phase.

Existing processing_session, cloud/persistence restrictions, confidential flow,
offline policy and audio output remain under terminal handlers. Gateway commands
cannot grant cloud permission, pass input text, choose audio or disclose results.
Starting a mode follows its existing policy; phone consent/private-session
propagation requires later review. Earphones do not imply local-only processing.
