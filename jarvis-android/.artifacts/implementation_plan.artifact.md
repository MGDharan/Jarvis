# Implementation Plan - Fix Gradle Sync and App Logic

This plan addresses the Gradle sync failure and several logic bugs in the Android app.

## Proposed Changes

### Build Configuration
#### [NEW] [gradle-wrapper.properties](file:///F:/jarvis/jarvis/jarvis-android/gradle/wrapper/gradle-wrapper.properties)
Create the Gradle wrapper configuration to use a stable version (8.6) and resolve the download error for version 9.3.0.

#### [MODIFY] [gradle.properties](file:///F:/jarvis/jarvis/jarvis-android/gradle.properties)
Add modern Android properties to ensure build consistency.

### App Logic & Stability
#### [MODIFY] [MainActivity.kt](file:///F:/jarvis/jarvis/jarvis-android/app/src/main/java/com/jarvis/remote/MainActivity.kt)
- Move `voiceRecorder` initialization to `onCreate` to prevent `UninitializedPropertyAccessException`.
- Wire up `FileDownloader` to handle incoming file transfer metadata.

#### [MODIFY] [QRPairingScreen.kt](file:///F:/jarvis/jarvis/jarvis-android/app/src/main/java/com/jarvis/remote/ui/screens/QRPairingScreen.kt)
- Ensure camera analysis results are processed safely.

## Verification Plan
### Automated Tests
- Run `gradle_sync` to verify the build configuration is fixed.
- Run `app:assembleDebug` to ensure the project compiles.

### Manual Verification
- The user should verify that the app no longer crashes on startup or during destruction.
- The user should verify that file downloads now trigger correctly when receiving a transfer message from the server.
