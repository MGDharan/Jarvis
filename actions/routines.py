"""Persistent weekday routines and a small calendar/weather briefing."""
from __future__ import annotations

import datetime as dt
import json
import re
import threading
from pathlib import Path
from typing import Callable

import requests

BASE_DIR = Path(__file__).resolve().parent.parent
ROUTINES_FILE = BASE_DIR / "config" / "routines.json"
_DEFAULT_ROUTINE = {
    "id": "weekday_morning_brief",
    "name": "Weekday morning briefing",
    "enabled": True,
    "weekdays": [0, 1, 2, 3, 4],
    "time": "08:00",
    "city": "Istanbul",
    "include_weather": True,
    "include_calendar": True,
}


def _load() -> list[dict]:
    try:
        value = json.loads(ROUTINES_FILE.read_text(encoding="utf-8"))
        return value if isinstance(value, list) else [_DEFAULT_ROUTINE.copy()]
    except Exception:
        return [_DEFAULT_ROUTINE.copy()]


def _save(routines: list[dict]) -> None:
    ROUTINES_FILE.parent.mkdir(parents=True, exist_ok=True)
    ROUTINES_FILE.write_text(json.dumps(routines, indent=2), encoding="utf-8")


def list_routines() -> list[dict]:
    return _load()


def save_routine(routine: dict) -> dict:
    item = _DEFAULT_ROUTINE | {k: v for k, v in routine.items() if k in _DEFAULT_ROUTINE}
    item["id"] = str(routine.get("id") or _DEFAULT_ROUTINE["id"])
    item["time"] = str(item["time"])
    dt.datetime.strptime(item["time"], "%H:%M")
    item["weekdays"] = sorted({int(day) for day in item["weekdays"] if 0 <= int(day) <= 6})
    routines = [r for r in _load() if r.get("id") != item["id"]]
    routines.append(item)
    _save(routines)
    return item


def set_routine_enabled(routine_id: str, enabled: bool) -> bool:
    routines = _load()
    found = False
    for routine in routines:
        if routine.get("id") == routine_id:
            routine["enabled"] = bool(enabled)
            found = True
    if found:
        _save(routines)
    return found


def _weather(city: str) -> str:
    try:
        response = requests.get(
            f"https://wttr.in/{requests.utils.quote(city)}?format=3",
            timeout=8,
            headers={"User-Agent": "JARVIS/1.0"},
        )
        response.raise_for_status()
        return response.text.strip()
    except Exception as exc:
        return f"Weather unavailable ({exc})"


def _calendar() -> str:
    today = dt.date.today()
    events: list[str] = []
    try:
        import win32com.client  # type: ignore
        outlook = win32com.client.Dispatch("Outlook.Application").GetNamespace("MAPI")
        calendar = outlook.GetDefaultFolder(9).Items
        calendar.IncludeRecurrences = True
        calendar.Sort("[Start]")
        start = dt.datetime.combine(today, dt.time.min)
        end = start + dt.timedelta(days=1)
        for event in calendar:
            event_start = event.Start.replace(tzinfo=None)
            if start <= event_start < end:
                events.append(f"{event_start:%H:%M} {event.Subject}")
            if event_start >= end:
                break
    except Exception:
        pass

    if events:
        return "Today's calendar: " + "; ".join(events[:8])
    return "No calendar events found for today."


def build_briefing(routine: dict) -> str:
    parts = [f"Good morning. It is {dt.datetime.now():%A, %B %d}. "]
    if routine.get("include_weather", True):
        parts.append(_weather(str(routine.get("city") or "Istanbul")) + ".")
    if routine.get("include_calendar", True):
        parts.append(_calendar())
    return " ".join(parts)


class RoutineRunner:
    def __init__(self, callback: Callable[[str], None], log: Callable[[str], None] = print):
        self._callback = callback
        self._log = log
        self._thread: threading.Thread | None = None
        self._stop = threading.Event()
        self._last_fired: dict[str, str] = {}

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, daemon=True, name="JarvisRoutineRunner")
        self._thread.start()

    def _run(self) -> None:
        while not self._stop.wait(20):
            now = dt.datetime.now()
            stamp = now.strftime("%Y-%m-%d")
            for routine in list_routines():
                if not routine.get("enabled", True) or now.weekday() not in routine.get("weekdays", []):
                    continue
                if now.strftime("%H:%M") != routine.get("time") or self._last_fired.get(routine.get("id")) == stamp:
                    continue
                self._last_fired[routine.get("id")] = stamp
                try:
                    self._callback(build_briefing(routine))
                    self._log(f"[Routine] Fired: {routine.get('name', routine.get('id'))}")
                except Exception as exc:
                    self._log(f"[Routine] Failed: {exc}")

    def stop(self) -> None:
        self._stop.set()
