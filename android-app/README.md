# BlindAssist Android companion — Phase 3 foundation

The native Kotlin/Compose companion contains accessible onboarding, disconnected
home/status, settings, and feature entry screens with English, Hindi and Gujarati
resources. It uses MVVM/StateFlow, Hilt and DataStore. Pairing, BLE/Wi-Fi,
remote terminal control and result transfer are not implemented; device status
remains truthfully unavailable until a later authenticated transport is added.
The standalone Raspberry Pi terminal and optional gateway now coexist in this
repository and remain independent of Android.

## Toolchain and checks

The preserved Phase 3 version catalog uses AGP 8.7.3, Kotlin 2.0.21, compile/target
SDK 35, minimum SDK 26, and Java 17. The inherited wrapper is aligned to Gradle
8.9, matching the existing Android CI, with the official distribution checksum.
Open this directory in Android Studio and provision SDK 35 / Build Tools 35.0.0.
Keep local SDK paths and signing/credential files outside Git.

```bash
./gradlew :app:assembleDebug :app:testDebugUnitTest :app:lintDebug --no-daemon
```

The merge host has Java 17 but no Android SDK; APK, lint and device/TalkBack
validation remain blocked here. CI supplies Gradle 8.9 and the SDK separately.
See [the Phase 3 architecture](../docs/MOBILE_PHASE3_ANDROID_ARCHITECTURE.md),
[accessibility requirements](../docs/MOBILE_PHASE3_ACCESSIBILITY.md) and
[test limitations](../docs/MOBILE_PHASE3_TEST_RESULTS.md). Existing phase reports
are historical snapshots; this merge restores a wrapper, not proof of an APK.

[Gateway setup](../docs/MOBILE_PHASE2_GATEWAY.md) documents the loopback-only
Python service. It is not yet an Android network transport. No phone pairing or
later feature was added as part of merging the branches.
