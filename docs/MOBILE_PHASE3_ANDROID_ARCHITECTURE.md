# Phase 3 — Android architecture

Repository: `Daxptl7/blindassistV2` (dedicated Android companion repository).

This repository was empty before Phase 3 was initialized. **No Raspberry Pi terminal, Phase 1 broker or Phase 2 gateway code was present here.** Do not infer their existence.

## Added

- `android-app/`: single-module Android Kotlin/Jetpack Compose application.
- `MainActivity.kt`: onboarding, Home, Devices, Features, Settings and About navigation.
- `MainViewModel.kt`: state through StateFlow, actions through SettingsRepository.
- `SettingsRepository.kt`: DataStore-backed onboarding, appearance and language.
- `DeviceRepository` interface and `UnavailableDeviceRepository`: explicitly no transport.
- Hilt binding for the device repository.
- English, Hindi and Gujarati app strings.

## Integration boundary

The app never opens Pico serial, reads camera/microphone, imports the Raspberry Pi runtime or executes terminal modes. Phase 4 can provide a BLE-backed DeviceRepository while preserving the UI/ViewModel contract. Phase 2 API integration must be validated against the actual terminal repo separately.

## Build requirements

JDK 17, Android SDK 35, Gradle 8.9 with Android Gradle Plugin 8.7.3 and Kotlin 2.0.21. The current environment did not include Android SDK or Gradle; builds were **not run** here. Gradle Wrapper binaries/scripts are **not included** in this commit; generate them in an Android-ready environment using `gradle wrapper --gradle-version 8.9`, then run `./gradlew :app:assembleDebug`.

## Phase 3 scope

No Bluetooth, LAN access, device pairing, remote controls, notifications, SMS, GPS or file transfers. All connectivity screens report unavailable.
