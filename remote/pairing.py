"""
remote/pairing.py — One-time short-lived QR pairing session manager.
"""
from __future__ import annotations

import base64
import io
import json
import secrets
import socket
import threading
import time
from typing import Any

from remote.config import load_remote_config, BASE_DIR
from remote.audit_log import audit_logger

try:
    import qrcode
    _QRCODE_OK = True
except ImportError:
    _QRCODE_OK = False

_lock = threading.Lock()

def _get_best_ip() -> str:
    """Finds best LAN or Tailscale IPv4 address for pairing QR."""
    # First check for Tailscale (100.64.0.0/10 range: 100.64.x.x - 100.127.x.x)
    try:
        for info in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET):
            ip = info[4][0]
            if ip.startswith("100."):
                return ip
    except Exception:
        pass

    # Next check normal LAN route trick
    for probe in ("8.8.8.8", "1.1.1.1", "192.168.1.1"):
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.settimeout(0.5)
            s.connect((probe, 80))
            ip = s.getsockname()[0]
            s.close()
            if not ip.startswith("127."):
                return ip
        except Exception:
            pass

    return "127.0.0.1"


PAIRING_SESSIONS_FILE = load_remote_config().get("_pairing_file") or (BASE_DIR / "data" / "pairing_sessions.json")

class PairingManager:
    def __init__(self):
        self._file = PAIRING_SESSIONS_FILE

    def _load_unlocked(self) -> dict[str, dict[str, Any]]:
        if not self._file.exists():
            return {}
        try:
            return json.loads(self._file.read_text(encoding="utf-8"))
        except Exception:
            return {}

    def _save_unlocked(self, sessions: dict[str, dict[str, Any]]) -> None:
        try:
            self._file.write_text(json.dumps(sessions, indent=2), encoding="utf-8")
        except Exception as e:
            print(f"[Pairing] Save error: {e}")

    def clean_expired(self) -> None:
        now = time.time()
        with _lock:
            sessions = self._load_unlocked()
            valid = {
                t: s for t, s in sessions.items()
                if s.get("expires_at", 0) > now and not s.get("used", False)
            }
            self._save_unlocked(valid)

    def create_pairing_session(self, host_override: str = "") -> dict[str, Any]:
        """
        Creates a new short-lived pairing session.
        Returns a dictionary with pairing metadata and QR code string/base64.
        """
        self.clean_expired()
        cfg = load_remote_config()
        expiry_sec = cfg.get("pairing_token_expiry_sec", 300)
        port = cfg.get("port", 8765)
        host = host_override or _get_best_ip()

        token = f"pair_{secrets.token_urlsafe(24)}"
        now = time.time()
        expires_at = now + expiry_sec

        with _lock:
            sessions = self._load_unlocked()
            sessions[token] = {
                "created_at": now,
                "expires_at": expires_at,
                "used": False,
                "host": host,
                "port": port,
            }
            self._save_unlocked(sessions)

        ws_url = f"ws://{host}:{port}/ws/remote"
        http_url = f"http://{host}:{port}"
        qr_payload = {
            "v": 1,
            "gateway_url": ws_url,
            "http_url": http_url,
            "pairing_token": token,
            "expires_at": int(expires_at),
        }
        qr_json = json.dumps(qr_payload)

        qr_b64 = ""
        if _QRCODE_OK:
            try:
                qr = qrcode.QRCode(
                    version=1,
                    error_correction=qrcode.constants.ERROR_CORRECT_M,
                    box_size=6,
                    border=2,
                )
                qr.add_data(qr_json)
                qr.make(fit=True)
                img = qr.make_image(fill_color="black", back_color="white")
                buf = io.BytesIO()
                img.save(buf, format="PNG")
                qr_b64 = base64.b64encode(buf.getvalue()).decode("ascii")
            except Exception as e:
                print(f"[Pairing] QR generation failed: {e}")

        audit_logger.log_event("PAIRING_SESSION_CREATED", f"New pairing token generated. Expires in {expiry_sec}s.")

        return {
            "pairing_token": token,
            "expires_at": expires_at,
            "expires_in_seconds": expiry_sec,
            "gateway_url": ws_url,
            "http_url": http_url,
            "qr_json": qr_json,
            "qr_png_base64": qr_b64,
        }

    def validate_and_consume_token(self, token: str) -> bool:
        """
        Validates the pairing token and immediately consumes it (single-use).
        """
        now = time.time()
        with _lock:
            sessions = self._load_unlocked()
            session = sessions.get(token)
            if not session:
                return False
            if session.get("used") or session.get("expires_at", 0) < now:
                return False
            session["used"] = True
            self._save_unlocked(sessions)
            return True

pairing_manager = PairingManager()
