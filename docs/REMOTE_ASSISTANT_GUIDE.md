# 📱 JARVIS Phone Remote Assistant — Complete User & Architecture Guide

This guide explains how to use and configure the **JARVIS Mobile Remote Assistant** for your Android phone, enabling voice control, remote file search, secure file transfer, real-time hardware telemetry, and proactive security alerts from your lab laptop.

---

## 🌟 1. System Overview

- **Host (Lab Laptop)**: Runs your existing Python JARVIS desktop application with PyQt6 HUD, Gemini Live, and local offline engines.
- **Client (Android Phone)**: Runs the native **JARVIS Android App** (Kotlin + Jetpack Compose) featuring a futuristic glowing orb, hold-to-talk voice interface, live telemetry gauges, and alert feed.
- **Network Link**: Encrypted WebSocket and HTTPS connection over your local WiFi or private **Tailscale** overlay network.
- **Zero Configuration Overhead**: Starts automatically whenever you click your JARVIS desktop shortcut. No separate servers, terminals, or scripts required.

---

## 🚀 2. Quick Start & Startup Workflow

### Laptop Startup
1. Click your normal **JARVIS desktop shortcut** (or run `python main.py`).
2. JARVIS boots up normally. In the system log, you will see:
   ```text
   SYS: Mobile Remote Gateway active.
   ```
3. The gateway is now running in the background on port `8765`.

---

## 📲 3. One-Time QR Pairing

1. On your JARVIS desktop HUD, click the **Remote Access** button.
2. An overlay appears displaying a dynamically generated **One-Time QR Code** and a 5-minute countdown.
3. Open the **JARVIS Android App** on your phone.
4. Scan the QR code (or paste the JSON payload if camera access is unavailable).
5. The phone and laptop perform an automated cryptographic handshake:
   - The laptop validates the short-lived pairing token.
   - The laptop assigns your phone a unique `device_id` and permanent `auth_token`.
   - The phone saves credentials to Android `EncryptedSharedPreferences`.
6. **Done!** The phone will now automatically connect to your laptop on launch. You will never need to scan the QR code again.

---

## 🛡️ 4. Device Management & Revocation

The laptop maintains all authorized devices in `config/authorized_devices.json`:

```json
{
    "version": 1,
    "devices": {
        "dev_a1b2c3d4e5f6": {
            "device_name": "Pixel 8 Pro",
            "device_model": "Android 14",
            "status": "authorized",
            "created_at": "2026-09-14T20:00:00"
        }
    }
}
```

### Revoking Access
To revoke a phone's access immediately:
- Run:
  ```powershell
  python -c "from remote.auth import device_auth_manager; device_auth_manager.revoke_device('dev_a1b2c3d4e5f6')"
  ```
- The gateway will **instantly drop the active WebSocket connection** and block all subsequent requests with `401 Unauthorized`.

---

## 🌐 5. Secure Remote Connection (Tailscale Setup)

To use your phone outside the lab without port forwarding:
1. Install **Tailscale** on your lab laptop and sign in ([tailscale.com](https://tailscale.com)).
2. Install **Tailscale** on your Android phone and sign in to the same account.
3. Your laptop will have a 100.x.y.z IP (e.g. `100.85.12.44`).
4. When you generate the pairing QR, JARVIS automatically detects your Tailscale IP and uses it for the gateway address.
5. All traffic between phone and laptop is end-to-end encrypted with WireGuard.

---

## 🗣️ 6. Remote Voice & Text Commands

Press and hold the glowing **HOLD TO TALK** orb (or type in the bottom bar):

| Command Example | What JARVIS Does |
|---|---|
| *"What is my CPU usage?"* | Returns real-time CPU, RAM, GPU, and Battery metrics. |
| *"JARVIS, find the Gaira folder."* | Searches configured directories and returns the exact folder path. |
| *"Send me the PDFs."* | Finds PDFs in the target folder, asks for confirmation, and transfers them. |
| *"Open Chrome."* | Launches Google Chrome on the laptop from the approved app allowlist. |
| *"Open VS Code."* | Launches Visual Studio Code on the laptop. |
| *"Turn on sentry mode."* | Arms the camera surveillance system. |
| *"Shut down the laptop."* | Triggers a **high-risk confirmation challenge**. |

---

## 📁 7. File Search & Transfer Security

### Directory Allowlist
Configured in `config/remote_config.json`:
- `D:/Projects`
- `D:/Documents`
- `D:/Datasets`
- `F:/jarvis`
- User Downloads and Documents

### Protection Guarantees:
- **Path Traversal Prevention**: `../` and directory escapes are strictly rejected.
- **System Directory Blocking**: `C:\Windows`, `C:\Program Files`, and `AppData` cannot be accessed.
- **Sensitive File Shielding**: `.env`, `api_keys.json`, private keys (`.pem`, `.key`, `id_rsa`) are blocked from discovery and downloads.

### Transfer Verification:
- Large folders are automatically packed into temporary zip archives.
- SHA-256 checksums are calculated and verified on download.
- Temporary transfer packages in `data/transfers/temp/` are automatically deleted after 15 minutes.

---

## ⚠️ 8. High-Risk Action Confirmation (Shutdown / Restart)

To prevent accidental power-offs or rogue commands:
1. User says: *"JARVIS, shut down my lab laptop."*
2. Laptop responds: *"Shutdown will power off the lab laptop. Please confirm."* and creates a 60-second challenge.
3. Phone displays an alert dialog:
   ```text
   ⚠️ HIGH-RISK ACTION CONFIRMATION
   Shutdown will power off the lab laptop. Please confirm.
   [ CONFIRM SHUTDOWN ]   [ CANCEL ]
   ```
4. Only when the user taps **CONFIRM SHUTDOWN** will the laptop initiate power off.

---

## 🚨 9. Camera & Proactive Push Notifications

When Sentry Mode is active on the laptop:
- Motion detected → Camera captures timestamped snapshot.
- Push notification sent to phone:
  ```text
  🚨 Motion Detected in Lab
  Movement detected at 20:15:30. Snapshot captured.
  ```
- Notifications also fire for:
  - 🔋 Low battery (< 20%)
  - 🌡️ High CPU / GPU temperature
  - 🤖 ML training completed / failed
  - 📁 File transfer completed

---

## 🧪 10. Local Simulator Test Client

You can test phone ↔ laptop communication on your computer without an Android device:
```powershell
python -m remote.test_client
```
- Emulates the phone pairing handshake.
- Connects to the WebSocket.
- Streams live telemetry in the terminal.
- Allows typing voice queries, searching files, and confirming challenges.

---

## 🔧 11. Android Project Setup (Android Studio)

1. Open **Android Studio**.
2. Select **Open** and choose:
   ```text
   f:\jarvis\jarvis\jarvis-android
   ```
3. Allow Gradle to sync dependencies (`OkHttp`, `Compose`, `CameraX`, `ML Kit`).
4. Connect your Android phone via USB (or use an emulator).
5. Click **Run 'app'** to install JARVIS on your phone.
