"""
remote/auth.py — Authorized device management and cryptographic validation.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import secrets
import threading
import time
import uuid
from datetime import datetime
from typing import Any

from remote.config import AUTH_DEVICES_FILE
from remote.audit_log import audit_logger

_lock = threading.Lock()

def _hash_token(raw_token: str) -> str:
    """SHA-256 hash for secure storage of auth tokens."""
    return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()

class DeviceAuthManager:
    def __init__(self):
        self._devices: dict[str, dict[str, Any]] = {}
        self._revocation_cache: set[str] = set()
        self.load_devices()

    def load_devices(self) -> None:
        with _lock:
            if not AUTH_DEVICES_FILE.exists():
                self._devices = {}
                self._save_unlocked()
                return
            try:
                data = json.loads(AUTH_DEVICES_FILE.read_text(encoding="utf-8"))
                self._devices = data.get("devices", {})
                self._revocation_cache = {
                    d_id for d_id, d_data in self._devices.items()
                    if d_data.get("status") == "revoked"
                }
            except Exception as e:
                print(f"[DeviceAuth] Failed to load devices: {e}")
                self._devices = {}

    def _save_unlocked(self) -> None:
        try:
            payload = {
                "version": 1,
                "updated_at": datetime.now().isoformat(),
                "devices": self._devices,
            }
            AUTH_DEVICES_FILE.write_text(
                json.dumps(payload, indent=4, ensure_ascii=False),
                encoding="utf-8"
            )
        except Exception as e:
            print(f"[DeviceAuth] Failed to save devices: {e}")

    def register_device(
        self,
        device_name: str,
        device_model: str = "Android",
        client_ip: str = "127.0.0.1"
    ) -> tuple[str, str]:
        """
        Registers a new authorized device.
        Returns (device_id, raw_auth_token).
        The raw token is only returned ONCE to be saved by the client.
        """
        device_id = f"dev_{uuid.uuid4().hex[:12]}"
        raw_token = f"jarvis_sec_{secrets.token_hex(32)}"
        token_hash = _hash_token(raw_token)

        now = datetime.now().isoformat()
        record = {
            "device_id": device_id,
            "device_name": device_name or "Android Phone",
            "device_model": device_model,
            "token_hash": token_hash,
            "created_at": now,
            "last_seen_at": now,
            "last_ip": client_ip,
            "status": "authorized",
            "permissions": {
                "voice": True,
                "files_search": True,
                "files_download": True,
                "system_status": True,
                "app_control": True,
                "shutdown": True,
            }
        }

        with _lock:
            self._devices[device_id] = record
            if device_id in self._revocation_cache:
                self._revocation_cache.remove(device_id)
            self._save_unlocked()

        audit_logger.log_event(
            "DEVICE_REGISTERED",
            f"Device '{device_name}' registered successfully.",
            device_id=device_id,
            client_ip=client_ip
        )
        return device_id, raw_token

    def validate_token(self, device_id: str, raw_token: str, client_ip: str = "") -> bool:
        """Validates that a device exists, is authorized, and the token hash matches."""
        with _lock:
            if device_id in self._revocation_cache:
                return False
            dev = self._devices.get(device_id)
            if not dev or dev.get("status") != "authorized":
                return False

            expected_hash = dev.get("token_hash", "")
            actual_hash = _hash_token(raw_token)
            # Constant-time comparison to prevent timing attacks
            if not hmac.compare_digest(expected_hash, actual_hash):
                return False

            dev["last_seen_at"] = datetime.now().isoformat()
            if client_ip:
                dev["last_ip"] = client_ip
            self._save_unlocked()
            return True

    def revoke_device(self, device_id: str, reason: str = "User revoked") -> bool:
        """Immediately revokes access for a device."""
        with _lock:
            dev = self._devices.get(device_id)
            if not dev:
                return False
            dev["status"] = "revoked"
            dev["revoked_at"] = datetime.now().isoformat()
            dev["revocation_reason"] = reason
            self._revocation_cache.add(device_id)
            self._save_unlocked()

        audit_logger.log_event(
            "DEVICE_REVOKED",
            f"Device revoked: {reason}",
            device_id=device_id,
            level="WARNING"
        )
        return True

    def rename_device(self, device_id: str, new_name: str) -> bool:
        with _lock:
            dev = self._devices.get(device_id)
            if not dev:
                return False
            dev["device_name"] = new_name
            self._save_unlocked()
        return True

    def is_revoked(self, device_id: str) -> bool:
        return device_id in self._revocation_cache

    def list_devices(self) -> list[dict[str, Any]]:
        with _lock:
            return [
                {
                    "device_id": d["device_id"],
                    "device_name": d["device_name"],
                    "device_model": d.get("device_model", "Android"),
                    "status": d.get("status", "authorized"),
                    "created_at": d.get("created_at"),
                    "last_seen_at": d.get("last_seen_at"),
                    "last_ip": d.get("last_ip", ""),
                }
                for d in self._devices.values()
            ]

device_auth_manager = DeviceAuthManager()
