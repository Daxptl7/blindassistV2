# BlindAssist Android companion — Phase 0 scaffold

This is a blank native Kotlin activity, not a working companion. Opening it shows
an empty solid-white window. No discovery, pairing, BLE/Wi-Fi, remote command,
AI, document upload, notification, navigation, reminder, login or cloud feature
exists. The manifest requests no permissions and defines no services/receivers.
Terminal Python code does not import or launch this application.

## Toolchain and build

Pinned foundation: Android Gradle Plugin **9.3.3**, its built-in Kotlin support,
Gradle **9.5.0**, JDK **17**, compile/target SDK **37**, minimum SDK **26**.
The package/application ID `com.blindassist.companion` is provisional project
configuration, not a claim of store/domain registration.

The official [AGP 9.3 release notes](https://developer.android.com/build/releases/agp-9-3-0-release-notes)
list Gradle 9.5.0, SDK Build Tools 36.0.0, JDK 17 and support through API 37.
AGP's [built-in Kotlin guidance](https://developer.android.com/build/migrate-to-built-in-kotlin)
explains why a separate `org.jetbrains.kotlin.android` plugin is absent. These
stable release settings were checked on 8 November 2026. No Compose compiler or
other application framework dependency is needed for this blank activity.

Open **this directory** as a project in a compatible Android Studio installation,
with JDK 17 and Android SDK Platform 37 / Build Tools 36.0.0 provisioned. Configure
the SDK through Android Studio, an SDK environment variable, or ignored
`local.properties`; never commit a machine-specific `sdk.dir`. Then run:

```bash
./gradlew :app:assembleDebug
```

On Windows use `gradlew.bat :app:assembleDebug`. The wrapper initially downloads
Gradle and dependency resolution needs build-time network access; this is
independent of the future runtime requirement for local operations without
internet. The wrapper pins the official distribution SHA-256. Wrapper scripts
and JAR come unmodified from
[Gradle v9.5.0](https://github.com/gradle/gradle/tree/v9.5.0/gradle/wrapper),
with upstream license notices retained in the scripts/JAR. JAR SHA-256:
`497c8c2a7e5031f6aa847f88104aa80a93532ec32ee17bdb8d1d2f67a194a9c7`,
verified against the [official wrapper checksum](https://services.gradle.org/distributions/gradle-9.5.0-wrapper.jar.sha256).
The distribution checksum comes from
[Gradle's checksum endpoint](https://services.gradle.org/distributions/gradle-9.5.0-bin.zip.sha256).

**Local validation: Android build BLOCKED.** Java 17 is installed, but the
Android SDK, sdkmanager, adb and system Gradle were absent during Phase 0.
The complete wrapper is supplied; no SDK, build dependencies or system packages
were installed merely to claim a passing build. XML parsing, wrapper integrity
and shell syntax checks are not APK compilation or emulator/device validation.
See [the full baseline](../docs/MOBILE_PHASE0_TEST_BASELINE.md).

## Later implementation direction

Preferred later stack: Jetpack Compose, MVVM/Clean Architecture, Hilt,
Coroutines/StateFlow, Room, DataStore, Android BLE APIs and OkHttp/Retrofit.
Add each only when needed; there are no empty service/database/domain classes
pretending to implement features. Pi AI/RAG remains on the terminal.

Permanent UI constraints: no gradients; solid colors; square rectangular buttons
with no rounded corners; minimal high-contrast layout; full TalkBack labels,
state and focus support; at least 48 dp touch targets and scalable text; English,
Hindi and Gujarati; no unnecessary animation/decorative clutter. The three app
label resources are a starting point, not a validated localization or TalkBack
result. Future Compose themes must override rounded component defaults.

See [the architecture and capability contract](../docs/MOBILE_ARCHITECTURE.md)
and [the Phase 1 handoff](../docs/MOBILE_PHASE0_HANDOFF.md) before adding behavior.
Never add permissions or an active transport as part of this Phase 0 scaffold.
