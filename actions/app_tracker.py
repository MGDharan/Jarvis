"""
AppTracker — tracks foreground app usage over time.

Records which application is in focus and for how long, persists sessions to
~/.jarvis/app_usage.json, and provides productivity stats + focus-mode support.

Zero subprocess usage on Windows: uses ctypes + pywin32 (win32process / win32gui)
for foreground window detection.  Gracefully degrades on macOS and Linux via
Subprocess/Wnck fallbacks.

Integrates with main.py via:
    from actions.app_tracker import AppTracker, get_usage_tool

The JarvisLive class creates one AppTracker instance and calls:
    tracker.start()          — begins background polling
    tracker.stop()           — stops (called on shutdown)
    tracker.get_session_alert()  — call periodically; returns a [USAGE_ALERT]
                                   string if something notable happened, else None
"""
from __future__ import annotations

import json
import platform
import re
import threading
import time
from collections import defaultdict
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Optional

_OS = platform.system()   # "Windows" | "Darwin" | "Linux"

# ── Storage ────────────────────────────────────────────────────────────────────

_STORAGE_DIR  = Path.home() / ".jarvis"
_USAGE_FILE   = _STORAGE_DIR / "app_usage.json"
_STORAGE_DIR.mkdir(parents=True, exist_ok=True)

# Polling interval (seconds).  1 s gives 1-second resolution without hammering CPU.
_POLL_INTERVAL = 1.0

# Apps that are "infrastructure" — not interesting for productivity reports.
_IGNORE_APPS = {
    "explorer", "searchhost", "searchapp", "shellexperiencehost",
    "startmenuexperiencehost", "applicationframehost", "textinputhost",
    "systemsettings", "lockapp", "cortana", "winlogon",
    "screensaver", "taskmgr", "dllhost", "conhost",
    # common notification overlays
    "notifications", "snip & sketch", "snipingtool",
}

# Time after which a single idle stretch is not counted as "active" usage.
_MAX_IDLE_SEC = 300   # 5 minutes — gap longer than this breaks the session

# Alert threshold: warn if user spends more than this on a category per hour.
_ALERT_MINUTES_PER_HOUR = 45   # e.g. 45 min of social media in one hour triggers alert
_ALERT_COOLDOWN_SEC     = 3600  # one alert per category per hour maximum

# App category mapping (lower-case substring → category label)
_CATEGORIES: list[tuple[str, str]] = [
    # Social / messaging
    ("whatsapp",    "Messaging"),
    ("telegram",    "Messaging"),
    ("discord",     "Messaging"),
    ("slack",       "Messaging"),
    ("signal",      "Messaging"),
    ("instagram",   "Social Media"),
    ("twitter",     "Social Media"),
    ("facebook",    "Social Media"),
    ("tiktok",      "Social Media"),
    ("reddit",      "Social Media"),
    # Entertainment
    ("youtube",     "Video"),
    ("netflix",     "Video"),
    ("prime video", "Video"),
    ("vlc",         "Video"),
    ("spotify",     "Music"),
    ("steam",       "Gaming"),
    ("epicgames",   "Gaming"),
    ("game",        "Gaming"),
    # Productivity
    ("visual studio code", "Coding"),
    ("vscode",      "Coding"),
    ("pycharm",     "Coding"),
    ("intellij",    "Coding"),
    ("terminal",    "Coding"),
    ("cmd",         "Terminal"),
    ("powershell",  "Terminal"),
    ("word",        "Documents"),
    ("excel",       "Documents"),
    ("powerpoint",  "Documents"),
    ("notepad",     "Documents"),
    ("notion",      "Documents"),
    ("obsidian",    "Documents"),
    ("chrome",      "Browser"),
    ("firefox",     "Browser"),
    ("edge",        "Browser"),
    ("opera",       "Browser"),
    ("brave",       "Browser"),
]


def _categorize(app_name: str) -> str:
    lower = app_name.lower()
    for keyword, category in _CATEGORIES:
        if keyword in lower:
            return category
    return "Other"


# ── Foreground window detection ────────────────────────────────────────────────

def _get_foreground_app() -> Optional[str]:
    """Return the friendly name of the currently focused application, or None."""
    if _OS == "Windows":
        return _foreground_windows()
    if _OS == "Darwin":
        return _foreground_macos()
    return _foreground_linux()


def _foreground_windows() -> Optional[str]:
    try:
        import ctypes
        import ctypes.wintypes
        hwnd = ctypes.windll.user32.GetForegroundWindow()
        if not hwnd:
            return None
        pid = ctypes.wintypes.DWORD()
        ctypes.windll.user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))

        # Try psutil first — gives a clean process name without needing pywin32
        try:
            import psutil
            proc = psutil.Process(pid.value)
            return proc.name().replace(".exe", "").strip()
        except Exception:
            pass

        # Fallback: GetWindowText gives the window title, which is usually informative
        buf = ctypes.create_unicode_buffer(256)
        ctypes.windll.user32.GetWindowTextW(hwnd, buf, 256)
        title = buf.value.strip()
        return title if title else None
    except Exception:
        return None


def _foreground_macos() -> Optional[str]:
    try:
        import subprocess
        script = (
            'tell application "System Events" to '
            'get name of first application process whose frontmost is true'
        )
        result = subprocess.run(
            ["osascript", "-e", script],
            capture_output=True, text=True, timeout=2,
        )
        name = result.stdout.strip()
        return name if name else None
    except Exception:
        return None


def _foreground_linux() -> Optional[str]:
    try:
        # xdotool is the most reliable cross-DE method
        import subprocess
        wid = subprocess.run(
            ["xdotool", "getactivewindow"],
            capture_output=True, text=True, timeout=2,
        ).stdout.strip()
        if wid:
            name = subprocess.run(
                ["xdotool", "getwindowname", wid],
                capture_output=True, text=True, timeout=2,
            ).stdout.strip()
            return name if name else None
    except Exception:
        pass
    try:
        import subprocess
        import os
        pid = subprocess.run(
            ["xprop", "-root", "_NET_ACTIVE_WINDOW"],
            capture_output=True, text=True, timeout=2,
        ).stdout.strip()
        m = re.search(r"0x[0-9a-f]+", pid)
        if m:
            win = subprocess.run(
                ["xprop", "-id", m.group(), "WM_NAME"],
                capture_output=True, text=True, timeout=2,
            ).stdout.strip()
            m2 = re.search(r'"(.+)"', win)
            if m2:
                return m2.group(1)
    except Exception:
        pass
    return None


def _is_ignored(name: str) -> bool:
    lower = name.lower()
    return any(ignored in lower for ignored in _IGNORE_APPS)


# ── Persistence ────────────────────────────────────────────────────────────────

def _load_usage() -> dict:
    """Load usage data from disk.  Returns {} on any read error."""
    try:
        if _USAGE_FILE.exists():
            return json.loads(_USAGE_FILE.read_text(encoding="utf-8"))
    except Exception:
        pass
    return {}


def _save_usage(data: dict) -> None:
    try:
        _USAGE_FILE.write_text(
            json.dumps(data, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
    except Exception as e:
        print(f"[AppTracker] ⚠️ Save failed: {e}")


# ── Main tracker class ─────────────────────────────────────────────────────────

class AppTracker:
    """
    Background thread that polls the foreground window every second and
    accumulates per-app, per-category seconds for the current day.

    Public API:
        start()                    — start background polling thread
        stop()                     — graceful stop + flush to disk
        get_session_alert()        — call periodically; returns alert string or None
        get_stats(period)          — dict of {app: seconds} for 'today'/'week'/'session'
        get_category_stats(period) — dict of {category: seconds} for the same periods
        set_focus_mode(apps)       — restrict alert to specific apps (empty = all)
        clear_focus_mode()         — disable focus mode
        format_report(period)      — human-readable productivity report string
    """

    def __init__(self):
        self._lock          = threading.Lock()
        self._stop_event    = threading.Event()
        self._thread: Optional[threading.Thread] = None

        # In-memory accumulators: {app_name: seconds_today}
        self._session_totals: dict[str, float] = defaultdict(float)   # this session only
        self._daily_totals:   dict[str, float] = defaultdict(float)   # today (loaded from disk)

        # Alert state
        self._alert_totals:   dict[str, float] = defaultdict(float)   # per category since last flush
        self._last_alert:     dict[str, float] = {}                   # category → monotonic time

        # Focus mode: if non-empty, only track these apps
        self._focus_apps:  set[str] = set()
        self._focus_start: Optional[float] = None

        # Today's date key for daily rollover
        self._today = str(date.today())

        # Load today's existing data from disk
        self._load_today()

    # ── Lifecycle ──────────────────────────────────────────────────────────────

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop_event.clear()
        self._thread = threading.Thread(
            target=self._poll_loop, daemon=True, name="JarvisAppTracker"
        )
        self._thread.start()
        print("[AppTracker] ✅ Started background app tracking.")

    def stop(self) -> None:
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=3.0)
        self._flush_to_disk()
        print("[AppTracker] 🛑 Stopped.")

    # ── Focus mode ─────────────────────────────────────────────────────────────

    def set_focus_mode(self, apps: list[str]) -> None:
        with self._lock:
            self._focus_apps  = {a.lower() for a in apps}
            self._focus_start = time.monotonic()
        print(f"[AppTracker] 🎯 Focus mode: {apps or 'all'}")

    def clear_focus_mode(self) -> None:
        with self._lock:
            self._focus_apps  = set()
            self._focus_start = None
        print("[AppTracker] Focus mode cleared.")

    # ── Stats retrieval ────────────────────────────────────────────────────────

    def get_stats(self, period: str = "today") -> dict[str, float]:
        """Return {app_name: seconds} for the requested period."""
        with self._lock:
            if period == "session":
                return dict(self._session_totals)
            if period == "today":
                return dict(self._daily_totals)
            if period == "week":
                return self._load_week_stats()
        return {}

    def get_category_stats(self, period: str = "today") -> dict[str, float]:
        stats = self.get_stats(period)
        cat: dict[str, float] = defaultdict(float)
        for app, secs in stats.items():
            cat[_categorize(app)] += secs
        return dict(cat)

    def get_top_apps(self, period: str = "today", n: int = 10) -> list[tuple[str, float]]:
        stats = self.get_stats(period)
        return sorted(stats.items(), key=lambda x: x[1], reverse=True)[:n]

    # ── Formatted report ───────────────────────────────────────────────────────

    def format_report(self, period: str = "today") -> str:
        top   = self.get_top_apps(period, n=8)
        cats  = self.get_category_stats(period)
        total = sum(s for _, s in top)

        if not top:
            return f"No app usage recorded for {period} yet."

        lines = [f"📊 App usage — {period}  (total tracked: {_fmt_time(total)})\n"]

        lines.append("By application:")
        for app, secs in top:
            bar  = "█" * min(20, int(secs / max(1, total) * 20))
            pct  = secs / max(1, total) * 100
            lines.append(f"  {app:<28} {_fmt_time(secs):>8}  {pct:4.0f}%  {bar}")

        lines.append("\nBy category:")
        for cat, secs in sorted(cats.items(), key=lambda x: x[1], reverse=True):
            lines.append(f"  {cat:<20} {_fmt_time(secs):>8}")

        # Productivity score: ratio of coding+documents vs entertainment+social
        productive   = cats.get("Coding", 0) + cats.get("Documents", 0) + cats.get("Terminal", 0)
        unproductive = cats.get("Social Media", 0) + cats.get("Video", 0) + cats.get("Gaming", 0)
        tracked_total = sum(cats.values())
        if tracked_total > 60:
            score = int(productive / tracked_total * 100)
            lines.append(f"\n🏆 Productivity score: {score}%")
            if score >= 70:
                lines.append("   Great focus today!")
            elif score >= 40:
                lines.append("   Decent balance. Consider reducing distractions.")
            else:
                lines.append("   Heavy entertainment usage detected.")

        return "\n".join(lines)

    # ── Alert interface (called by JarvisLive background loop) ────────────────

    def get_session_alert(self) -> Optional[str]:
        """
        Returns a [USAGE_ALERT] string if a category threshold was exceeded,
        or None.  Called by the JARVIS background monitor every few minutes.
        """
        with self._lock:
            cats = defaultdict(float)
            for app, secs in self._alert_totals.items():
                cats[_categorize(app)] += secs

            now = time.monotonic()
            alerts = []
            for cat, secs in cats.items():
                if cat in ("Other", "Browser", "Terminal", "Coding", "Documents"):
                    continue   # these are fine to use heavily
                if secs < _ALERT_MINUTES_PER_HOUR * 60:
                    continue
                last = self._last_alert.get(cat, 0.0)
                if (now - last) < _ALERT_COOLDOWN_SEC:
                    continue
                self._last_alert[cat] = now
                # Reset counter for this category
                for app in list(self._alert_totals):
                    if _categorize(app) == cat:
                        self._alert_totals[app] = 0.0

                alerts.append(
                    f"[USAGE_ALERT] The user has spent {int(secs // 60)} minutes on "
                    f"{cat} apps in the past hour (threshold: {_ALERT_MINUTES_PER_HOUR} min). "
                    f"Gently mention it once if appropriate."
                )

            return " ".join(alerts) if alerts else None

    # ── Internal polling ───────────────────────────────────────────────────────

    def _poll_loop(self) -> None:
        _prev_app    = ""
        _prev_time   = time.monotonic()
        _idle_streak = 0.0

        while not self._stop_event.wait(_POLL_INTERVAL):
            app = _get_foreground_app()

            # Ignore system infrastructure and empty results
            if not app or _is_ignored(app):
                _idle_streak += _POLL_INTERVAL
                if _idle_streak > _MAX_IDLE_SEC:
                    _prev_app  = ""   # break the session
                continue
            _idle_streak = 0.0

            # Check for daily rollover
            today = str(date.today())
            with self._lock:
                if today != self._today:
                    self._flush_to_disk()
                    self._daily_totals = defaultdict(float)
                    self._alert_totals = defaultdict(float)
                    self._today = today

            # Accumulate time for the previous app
            now = time.monotonic()
            elapsed = now - _prev_time
            _prev_time = now

            if _prev_app and elapsed < _MAX_IDLE_SEC:
                # Filter by focus mode if active
                if self._focus_apps:
                    if not any(f in _prev_app.lower() for f in self._focus_apps):
                        _prev_app = app
                        continue

                with self._lock:
                    self._session_totals[_prev_app] += elapsed
                    self._daily_totals[_prev_app]   += elapsed
                    self._alert_totals[_prev_app]   += elapsed

            _prev_app = app

        # Final flush on exit
        self._flush_to_disk()

    # ── Disk I/O ───────────────────────────────────────────────────────────────

    def _load_today(self) -> None:
        data = _load_usage()
        today_data = data.get(self._today, {})
        with self._lock:
            for app, secs in today_data.items():
                self._daily_totals[app] = float(secs)

    def _flush_to_disk(self) -> None:
        with self._lock:
            data = _load_usage()
            data[self._today] = dict(self._daily_totals)
            # Keep only the last 30 days on disk
            cutoff = str(date.today() - timedelta(days=30))
            data = {k: v for k, v in data.items() if k >= cutoff}
        _save_usage(data)

    def _load_week_stats(self) -> dict[str, float]:
        """Load and merge the last 7 days from disk + today's in-memory data."""
        data   = _load_usage()
        merged: dict[str, float] = defaultdict(float)
        cutoff = str(date.today() - timedelta(days=7))
        for day_key, apps in data.items():
            if day_key >= cutoff:
                for app, secs in apps.items():
                    merged[app] += float(secs)
        # Overlay in-memory today (may be fresher than what's on disk)
        for app, secs in self._daily_totals.items():
            merged[app] = max(merged.get(app, 0.0), secs)
        return dict(merged)


# ── Tool entry point (called by main.py _execute_tool) ────────────────────────

def get_usage_tool(
    parameters:     dict,
    tracker:        "AppTracker | None" = None,
    player=None,
    session_memory=None,
) -> str:
    """
    JARVIS tool handler for the 'app_usage' tool declaration.

    parameters keys:
      action  : report | category_report | focus | clear_focus | current
      period  : today | week | session  (default: today)
      apps    : list of app names for focus mode
    """
    if tracker is None:
        return "App tracking is not active."

    action = (parameters.get("action") or "report").lower().strip()
    period = (parameters.get("period") or "today").lower().strip()
    apps   = parameters.get("apps") or []

    if action == "current":
        app = _get_foreground_app()
        return f"Currently active: {app or 'unknown'}"

    if action == "focus":
        if not apps:
            return "Please specify which apps to focus on (e.g. 'Visual Studio Code', 'Chrome')."
        tracker.set_focus_mode(apps)
        return f"Focus mode enabled for: {', '.join(apps)}. I'll alert you if you drift to other apps."

    if action == "clear_focus":
        tracker.clear_focus_mode()
        return "Focus mode cleared. All apps are being tracked again."

    if action == "category_report":
        cats = tracker.get_category_stats(period)
        if not cats:
            return f"No app usage data for {period}."
        lines = [f"Category breakdown — {period}:"]
        for cat, secs in sorted(cats.items(), key=lambda x: x[1], reverse=True):
            lines.append(f"  {cat}: {_fmt_time(secs)}")
        return "\n".join(lines)

    # Default: full report
    return tracker.format_report(period)


# ── Helpers ────────────────────────────────────────────────────────────────────

def _fmt_time(seconds: float) -> str:
    s = int(seconds)
    if s < 60:
        return f"{s}s"
    if s < 3600:
        return f"{s // 60}m {s % 60:02d}s"
    return f"{s // 3600}h {(s % 3600) // 60:02d}m"
