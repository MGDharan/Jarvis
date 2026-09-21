"""
remote/audit_log.py — Tamper-evident audit logging for JARVIS remote operations.
"""
from __future__ import annotations

import logging
import threading
from datetime import datetime
from typing import Any
from remote.config import AUDIT_LOG_FILE

_lock = threading.Lock()

class AuditLogger:
    def __init__(self):
        self._logger = logging.getLogger("jarvis_remote_audit")
        self._logger.setLevel(logging.INFO)
        if not self._logger.handlers:
            handler = logging.FileHandler(str(AUDIT_LOG_FILE), encoding="utf-8")
            formatter = logging.Formatter(
                fmt="[%(asctime)s] [%(levelname)s] [DEV:%(device_id)s] [IP:%(client_ip)s] %(message)s",
                datefmt="%Y-%m-%d %H:%M:%S"
            )
            handler.setFormatter(formatter)
            self._logger.addHandler(handler)

    def log_event(
        self,
        event_type: str,
        message: str,
        device_id: str = "SYSTEM",
        client_ip: str = "127.0.0.1",
        level: str = "INFO",
        metadata: dict[str, Any] | None = None
    ) -> None:
        with _lock:
            extra = {"device_id": device_id, "client_ip": client_ip}
            meta_str = f" | meta={metadata}" if metadata else ""
            log_line = f"[{event_type}] {message}{meta_str}"
            if level == "WARNING":
                self._logger.warning(log_line, extra=extra)
            elif level == "ERROR":
                self._logger.error(log_line, extra=extra)
            else:
                self._logger.info(log_line, extra=extra)

audit_logger = AuditLogger()
