# Phase 3 → Phase 4 handoff

**Canonical repository:** `https://github.com/Daxptl7/blindassistV2.git`.

The repository contains a Phase 3 Android companion foundation only. The original Raspberry Pi backend must be imported or supplied via an explicitly planned integration, not invented.

## Before BLE implementation

1. Verify the actual Raspberry Pi code, Phase 1 dispatcher and Phase 2 gateway locations and working state.
2. Validate Android project build on Android SDK 35 and JDK 17; generate missing Gradle Wrapper.
3. Verify BLE availability on the target Pi and the chosen Linux GATT service design.
4. Define authenticated pairing, bond/association, GATT characteristics, replay protection, protocol version and MTU.
5. Add only necessary Android Bluetooth permissions with API-level handling.
6. Implement a BLE-backed `DeviceRepository`, replacing `UnavailableDeviceRepository` through DI.
7. Provide real state and capability discovery; do not fabricate `Connected`.
8. Preserve standalone terminal behavior and single ownership of Pico serial.
9. Test disconnect/reconnect, permission denial, TalkBack pairing and malformed BLE payloads.

Phase 4 does not include bulk PDF transfer or other Wi-Fi features.
