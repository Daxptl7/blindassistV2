# BlindAssist optional local gateway — Phase 2

The independent FastAPI process binds to `127.0.0.1:8765` by default and reaches
the existing terminal-owned Phase 1 broker through a private Unix socket.
It never imports `main.py`, opens hardware, executes modes or starts a terminal.
The terminal socket is disabled unless `BLINDASSIST_IPC_ENABLED=1`.

- [Setup and architecture](../docs/MOBILE_PHASE2_GATEWAY.md)
- [Six-route API](../docs/MOBILE_PHASE2_API.md)
- [Credentials, authorization and privacy](../docs/MOBILE_PHASE2_SECURITY.md)
- [Actual test results](../docs/MOBILE_PHASE2_TEST_RESULTS.md)
- [Phase 3 handoff](../docs/MOBILE_PHASE2_HANDOFF.md)

Earlier phase documents describe their historical scope. Android, BLE, phone
pairing, LAN access, results transfer and document synchronization remain outside
Phase 2. Keep credentials and private runtime files outside version control.
