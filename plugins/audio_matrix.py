"""
plugins/audio_matrix.py — Advanced Per-Application Audio Matrix & Mixer for JARVIS.

Allows JARVIS to granularly inspect and control individual application volume levels,
mute/unmute specific programs (e.g., Discord, Spotify, Chrome, games), duck background
audio streams, or silence all applications except a designated program.
"""
from __future__ import annotations

import re
from typing import Optional

PLUGIN = {
    "name": "audio_matrix",
    "description": (
        "Controls per-application volume, mutes specific apps (Discord, Spotify, games, Chrome), "
        "ducks background audio, or lists active audio streams. Use this whenever the user "
        "asks to change volume for a SPECIFIC application (e.g. 'turn down Spotify to 30%', "
        "'mute Discord', 'mute everything except game', 'list what apps are playing sound'). "
        "Do NOT use computer_settings for single-app audio controls."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "action": {
                "type": "STRING",
                "description": (
                    "Action to execute: 'set_volume' | 'mute' | 'unmute' | 'mute_all' | "
                    "'unmute_all' | 'mute_all_except' | 'duck' | 'list'"
                ),
            },
            "app_name": {
                "type": "STRING",
                "description": (
                    "Target application name (e.g. 'Spotify', 'Discord', 'Chrome', 'Edge', 'Game'). "
                    "Case-insensitive partial matching is supported."
                ),
            },
            "volume": {
                "type": "INTEGER",
                "description": "Target volume percentage from 0 to 100 (for 'set_volume' or 'duck').",
            },
        },
        "required": ["action"],
    },
}


def _match_process(proc_name: str, target: str) -> bool:
    """Fuzzy match process name against target string."""
    if not proc_name or not target:
        return False
    clean_p = proc_name.lower().replace(".exe", "").strip()
    clean_t = target.lower().replace(".exe", "").strip()
    return clean_t in clean_p or clean_p in clean_t


def _get_audio_sessions():
    """Import and return active sessions with COM initialization."""
    import comtypes
    try:
        comtypes.CoInitialize()
    except Exception:
        pass
    from pycaw.pycaw import AudioUtilities, ISimpleAudioVolume
    sessions = AudioUtilities.GetAllSessions()
    return sessions, ISimpleAudioVolume


def run(parameters: dict, player=None, session_memory=None) -> str:
    action = parameters.get("action", "").lower().strip()
    target_app = parameters.get("app_name", "").strip()
    raw_vol = parameters.get("volume")

    # Volume clamping
    if raw_vol is not None:
        try:
            vol_int = max(0, min(100, int(raw_vol)))
        except (ValueError, TypeError):
            vol_int = 50
    else:
        vol_int = 30 if action == "duck" else 50

    try:
        import comtypes
        try:
            comtypes.CoInitialize()
        except Exception:
            pass

        sessions, ISimpleAudioVolume = _get_audio_sessions()

        active_apps = []
        for s in sessions:
            if s.Process and s.Process.name():
                active_apps.append((s.Process.name(), s))

        if action in ("list", "get_sessions", "status"):
            if not active_apps:
                res = "No active application audio sessions found."
            else:
                details = []
                seen = set()
                for name, s in active_apps:
                    if name in seen:
                        continue
                    seen.add(name)
                    try:
                        vol_ctl = s._ctl.QueryInterface(ISimpleAudioVolume)
                        pct = int(round(vol_ctl.GetMasterVolume() * 100))
                        is_muted = vol_ctl.GetMute() == 1
                        status = "muted" if is_muted else f"{pct}%"
                        clean_name = name.replace(".exe", "")
                        details.append(f"{clean_name} ({status})")
                    except Exception:
                        details.append(name.replace(".exe", ""))
                res = f"Active audio streams: {', '.join(details)}."

        elif action == "mute_all":
            count = 0
            for name, s in active_apps:
                try:
                    vol_ctl = s._ctl.QueryInterface(ISimpleAudioVolume)
                    vol_ctl.SetMute(1, None)
                    count += 1
                except Exception:
                    pass
            res = f"Muted all {count} active application audio streams."

        elif action == "unmute_all":
            count = 0
            for name, s in active_apps:
                try:
                    vol_ctl = s._ctl.QueryInterface(ISimpleAudioVolume)
                    vol_ctl.SetMute(0, None)
                    count += 1
                except Exception:
                    pass
            res = f"Unmuted all {count} active application audio streams."

        elif action == "mute_all_except":
            if not target_app:
                res = "Sir, please specify which app to keep audible."
            else:
                muted_names = []
                kept_name = None
                for name, s in active_apps:
                    try:
                        vol_ctl = s._ctl.QueryInterface(ISimpleAudioVolume)
                        if _match_process(name, target_app):
                            vol_ctl.SetMute(0, None)
                            kept_name = name.replace(".exe", "")
                        else:
                            vol_ctl.SetMute(1, None)
                            muted_names.append(name.replace(".exe", ""))
                    except Exception:
                        pass
                if kept_name:
                    res = f"Isolated audio to {kept_name}; muted {len(muted_names)} other streams."
                else:
                    res = f"Could not find '{target_app}' among active audio streams to isolate."

        elif action == "duck":
            # Lower everything else to vol_int, keep target app at its current level or full
            ducked = []
            target_found = False
            for name, s in active_apps:
                try:
                    vol_ctl = s._ctl.QueryInterface(ISimpleAudioVolume)
                    if target_app and _match_process(name, target_app):
                        target_found = True
                        vol_ctl.SetMute(0, None)
                    else:
                        vol_ctl.SetMasterVolume(vol_int / 100.0, None)
                        ducked.append(name.replace(".exe", ""))
                except Exception:
                    pass
            if ducked:
                res = f"Ducked background audio ({', '.join(set(ducked))}) to {vol_int}%."
            else:
                res = "No background audio streams were available to duck."

        elif action in ("set_volume", "mute", "unmute"):
            if not target_app:
                res = f"Sir, please specify the target application name for {action}."
            else:
                matches = []
                for name, s in active_apps:
                    if _match_process(name, target_app):
                        matches.append((name, s))

                if not matches:
                    res = f"No active audio stream found for '{target_app}'. The app might not be playing audio."
                else:
                    for name, s in matches:
                        vol_ctl = s._ctl.QueryInterface(ISimpleAudioVolume)
                        if action == "set_volume":
                            vol_ctl.SetMasterVolume(vol_int / 100.0, None)
                            vol_ctl.SetMute(0, None)
                        elif action == "mute":
                            vol_ctl.SetMute(1, None)
                        elif action == "unmute":
                            vol_ctl.SetMute(0, None)

                    display_name = matches[0][0].replace(".exe", "")
                    if action == "set_volume":
                        res = f"Set {display_name} volume to {vol_int}%."
                    elif action == "mute":
                        res = f"Muted {display_name}."
                    else:
                        res = f"Unmuted {display_name}."
        else:
            res = f"Unknown audio matrix action '{action}'."

    except Exception as e:
        res = f"Sir, audio matrix control encountered an error: {e}"
    finally:
        try:
            import comtypes
            comtypes.CoUninitialize()
        except Exception:
            pass

    if player:
        try:
            player.write_log(f"JARVIS: {res}")
        except Exception:
            pass

    return res
