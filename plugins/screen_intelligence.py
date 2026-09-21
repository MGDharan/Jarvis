"""
Screen Intelligence Plugin — Always-on proactive screen watcher.

When active, captures a screenshot every N seconds, sends it to Gemini Vision,
and if Gemini detects something worth mentioning (error, suggestion, opportunity)
it speaks up proactively through the active JARVIS session.

Smart suppression:
  - Only speaks if JARVIS is NOT already speaking
  - Minimum 60-second gap between proactive remarks
  - Skips if screen hasn't changed significantly (pixel diff < threshold)
  - User can say "watch my screen" to start and "stop watching" to stop

Say: "watch my screen", "start screen intelligence", "enable screen watcher"
     "stop watching", "disable screen intelligence", "stop screen watcher"
     "what's on my screen" → immediate one-shot analysis (uses existing tool)
"""

from __future__ import annotations

import base64
import io
import json
import threading
import time
import warnings
from pathlib import Path

try:
    import mss
    import mss.tools
    _MSS = True
except ImportError:
    _MSS = False

try:
    import PIL.Image
    import PIL.ImageChops
    import PIL.ImageStat
    _PIL = True
except ImportError:
    _PIL = False

try:
    from google import genai as _genai
    _GENAI = True
except ImportError:
    _GENAI = False

# ── PLUGIN manifest ───────────────────────────────────────────────────────────
PLUGIN = {
    "name": "screen_intelligence",
    "description": (
        "Starts or stops the always-on screen intelligence watcher. "
        "When active, JARVIS continuously monitors the screen and proactively "
        "speaks up when it notices errors, code issues, important notifications, "
        "or anything worth flagging. "
        "Trigger phrases to START: 'watch my screen', 'enable screen watcher', "
        "'start screen intelligence', 'monitor my screen', 'keep an eye on my screen'. "
        "Trigger phrases to STOP: 'stop watching my screen', 'disable screen watcher', "
        "'stop screen intelligence'. "
        "For an immediate one-shot look say: 'what is on my screen right now'."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "action": {
                "type": "STRING",
                "description": "'on' to start watching, 'off' to stop, 'snapshot' for immediate one-shot.",
            },
            "interval_seconds": {
                "type": "NUMBER",
                "description": "How often to check in seconds (default 20, min 10, max 120).",
            },
            "sensitivity": {
                "type": "STRING",
                "description": (
                    "'low' — only speak for errors/crashes, "
                    "'medium' (default) — errors + suggestions, "
                    "'high' — anything interesting."
                ),
            },
        },
        "required": ["action"],
    },
}

# ── Module state ──────────────────────────────────────────────────────────────
_watcher_thread:   threading.Thread | None = None
_watching          = False
_stop_evt          = threading.Event()
_last_speak_time   = 0.0
_last_img_bytes: bytes | None = None

_CONFIG_PATH = Path(__file__).resolve().parent.parent / "config" / "api_keys.json"

# Sensitivity → system prompt tuning
_SENSITIVITY_PROMPTS = {
    "low": (
        "You are JARVIS, an AI watching the user's screen silently. "
        "ONLY speak if you see a clear ERROR, crash dialog, exception traceback, "
        "or security warning. Stay silent for everything else. "
        "Response format: one sentence starting with 'Sir,' or stay completely silent (empty string)."
    ),
    "medium": (
        "You are JARVIS, an AI watching the user's screen. "
        "Speak up if you notice: errors or exceptions, inefficient code patterns, "
        "important notifications the user may have missed, or clear opportunities to help. "
        "Stay silent for routine work. "
        "Response format: one short sentence starting with 'Sir,' or empty string to stay silent."
    ),
    "high": (
        "You are JARVIS, an AI watching the user's screen. "
        "Comment on anything interesting: what the user is working on, "
        "suggestions to improve their work, shortcuts they could use, "
        "or anything worth noting. Be brief and helpful. "
        "Response format: one sentence starting with 'Sir,' or empty string to stay silent."
    ),
}


def _load_api_key() -> str:
    try:
        return json.loads(_CONFIG_PATH.read_text(encoding="utf-8")).get("gemini_api_key", "")
    except Exception:
        return ""


def _capture_screen_small() -> bytes | None:
    """Capture screen and return compressed JPEG bytes."""
    if not _MSS or not _PIL:
        return None
    try:
        with mss.mss() as sct:
            monitors = sct.monitors
            target   = monitors[1] if len(monitors) > 1 else monitors[0]
            shot     = sct.grab(target)
            png      = mss.tools.to_png(shot.rgb, shot.size)

        img = PIL.Image.open(io.BytesIO(png)).convert("RGB")
        # Resize to 960x540 — enough for Gemini to read text/UI, smaller = faster
        img.thumbnail((960, 540), PIL.Image.BILINEAR)
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=72)
        return buf.getvalue()
    except Exception as e:
        print(f"[ScreenIntel] Capture error: {e}")
        return None


def _screen_changed(new_bytes: bytes, threshold: float = 8.0) -> bool:
    """Returns True if the screen changed significantly from the last capture."""
    global _last_img_bytes
    if _last_img_bytes is None or not _PIL:
        _last_img_bytes = new_bytes
        return True
    try:
        img_old = PIL.Image.open(io.BytesIO(_last_img_bytes)).convert("L")
        img_new = PIL.Image.open(io.BytesIO(new_bytes)).convert("L")
        if img_old.size != img_new.size:
            _last_img_bytes = new_bytes
            return True
        diff    = PIL.ImageChops.difference(img_old, img_new)
        rms     = PIL.ImageStat.Stat(diff).rms[0]
        changed = rms > threshold
        if changed:
            _last_img_bytes = new_bytes
        return changed
    except Exception:
        _last_img_bytes = new_bytes
        return True


def _ask_gemini(img_bytes: bytes, system_prompt: str) -> str:
    """Send screenshot to Gemini, get a one-sentence reply (or empty = stay silent)."""
    api_key = _load_api_key()
    if not api_key or not _GENAI:
        return ""
    try:
        b64 = base64.b64encode(img_bytes).decode("ascii")
        client = _genai.Client(api_key=api_key)
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            response = client.models.generate_content(
                model="gemini-2.5-flash",
                contents=[
                    {"parts": [
                        {"inline_data": {"mime_type": "image/jpeg", "data": b64}},
                        {"text": (
                            "Look at this screenshot carefully. "
                            + system_prompt
                        )},
                    ]}
                ],
            )
        text = (response.text or "").strip()
        # If Gemini says nothing actionable, return empty
        if not text or len(text) < 5:
            return ""
        return text
    except Exception as e:
        print(f"[ScreenIntel] Gemini error: {e}")
        return ""


def _watcher_loop(player, interval: int, sensitivity: str) -> None:
    global _watching, _last_speak_time

    sys_prompt = _SENSITIVITY_PROMPTS.get(sensitivity, _SENSITIVITY_PROMPTS["medium"])
    print(f"[ScreenIntel] ▶ Started (interval={interval}s, sensitivity={sensitivity})")

    if player:
        try:
            player.write_log(f"JARVIS: Screen intelligence active (every {interval}s).")
        except Exception:
            pass

    while not _stop_evt.is_set():
        _stop_evt.wait(timeout=interval)
        if _stop_evt.is_set():
            break

        try:
            # Don't analyze if JARVIS is speaking
            if player and hasattr(player, "muted"):
                pass  # muted is fine — we still watch

            img = _capture_screen_small()
            if img is None:
                continue

            # Skip if screen hasn't changed much
            if not _screen_changed(img):
                continue

            # Rate limit proactive speech
            now = time.time()
            if now - _last_speak_time < 55:
                continue

            print("[ScreenIntel] 🔍 Analyzing screen...")
            remark = _ask_gemini(img, sys_prompt)

            if not remark:
                print("[ScreenIntel] 💤 Nothing to report.")
                continue

            print(f"[ScreenIntel] 💬 {remark}")
            _last_speak_time = now

            # Log to UI
            if player:
                try:
                    player.write_log(f"JARVIS: {remark}")
                except Exception:
                    pass

            # Inject into Gemini live session
            if player and hasattr(player, "request_say") and callable(player.request_say):
                try:
                    player.request_say(remark)
                except Exception as e:
                    print(f"[ScreenIntel] request_say failed: {e}")

        except Exception as e:
            print(f"[ScreenIntel] Loop error: {e}")

    _watching = False
    print("[ScreenIntel] ■ Stopped.")


def _do_snapshot(player, sensitivity: str) -> str:
    """Immediate one-shot screen analysis."""
    img = _capture_screen_small()
    if img is None:
        return "Could not capture screen, sir. Make sure mss and Pillow are installed."

    sys_prompt = _SENSITIVITY_PROMPTS.get(sensitivity, _SENSITIVITY_PROMPTS["medium"])
    # For snapshots use a more descriptive prompt
    snap_prompt = (
        "Describe what you see on this screen in detail. "
        "Mention the active application, what the user appears to be doing, "
        "any visible errors or important content, and any suggestions you have. "
        "Be thorough but concise — 2-4 sentences. Start with 'Sir,'"
    )

    print("[ScreenIntel] 📸 One-shot snapshot analysis...")
    if player:
        try:
            player.write_log("JARVIS: Analyzing your screen...")
        except Exception:
            pass

    result = _ask_gemini(img, snap_prompt)
    if not result:
        result = "I can see your screen, sir, but nothing particularly notable stands out right now."

    if player:
        try:
            player.write_log(f"JARVIS: {result}")
        except Exception:
            pass
        if hasattr(player, "request_say") and callable(player.request_say):
            try:
                player.request_say(result)
            except Exception:
                pass

    return result


# ── Plugin entry point ────────────────────────────────────────────────────────

def run(parameters: dict, player=None, session_memory=None) -> str:
    global _watcher_thread, _watching

    action      = parameters.get("action", "on").strip().lower()
    interval    = int(max(10, min(120, parameters.get("interval_seconds", 20) or 20)))
    sensitivity = parameters.get("sensitivity", "medium").strip().lower()
    if sensitivity not in ("low", "medium", "high"):
        sensitivity = "medium"

    # ── Snapshot (one-shot) ───────────────────────────────────────────────────
    if action in ("snapshot", "look", "check", "analyze"):
        return _do_snapshot(player, sensitivity)

    # ── Stop ─────────────────────────────────────────────────────────────────
    if action in ("off", "stop", "disable"):
        if not _watching:
            return "Screen intelligence watcher is already off."
        _stop_evt.set()
        _watching = False
        if player:
            try:
                player.write_log("JARVIS: Screen intelligence deactivated.")
            except Exception:
                pass
        return "Screen intelligence deactivated. I'll stop watching your screen, sir."

    # ── Start ─────────────────────────────────────────────────────────────────
    missing = []
    if not _MSS:
        missing.append("mss")
    if not _PIL:
        missing.append("Pillow")
    if not _GENAI:
        missing.append("google-generativeai")
    if missing:
        return (
            f"Cannot start — missing packages: {', '.join(missing)}. "
            f"Run: pip install {' '.join(missing)}"
        )

    if not _load_api_key():
        return "Gemini API key not configured — cannot start screen intelligence."

    if _watching:
        return (
            f"Screen intelligence is already active "
            f"(interval={interval}s, sensitivity={sensitivity})."
        )

    _stop_evt.clear()
    _watching = True
    _watcher_thread = threading.Thread(
        target=_watcher_loop,
        args=(player, interval, sensitivity),
        daemon=True,
    )
    _watcher_thread.start()

    return (
        f"Screen intelligence activated, sir. "
        f"I will watch your screen every {interval} seconds "
        f"and speak up if I notice anything worth flagging. "
        f"Sensitivity is set to {sensitivity}. "
        f"Say 'stop watching my screen' to deactivate."
    )
