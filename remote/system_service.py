"""
remote/system_service.py — Hardware telemetry and two-step confirmation for dangerous actions.
"""
from __future__ import annotations

import os
import platform
import subprocess
import threading
import time
import uuid
from typing import Any

import psutil

from remote.config import load_remote_config
from remote.audit_log import audit_logger
from actions.open_app import open_app

_OS = platform.system()
_lock = threading.Lock()

# ── NVML helpers for GPU telemetry ──────────────────────────────────────────
_nvml_ok = None
_nvml_handle = None

def _get_gpu_metrics() -> dict[str, Any]:
    global _nvml_ok, _nvml_handle
    if _nvml_ok is False:
        return {"load_percent": -1, "memory_percent": -1, "temp_c": -1, "name": "N/A"}

    try:
        if _nvml_handle is None:
            import pynvml
            pynvml.nvmlInit()
            _nvml_handle = pynvml.nvmlDeviceGetHandleByIndex(0)
            _nvml_ok = True

        import pynvml
        util = pynvml.nvmlDeviceGetUtilizationRates(_nvml_handle)
        mem = pynvml.nvmlDeviceGetMemoryInfo(_nvml_handle)
        temp = -1
        try:
            temp = pynvml.nvmlDeviceGetTemperature(_nvml_handle, pynvml.NVML_TEMPERATURE_GPU)
        except Exception:
            pass

        name = pynvml.nvmlDeviceGetName(_nvml_handle)
        if isinstance(name, bytes):
            name = name.decode("utf-8")

        mem_pct = round((mem.used / mem.total) * 100, 1) if mem.total else 0
        return {
            "load_percent": float(util.gpu),
            "memory_percent": mem_pct,
            "temp_c": float(temp),
            "name": name,
        }
    except Exception:
        _nvml_ok = False
        return {"load_percent": -1, "memory_percent": -1, "temp_c": -1, "name": "N/A"}


class RemoteSystemService:
    def __init__(self):
        # challenge_id -> { "action": str, "details": dict, "created_at": float, "expires_at": float, "device_id": str }
        self._pending_challenges: dict[str, dict[str, Any]] = {}
        self._last_net = psutil.net_io_counters()
        self._last_net_t = time.time()

    def get_telemetry(self) -> dict[str, Any]:
        """Collects real-time hardware metrics."""
        cpu = psutil.cpu_percent(interval=None)
        mem = psutil.virtual_memory()

        # Battery
        bat = psutil.sensors_battery()
        battery_data = {
            "percent": round(bat.percent, 1) if bat else 100,
            "power_plugged": bat.power_plugged if bat else True,
            "has_battery": bat is not None,
        }

        # Disk
        disk = psutil.disk_usage("C:\\" if _OS == "Windows" else "/")
        disk_data = {
            "percent": round(disk.percent, 1),
            "free_gb": round(disk.free / (1024 ** 3), 1),
            "total_gb": round(disk.total / (1024 ** 3), 1),
        }

        # Network speed
        now = time.time()
        dt = max(now - self._last_net_t, 0.1)
        net_curr = psutil.net_io_counters()
        up_kbps = round(((net_curr.bytes_sent - self._last_net.bytes_sent) / dt) / 1024, 1)
        down_kbps = round(((net_curr.bytes_recv - self._last_net.bytes_recv) / dt) / 1024, 1)
        self._last_net = net_curr
        self._last_net_t = now

        gpu = _get_gpu_metrics()

        return {
            "timestamp": now,
            "os": _OS,
            "cpu_percent": round(cpu, 1),
            "ram_percent": round(mem.percent, 1),
            "ram_used_gb": round(mem.used / (1024 ** 3), 1),
            "ram_total_gb": round(mem.total / (1024 ** 3), 1),
            "gpu": gpu,
            "battery": battery_data,
            "disk": disk_data,
            "network": {
                "upload_kbps": up_kbps,
                "download_kbps": down_kbps,
            },
        }

    def launch_application(self, app_name: str, device_id: str = "UNKNOWN") -> dict[str, Any]:
        """Launches an approved application."""
        cfg = load_remote_config()
        allowed_apps = [a.lower().strip() for a in cfg.get("allowed_applications", [])]
        clean_name = app_name.lower().strip()

        is_allowed = any(clean_name == a or a in clean_name or clean_name in a for a in allowed_apps)
        if not is_allowed:
            audit_logger.log_event(
                "APP_LAUNCH_BLOCKED",
                f"Attempt to launch non-allowlisted application '{app_name}' was blocked.",
                device_id=device_id,
                level="WARNING"
            )
            return {
                "status": "error",
                "message": f"Application '{app_name}' is not in the approved application allowlist."
            }

        res = open_app(parameters={"app_name": app_name})
        audit_logger.log_event(
            "APP_LAUNCHED",
            f"Application '{app_name}' launched: {res}",
            device_id=device_id
        )
        return {
            "status": "success",
            "message": res or f"Opened {app_name} on your lab laptop."
        }

    def create_dangerous_challenge(
        self,
        action: str,
        details: dict[str, Any] | None = None,
        device_id: str = "UNKNOWN"
    ) -> dict[str, Any]:
        """
        Creates a challenge for high-risk operations (shutdown, restart, etc.).
        """
        cfg = load_remote_config()
        expiry_sec = cfg.get("challenge_expiry_sec", 60)
        challenge_id = f"chal_{uuid.uuid4().hex[:12]}"
        now = time.time()

        with _lock:
            self._pending_challenges[challenge_id] = {
                "action": action,
                "details": details or {},
                "created_at": now,
                "expires_at": now + expiry_sec,
                "device_id": device_id,
            }

        audit_logger.log_event(
            "CHALLENGE_CREATED",
            f"Confirmation challenge generated for '{action}'",
            device_id=device_id
        )

        messages = {
            "shutdown": "Shutdown will power off the lab laptop. Please confirm.",
            "restart": "Restart will reboot the lab laptop. Please confirm.",
            "delete_file": "File deletion cannot be undone. Please confirm.",
        }

        return {
            "status": "confirmation_required",
            "challenge_id": challenge_id,
            "action": action,
            "message": messages.get(action, f"This action requires confirmation: {action}"),
            "expires_in_seconds": expiry_sec,
        }

    def verify_and_execute_challenge(
        self,
        challenge_id: str,
        device_id: str = "UNKNOWN"
    ) -> dict[str, Any]:
        """
        Validates challenge token and executes the high-risk action.
        """
        now = time.time()
        with _lock:
            chal = self._pending_challenges.pop(challenge_id, None)

        if not chal or chal["expires_at"] < now:
            audit_logger.log_event(
                "CHALLENGE_FAILED",
                f"Expired or invalid challenge confirmation attempt: {challenge_id}",
                device_id=device_id,
                level="WARNING"
            )
            return {
                "status": "error",
                "message": "Confirmation challenge expired or invalid. Please request the action again."
            }

        action = chal["action"]
        audit_logger.log_event(
            "CHALLENGE_EXECUTED",
            f"Action '{action}' confirmed and executed.",
            device_id=device_id
        )

        if action == "shutdown":
            def _delayed_shutdown():
                time.sleep(2)
                if _OS == "Windows":
                    subprocess.run(["shutdown", "/s", "/t", "5", "/c", "JARVIS Remote Shutdown confirmed"], shell=False)
                else:
                    subprocess.run(["shutdown", "-h", "now"], shell=False)

            threading.Thread(target=_delayed_shutdown, daemon=True).start()
            return {
                "status": "success",
                "message": "Shutdown confirmed. The lab laptop is powering off."
            }

        elif action == "restart":
            def _delayed_restart():
                time.sleep(2)
                if _OS == "Windows":
                    subprocess.run(["shutdown", "/r", "/t", "5", "/c", "JARVIS Remote Restart confirmed"], shell=False)
                else:
                    subprocess.run(["shutdown", "-r", "now"], shell=False)

            threading.Thread(target=_delayed_restart, daemon=True).start()
            return {
                "status": "success",
                "message": "Restart confirmed. The lab laptop is restarting."
            }

        return {
            "status": "success",
            "message": f"Action '{action}' completed."
        }

remote_system_service = RemoteSystemService()
