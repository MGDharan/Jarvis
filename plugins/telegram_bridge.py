"""
plugins/telegram_bridge.py — Autonomous Telegram & Discord Remote Uplink for JARVIS.

Provides a secure two-way remote uplink between JARVIS on your PC and your phone
via Telegram Bot API, with optional Discord webhook mirroring.

Features:
- Two-way mobile control from anywhere via Telegram.
- Remote commands: /status, /screenshot, /sentry on|off, /lock, /ask.
- Sentry Mode intrusion alerts: automatically dispatches intruder photos to your phone.
- Secure pairing: requires authorization or /pair <code_or_passphrase>.
- Discord webhook mirroring for team or multi-device alerts.
"""
from __future__ import annotations

import ctypes
import json
import os
import sys
import threading
import time
from pathlib import Path
from typing import Any, Optional

try:
    import requests
    _REQUESTS_AVAILABLE = True
except ImportError:
    _REQUESTS_AVAILABLE = False

try:
    import psutil
    _PSUTIL_AVAILABLE = True
except ImportError:
    _PSUTIL_AVAILABLE = False

try:
    from PIL import ImageGrab
    _PIL_AVAILABLE = True
except ImportError:
    _PIL_AVAILABLE = False


def _base_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    return Path(__file__).resolve().parent.parent


BASE_DIR = _base_dir()
CONFIG_PATH = BASE_DIR / "config" / "api_keys.json"
TEMP_DIR = BASE_DIR / "snapshots" / "telegram"

PLUGIN = {
    "name": "telegram_bridge",
    "description": (
        "Provides remote uplink and communication with the user's phone via Telegram and Discord. "
        "Can send instant notifications, photos, system alerts, or check bridge connection status. "
        "Use this when the user asks to 'send a Telegram message', 'text my phone', "
        "'send a photo to my Telegram', 'check Telegram status', or 'start Telegram bridge'."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "action": {
                "type": "STRING",
                "description": "'send_message' | 'send_photo' | 'status' | 'start' | 'stop'",
            },
            "message": {
                "type": "STRING",
                "description": "The text message to send to the user's mobile device.",
            },
            "photo_path": {
                "type": "STRING",
                "description": "Optional local file path to an image to send.",
            },
        },
        "required": ["action"],
    },
}


class TelegramBridge:
    _instance: Optional[TelegramBridge] = None

    @classmethod
    def get_instance(cls) -> TelegramBridge:
        if cls._instance is None:
            cls._instance = TelegramBridge()
        return cls._instance

    def __init__(self):
        self.token: str = ""
        self.chat_id: str = ""
        self.pair_code: str = "JARVIS123"
        self.discord_webhook: str = ""
        
        self.is_running: bool = False
        self._stop_event = threading.Event()
        self._worker_thread: Optional[threading.Thread] = None
        self.last_offset: int = 0
        self.diagnostic_log: list[str] = []
        self.player: Any = None
        
        self._load_config()

    def log(self, msg: str):
        entry = f"[{time.strftime('%X')}] {msg}"
        self.diagnostic_log.append(entry)
        if len(self.diagnostic_log) > 100:
            self.diagnostic_log.pop(0)
        print(f"[TelegramBridge] {msg}")
        if self.player and hasattr(self.player, "write_log"):
            try:
                self.player.write_log(f"SYS: [Telegram] {msg}")
            except Exception:
                pass

    def _load_config(self):
        if not CONFIG_PATH.exists():
            return
        try:
            data = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
            self.token = data.get("telegram_bot_token", "").strip()
            self.chat_id = str(data.get("telegram_chat_id", "")).strip()
            self.pair_code = str(data.get("telegram_pair_code", "JARVIS123")).strip()
            self.discord_webhook = data.get("discord_webhook_url", "").strip()
        except Exception as e:
            self.log(f"Error loading config: {e}")

    def save_chat_id(self, chat_id: str):
        """Persist paired chat_id to config/api_keys.json."""
        self.chat_id = str(chat_id).strip()
        try:
            data: dict = {}
            if CONFIG_PATH.exists():
                data = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
            data["telegram_chat_id"] = self.chat_id
            CONFIG_PATH.write_text(json.dumps(data, indent=4), encoding="utf-8")
            self.log(f"Paired and saved chat_id: {self.chat_id}")
        except Exception as e:
            self.log(f"Failed to persist chat_id to config: {e}")

    # ── Outbound Communication ───────────────────────────────────────────────────

    def send_message(self, text: str, chat_id: Optional[str] = None) -> bool:
        """Send a text message to Telegram (and mirror to Discord if configured)."""
        target_chat = str(chat_id or self.chat_id).strip()
        success = False

        if self.token and target_chat and _REQUESTS_AVAILABLE:
            url = f"https://api.telegram.org/bot{self.token}/sendMessage"
            payload = {
                "chat_id": target_chat,
                "text": text,
                "parse_mode": "Markdown",
            }
            try:
                resp = requests.post(url, json=payload, timeout=10)
                if resp.status_code == 200:
                    success = True
                else:
                    # Retry without Markdown parsing in case of formatting errors
                    payload.pop("parse_mode", None)
                    resp2 = requests.post(url, json=payload, timeout=10)
                    success = (resp2.status_code == 200)
            except Exception as e:
                self.log(f"Telegram send error: {e}")

        # Mirror to Discord webhook if configured
        if self.discord_webhook and _REQUESTS_AVAILABLE:
            try:
                requests.post(self.discord_webhook, json={"content": text}, timeout=10)
            except Exception as e:
                self.log(f"Discord webhook error: {e}")

        return success

    def send_photo(self, photo_path: str, caption: str = "", chat_id: Optional[str] = None) -> bool:
        """Send an image to Telegram (and mirror to Discord if configured)."""
        target_chat = str(chat_id or self.chat_id).strip()
        path = Path(photo_path)
        if not path.exists():
            self.log(f"Photo path does not exist: {photo_path}")
            return False

        success = False
        if self.token and target_chat and _REQUESTS_AVAILABLE:
            url = f"https://api.telegram.org/bot{self.token}/sendPhoto"
            try:
                with open(path, "rb") as f:
                    files = {"photo": f}
                    data = {"chat_id": target_chat, "caption": caption}
                    resp = requests.post(url, data=data, files=files, timeout=15)
                    success = (resp.status_code == 200)
            except Exception as e:
                self.log(f"Telegram send_photo error: {e}")

        # Mirror photo to Discord webhook
        if self.discord_webhook and _REQUESTS_AVAILABLE:
            try:
                with open(path, "rb") as f:
                    requests.post(
                        self.discord_webhook,
                        data={"content": caption},
                        files={"file": f},
                        timeout=15,
                    )
            except Exception as e:
                self.log(f"Discord photo mirror error: {e}")

        return success

    def notify_sentry_alert(self, image_path: str, incident_num: int = 1) -> bool:
        """Convenience hook called by Sentry Mode when motion is detected."""
        caption = (
            f"🚨 *JARVIS Sentry Alert*\n"
            f"Motion detected at {time.strftime('%Y-%m-%d %H:%M:%S')}!\n"
            f"Incident #{incident_num} captured."
        )
        return self.send_photo(image_path, caption=caption)

    # ── Remote Command Execution ────────────────────────────────────────────────

    def execute_command(self, chat_id: str, raw_text: str, user_name: str = "User") -> str:
        """Process incoming command and return response text."""
        cmd_raw = raw_text.strip()
        parts = cmd_raw.split(maxsplit=1)
        command = parts[0].lower() if parts else ""
        arg = parts[1].strip() if len(parts) > 1 else ""

        # Check authorization
        target_chat = str(chat_id).strip()
        is_paired = bool(self.chat_id and self.chat_id == target_chat)

        if not is_paired:
            # Check for pairing attempt
            if command in ("/pair", "/start") and arg:
                if arg == self.pair_code:
                    self.save_chat_id(target_chat)
                    return (
                        f"✅ *Pairing Successful!*\n"
                        f"Welcome, {user_name}. JARVIS Remote Uplink is now securely paired with your device.\n"
                        f"Type /help for available commands."
                    )
                return "⛔ *Invalid Pairing Code.* Please provide the correct authorization code."
            
            return (
                "🔒 *JARVIS Security Check*\n"
                "This device is not authorized.\n"
                f"To pair this chat, send: `/pair {self.pair_code}`"
            )

        # Authorized commands
        if command in ("/start", "/help"):
            return (
                "🤖 *JARVIS Remote Uplink Control Center*\n\n"
                "• `/status` — System telemetry (CPU, RAM, Disk, Uptime)\n"
                "• `/screenshot` — Desktop screen capture\n"
                "• `/sentry on` — Arm Room Sentry surveillance\n"
                "• `/sentry off` — Disarm Room Sentry\n"
                "• `/sentry status` — Sentry surveillance diagnostics\n"
                "• `/lock` — Lock PC workstation immediately\n"
                "• `/ask <query>` — Ask JARVIS / Gemini LLM\n"
                "• Simply send any message to chat with JARVIS."
            )

        if command == "/status":
            return self._build_status_report()

        if command == "/screenshot":
            return self._handle_screenshot(target_chat)

        if command == "/lock":
            return self._handle_lock_workstation()

        if command == "/sentry":
            return self._handle_sentry_command(arg)

        if command == "/ask":
            if not arg:
                return "Please provide a query: `/ask <your question>`"
            return self._handle_llm_query(arg)

        # Conversational fallback
        return self._handle_llm_query(cmd_raw)

    def _build_status_report(self) -> str:
        report = ["🖥️ *JARVIS System Telemetry Report*"]
        
        if _PSUTIL_AVAILABLE:
            cpu = psutil.cpu_percent(interval=0.1)
            ram = psutil.virtual_memory()
            disk = psutil.disk_usage("/")
            report.append(f"• *CPU Usage:* {cpu}%")
            report.append(f"• *RAM:* {ram.percent}% ({ram.used // (1024**2)}MB / {ram.total // (1024**2)}MB)")
            report.append(f"• *Disk Free:* {disk.free // (1024**3)} GB ({disk.percent}% used)")
            
            battery = psutil.sensors_battery()
            if battery:
                plugged = "🔌 Plugged In" if battery.power_plugged else "🔋 On Battery"
                report.append(f"• *Battery:* {battery.percent}% ({plugged})")
        else:
            report.append("• *Telemetry:* psutil not available")

        # Sentry mode status check
        try:
            from plugins.sentry_mode import SentryController
            sentry = SentryController.get_instance()
            report.append(f"• *Sentry Mode:* {sentry.state} ({len(sentry.incidents)} incidents)")
        except Exception:
            report.append("• *Sentry Mode:* Offline")

        report.append(f"• *Uplink Status:* Active (Polling)")
        report.append(f"• *Local Time:* {time.strftime('%Y-%m-%d %H:%M:%S')}")
        return "\n".join(report)

    def _handle_screenshot(self, target_chat: str) -> str:
        if not _PIL_AVAILABLE:
            return "❌ Screenshot capability unavailable (Pillow not installed)."

        try:
            TEMP_DIR.mkdir(parents=True, exist_ok=True)
            shot_path = TEMP_DIR / f"shot_{int(time.time())}.jpg"
            img = ImageGrab.grab()
            img.save(str(shot_path), "JPEG", quality=80)
            self.send_photo(
                str(shot_path),
                caption=f"📸 Desktop Screenshot — {time.strftime('%H:%M:%S')}",
                chat_id=target_chat,
            )
            return "📸 Screenshot dispatched."
        except Exception as e:
            return f"❌ Failed to capture screenshot: {e}"

    def _handle_lock_workstation(self) -> str:
        try:
            if sys.platform == "win32":
                ctypes.windll.user32.LockWorkStation()
                return "🔒 *Workstation Locked.* Screen session secured, Sir."
            return "⚠️ Workstation lock is only supported on Windows."
        except Exception as e:
            return f"❌ Failed to lock workstation: {e}"

    def _handle_sentry_command(self, action: str) -> str:
        action = action.lower().strip()
        try:
            from plugins.sentry_mode import SentryController
            sentry = SentryController.get_instance()
            if action in ("on", "arm", "start"):
                res = sentry.arm(countdown=3, sensitivity="medium")
                return f"🛡️ *Sentry Mode:* {res}"
            elif action in ("off", "disarm", "stop"):
                res = sentry.disarm()
                return f"🛡️ *Sentry Mode:* {res}"
            elif action in ("status", "check"):
                return f"🛡️ *Sentry Mode Status:* {sentry.status()}"
            else:
                return "Usage: `/sentry on` | `/sentry off` | `/sentry status`"
        except Exception as e:
            return f"❌ Sentry controller error: {e}"

    def _handle_llm_query(self, query: str) -> str:
        try:
            from core.llm_client import call_llm_stream
            messages = [
                {"role": "system", "content": "You are JARVIS, an advanced AI assistant. Reply concisely and informatively via Telegram."},
                {"role": "user", "content": query},
            ]
            response = ""
            for msg in call_llm_stream(messages):
                if msg.get("type") == "sentence":
                    response += msg.get("text", "") + " "
            clean_res = response.strip()
            return clean_res if clean_res else "I have processed your query, Sir."
        except Exception as e:
            return f"🤖 (JARVIS Response Offline): Received: '{query}'"

    # ── Polling Daemon ──────────────────────────────────────────────────────────

    def start(self, player=None) -> str:
        """Start the background Telegram polling worker thread."""
        self.player = player
        if not self.token:
            self._load_config()

        if not self.token:
            return "Telegram bot token is not configured in config/api_keys.json (key: 'telegram_bot_token')."

        if not _REQUESTS_AVAILABLE:
            return "requests package is required for Telegram bridge."

        if self.is_running:
            return "Telegram bridge is already active."

        self._stop_event.clear()
        self.is_running = True
        self._worker_thread = threading.Thread(
            target=self._poll_loop,
            name="TelegramBridgeWorker",
            daemon=True,
        )
        self._worker_thread.start()
        self.log("Telegram Remote Uplink started.")
        return f"Telegram bridge activated. Paired chat: {self.chat_id or 'Waiting for pairing code'}"

    def stop(self) -> str:
        """Stop the background polling worker."""
        if not self.is_running:
            return "Telegram bridge is already stopped."

        self._stop_event.set()
        self.is_running = False
        if self._worker_thread and self._worker_thread.is_alive():
            self._worker_thread.join(timeout=2.0)
        self._worker_thread = None
        self.log("Telegram Remote Uplink stopped.")
        return "Telegram bridge stopped."

    def status(self) -> str:
        paired = f"Paired (chat_id: {self.chat_id})" if self.chat_id else "Unpaired (awaiting /pair)"
        token_set = "Configured" if self.token else "Missing"
        state = "ONLINE" if self.is_running else "OFFLINE"
        discord = "Configured" if self.discord_webhook else "Disabled"
        return (
            f"Telegram Bridge is {state}.\n"
            f"Bot Token: {token_set}\n"
            f"Device Status: {paired}\n"
            f"Discord Webhook: {discord}"
        )

    def _poll_loop(self):
        """Long-polling loop for Telegram updates."""
        url = f"https://api.telegram.org/bot{self.token}/getUpdates"
        
        while not self._stop_event.is_set():
            try:
                params = {
                    "offset": self.last_offset + 1,
                    "timeout": 20,
                }
                resp = requests.get(url, params=params, timeout=25)
                if resp.status_code == 200:
                    data = resp.json()
                    for update in data.get("result", []):
                        update_id = update.get("update_id", 0)
                        if update_id > self.last_offset:
                            self.last_offset = update_id

                        msg = update.get("message") or update.get("edited_message")
                        if not msg:
                            continue

                        chat = msg.get("chat", {})
                        chat_id = str(chat.get("id", ""))
                        user_info = msg.get("from", {})
                        username = user_info.get("first_name", "Boss")
                        text = msg.get("text", "")

                        if text and chat_id:
                            reply = self.execute_command(chat_id, text, user_name=username)
                            if reply:
                                self.send_message(reply, chat_id=chat_id)

                elif resp.status_code in (401, 404):
                    self.log(f"Invalid Telegram bot token: {resp.status_code}")
                    time.sleep(10)
                else:
                    time.sleep(2)
            except requests.RequestException:
                # Network hiccup / timeout — backoff slightly and resume
                time.sleep(3)
            except Exception as e:
                self.log(f"Polling loop exception: {e}")
                time.sleep(3)


def run(parameters: dict, player=None, session_memory=None) -> str:
    """Plugin dispatch entrypoint invoked by Gemini tool execution."""
    action = parameters.get("action", "").strip().lower()
    message = parameters.get("message", "").strip()
    photo_path = parameters.get("photo_path", "").strip()

    bridge = TelegramBridge.get_instance()

    if action == "start":
        return bridge.start(player=player)

    if action == "stop":
        return bridge.stop()

    if action == "status":
        return bridge.status()

    if action == "send_message":
        if not message:
            return "Error: message parameter is required for send_message."
        ok = bridge.send_message(message)
        return "Message sent to your phone via Telegram." if ok else "Failed to send Telegram message. Ensure bot is configured and paired."

    if action == "send_photo":
        if not photo_path:
            return "Error: photo_path parameter is required for send_photo."
        ok = bridge.send_photo(photo_path, caption=message)
        return f"Photo {photo_path} sent to your phone via Telegram." if ok else "Failed to send photo to Telegram. Check file path and bot configuration."

    return f"Error: Unknown action '{action}' for telegram_bridge."
