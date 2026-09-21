"""
remote/config.py — Configuration and security allowlists for JARVIS Phone Remote.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any

def _get_base_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    return Path(__file__).resolve().parent.parent

BASE_DIR = _get_base_dir()
CONFIG_DIR = BASE_DIR / "config"
CONFIG_FILE = CONFIG_DIR / "remote_config.json"
DATA_DIR = BASE_DIR / "data"
AUTH_DEVICES_FILE = CONFIG_DIR / "authorized_devices.json"
AUDIT_LOG_FILE = DATA_DIR / "remote_audit.log"
TRANSFERS_DIR = DATA_DIR / "transfers" / "temp"

# Ensure data and config directories exist
CONFIG_DIR.mkdir(parents=True, exist_ok=True)
DATA_DIR.mkdir(parents=True, exist_ok=True)
TRANSFERS_DIR.mkdir(parents=True, exist_ok=True)

DEFAULT_CONFIG: dict[str, Any] = {
    "enabled": True,
    "port": 8765,
    "host": "0.0.0.0",
    "pairing_token_expiry_sec": 300,  # 5 minutes for QR pairing token
    "auth_token_expiry_days": 365,
    "rate_limit_rpm": 60,            # requests per minute per device
    "max_transfer_mb": 500,           # maximum single file/bundle transfer size
    "temp_cleanup_sec": 900,          # 15 minutes to cleanup temporary zip packages
    "challenge_expiry_sec": 60,       # 60 seconds to confirm dangerous actions
    "allowed_directories": [
        "D:/Projects",
        "D:/Documents",
        "D:/Datasets",
        "F:/jarvis",
        str(Path.home() / "Documents"),
        str(Path.home() / "Downloads"),
        str(Path.home() / "Desktop"),
        str(Path.home() / "Projects"),
    ],
    "blocked_directories": [
        "C:/Windows",
        "C:/Program Files",
        "C:/Program Files (x86)",
        str(Path.home() / "AppData"),
        str(BASE_DIR / ".git"),
        str(BASE_DIR / "config" / "certs"),
    ],
    "blocked_files": [
        "api_keys.json",
        ".env",
        "id_rsa",
        "id_ed25519",
        "authorized_devices.json",
    ],
    "allowed_applications": [
        "chrome",
        "google chrome",
        "code",
        "vscode",
        "visual studio code",
        "antigravity",
        "whatsapp",
        "telegram",
        "spotify",
        "terminal",
        "cmd",
        "powershell",
        "vlc",
        "notepad",
        "explorer",
        "edge",
        "firefox",
        "brave",
    ],
}

def load_remote_config() -> dict[str, Any]:
    """Loads configuration from config/remote_config.json or writes defaults."""
    if not CONFIG_FILE.exists():
        save_remote_config(DEFAULT_CONFIG)
        return dict(DEFAULT_CONFIG)
    try:
        data = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
        merged = dict(DEFAULT_CONFIG)
        merged.update(data)
        return merged
    except Exception:
        return dict(DEFAULT_CONFIG)

def save_remote_config(cfg: dict[str, Any]) -> None:
    """Saves configuration to config/remote_config.json."""
    try:
        CONFIG_FILE.write_text(json.dumps(cfg, indent=4, ensure_ascii=False), encoding="utf-8")
    except Exception as e:
        print(f"[RemoteConfig] Failed to save config: {e}")
