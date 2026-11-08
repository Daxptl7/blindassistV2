# BlindAssist mobile gateway — PLANNED

Phase 0 reserves this directory only. There is no Python service, listener,
transport, pairing logic, command execution, hardware import or dependency file.
The terminal starts using its existing instructions without this directory.

Later phases may add authentication, phone association, strict protocol
validation, BLE/local Wi-Fi adapters and sanitized status/results. Forward
permitted requests to a broker at the existing terminal execution boundary;
the gateway must never open the Pico serial port, take camera/microphone/audio
ownership, import/run another copy of `main.py`, invoke feature modules directly,
or initialize an AI/RAG pipeline. Failure or absence of the gateway must leave
physical terminal use independent.

The broker/IPC process boundary, identity provisioning and interactive mode-input
adapters still require design and validation. Protocol examples do not authorize
an implementation during Phase 0.

- [Verified current terminal architecture](../docs/MOBILE_PHASE0_AUDIT.md)
- [Planned boundaries and capability matrix](../docs/MOBILE_ARCHITECTURE.md)
- [Proposed protocol 1.0](../docs/MOBILE_PROTOCOL.md)
- [Phase 1 handoff and regression requirements](../docs/MOBILE_PHASE0_HANDOFF.md)

Keep credentials, local configuration, private document/audio staging and runtime
state outside version control. No device service/startup changes belong here in
Phase 0.
