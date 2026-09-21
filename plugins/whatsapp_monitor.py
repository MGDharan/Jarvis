"""
WhatsApp Monitor Plugin — UIA-based (no Windows notification polling).

How it works:
  1. Finds the WhatsApp Desktop Chrome window via win32gui.
  2. Every 3 seconds, walks the UIA DataGridControl "Chat list" and reads
     DataItemControl names — items prefixed with "N unread message(s)" are new.
  3. For each new unread sender (not seen before this session), generates a
     contextual AI reply via Gemini, then sends it via _send_whatsapp().
  4. Notifies the user through JARVIS speech (plugin_say / player.request_say).

Dependencies (already in requirements.txt):
  uiautomation, pywin32, pyautogui, pyperclip, google-genai
"""

import json
import re
import threading
import time
from pathlib import Path

# ── optional deps — fail gracefully ──────────────────────────────────────────
try:
    import win32gui as _win32gui
    _WIN32_OK = True
except ImportError:
    _WIN32_OK = False

try:
    import uiautomation as _auto
    _UIA_OK = True
except ImportError:
    _UIA_OK = False

try:
    from google import genai as _genai
    _GENAI_OK = True
except ImportError:
    _GENAI_OK = False

# Reuse the project's own WhatsApp send helper
import sys
sys.path.append(str(Path(__file__).resolve().parent.parent))
try:
    from actions.send_message import _send_whatsapp
    _SEND_OK = True
except ImportError:
    _SEND_OK = False

# ── PLUGIN manifest ───────────────────────────────────────────────────────────
PLUGIN = {
    "name": "whatsapp_monitor",
    "description": (
        "Turns WhatsApp auto-reply monitoring on or off. "
        "When active, JARVIS watches incoming WhatsApp messages and sends a smart "
        "AI reply on the user's behalf. "
        "Trigger phrases: 'monitor my WhatsApp', 'watch my WhatsApp', "
        "'start WhatsApp monitor', 'auto-reply WhatsApp', "
        "'handle my WhatsApp messages', 'stop WhatsApp monitor', "
        "'turn off WhatsApp auto-reply', 'I am busy reply to whatsapp'. "
        "Always call this tool — never say you cannot monitor WhatsApp."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "status": {
                "type": "STRING",
                "description": "'on' to start monitoring, 'off' to stop.",
            },
            "reply_instruction": {
                "type": "STRING",
                "description": (
                    "Optional custom instruction for how to reply, e.g. "
                    "'tell them I am busy', 'say I will call back later'. "
                    "If omitted, a polite busy-reply is used."
                ),
            },
        },
        "required": ["status"],
    },
}

# ── module-level state ────────────────────────────────────────────────────────
_monitor_thread: threading.Thread | None = None
_monitoring_active = False
_stop_event = threading.Event()

# Track which senders we have already replied to this session
# key = sender string  →  value = timestamp of last reply
_replied: dict[str, float] = {}
# Minimum seconds before re-replying to the same sender
_REPLY_COOLDOWN = 120


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _get_wa_hwnd() -> int | None:
    """Return the HWND of the WhatsApp Chromium window, or None."""
    if not _WIN32_OK:
        return None
    found = []
    def _cb(hwnd, _):
        title = _win32gui.GetWindowText(hwnd)
        cls   = _win32gui.GetClassName(hwnd)
        if "WhatsApp" in title and cls == "Chrome_WidgetWin_1":
            found.append(hwnd)
    _win32gui.EnumWindows(_cb, None)
    return found[0] if found else None


def _get_unread_chats(hwnd: int) -> list[dict]:
    """
    Scan the WhatsApp UIA tree and return unread chats.
    Each entry: {"sender": str, "message": str, "count": int}
    Must be called from a COM-initialised thread.
    """
    if not _UIA_OK:
        return []
    try:
        # Ensure COM is initialised for this thread (safe to call multiple times)
        with _auto.UIAutomationInitializerInThread():
            ctrl = _auto.ControlFromHandle(hwnd)
            grid = ctrl.DataGridControl(Name="Chat list", searchDepth=25)
            if not grid.Exists(0.3):
                return []

            results = []
            seen: set[str] = set()

            for item in grid.GetChildren():
                raw = (item.Name or "").strip()
                if not raw or raw in seen:
                    continue
                seen.add(raw)

                # Pattern: "N unread message(s)  <Sender>  HH:MM am/pm  <preview>"
                m = re.match(
                    r"^(\d+)\s+unread\s+messages?\s+(.+?)\s+\d+:\d+\s*(?:am|pm)\s+(.*)",
                    raw,
                    re.IGNORECASE,
                )
                if not m:
                    continue

                count  = int(m.group(1))
                sender = m.group(2).strip()
                rest   = m.group(3).strip()

                # Group chats: rest starts with "~Name:\xa0 message"
                grp = re.match(r"^~?[^:]+:\xa0?\s*(.*)", rest)
                message = grp.group(1).strip() if grp else rest

                # Clean non-breaking spaces
                message = message.replace("\xa0", " ").strip()
                sender  = sender.replace("\xa0", " ").strip()

                results.append({"sender": sender, "message": message, "count": count})

            return results

    except Exception as exc:
        print(f"[WhatsApp Monitor] UIA scan error: {exc}")
        return []


def _generate_reply(sender: str, message: str, instruction: str) -> str:
    """Generate a contextual reply via Gemini, falling back to a static string."""
    # Load user name from config
    config_path = Path(__file__).resolve().parent.parent / "config" / "api_keys.json"
    user_name = "the user"
    api_key   = ""
    try:
        cfg       = json.loads(config_path.read_text(encoding="utf-8"))
        api_key   = cfg.get("gemini_api_key", "").strip()
        user_name = (cfg.get("user_name") or cfg.get("assistant_name") or "the user").strip()
    except Exception:
        pass

    fallback = f"Hi, I'm JARVIS, {user_name}'s AI assistant. {user_name} is currently busy and will get back to you soon."

    if not _GENAI_OK or not api_key:
        return fallback

    # Build the instruction clause
    if instruction:
        instr_clause = instruction.strip().rstrip(".")
    else:
        instr_clause = f"{user_name} is currently busy"

    prompt = (
        f"You are JARVIS, {user_name}'s personal AI assistant. "
        f"You received a WhatsApp message from '{sender}': \"{message}\". "
        f"Instruction: {instr_clause}. "
        f"Write a short, natural, polite reply on {user_name}'s behalf. "
        f"Acknowledge what they said if relevant. "
        f"Keep it under 2 sentences. Reply directly — no preamble."
    )

    try:
        import warnings
        client   = _genai.Client(api_key=api_key)
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            response = client.models.generate_content(
                model="gemini-2.5-flash",
                contents=prompt,
            )
        return (response.text or "").strip() or fallback
    except Exception as exc:
        print(f"[WhatsApp Monitor] Gemini reply error: {exc}")
        return fallback


# ─────────────────────────────────────────────────────────────────────────────
# Monitor loop
# ─────────────────────────────────────────────────────────────────────────────

def _monitor_loop(player, instruction: str) -> None:
    global _monitoring_active

    print("[WhatsApp Monitor] ▶ Started (UIA mode).")
    if player:
        try:
            player.write_log("JARVIS: WhatsApp auto-reply monitor is now active.")
        except Exception:
            pass

    hwnd: int | None = None

    while not _stop_event.is_set():
        try:
            # Re-locate the window every cycle (handles WhatsApp restarts)
            hwnd = _get_wa_hwnd()
            if hwnd is None:
                time.sleep(5)
                continue

            unread = _get_unread_chats(hwnd)

            for chat in unread:
                sender  = chat["sender"]
                message = chat["message"]
                now     = time.time()

                # Skip if we replied to this sender recently
                last = _replied.get(sender, 0)
                if now - last < _REPLY_COOLDOWN:
                    continue

                _replied[sender] = now
                print(f"[WhatsApp Monitor] 📩 New message from '{sender}': {message[:60]}")

                # Generate reply
                reply = _generate_reply(sender, message, instruction)
                print(f"[WhatsApp Monitor] 📤 Replying: {reply[:80]}")

                # Send via WhatsApp desktop
                if _SEND_OK:
                    try:
                        result = _send_whatsapp(sender, reply)
                        print(f"[WhatsApp Monitor] ✅ {result}")
                    except Exception as send_err:
                        print(f"[WhatsApp Monitor] ❌ Send failed: {send_err}")
                else:
                    print("[WhatsApp Monitor] ⚠️ send_message not available.")

                # Notify the user via JARVIS voice
                alert = (
                    f"Sir, '{sender}' sent you a message: \"{message[:80]}\". "
                    f"I replied: \"{reply[:80]}\""
                )
                if player:
                    try:
                        player.write_log(f"JARVIS: 📨 {alert}")
                    except Exception:
                        pass
                    # Speak alert through active Gemini session if possible
                    if hasattr(player, "request_say") and callable(player.request_say):
                        try:
                            player.request_say(
                                f"New WhatsApp message from {sender}. I have replied on your behalf."
                            )
                        except Exception:
                            pass

        except Exception as loop_err:
            print(f"[WhatsApp Monitor] Loop error: {loop_err}")

        _stop_event.wait(timeout=3)  # poll every 3 seconds

    print("[WhatsApp Monitor] ■ Stopped.")


# ─────────────────────────────────────────────────────────────────────────────
# Plugin entry point
# ─────────────────────────────────────────────────────────────────────────────

def run(parameters: dict, player=None, session_memory=None) -> str:
    global _monitor_thread, _monitoring_active

    status      = parameters.get("status", "off").strip().lower()
    instruction = parameters.get("reply_instruction", "").strip()

    # ── Start ────────────────────────────────────────────────────────────────
    if status == "on":
        if _monitoring_active:
            return "WhatsApp monitor is already running."

        # Dependency checks
        missing = []
        if not _WIN32_OK:
            missing.append("pywin32")
        if not _UIA_OK:
            missing.append("uiautomation")
        if not _SEND_OK:
            missing.append("pyautogui / pyperclip")
        if missing:
            return (
                f"Cannot start — missing packages: {', '.join(missing)}. "
                f"Run: pip install {' '.join(missing)}"
            )

        if _get_wa_hwnd() is None:
            return (
                "WhatsApp Desktop is not open. "
                "Please open WhatsApp Desktop first, then ask me to start the monitor."
            )

        _stop_event.clear()
        _replied.clear()
        _monitoring_active = True

        _monitor_thread = threading.Thread(
            target=_monitor_loop,
            args=(player, instruction),
            daemon=True,
        )
        _monitor_thread.start()

        instr_note = f" I will {instruction}." if instruction else ""
        return (
            f"WhatsApp monitor is now active.{instr_note} "
            f"I will scan for new messages every 3 seconds and reply automatically."
        )

    # ── Stop ─────────────────────────────────────────────────────────────────
    elif status == "off":
        if not _monitoring_active:
            return "WhatsApp monitor is not running."

        _stop_event.set()
        _monitoring_active = False

        if _monitor_thread and _monitor_thread.is_alive():
            _monitor_thread.join(timeout=5)

        return "WhatsApp monitor stopped. I will no longer auto-reply to messages."

    return "Invalid status. Use 'on' or 'off'."
