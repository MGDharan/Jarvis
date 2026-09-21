"""
remote/notifications.py — Push notification broadcaster and event history.
"""
from __future__ import annotations

import asyncio
import base64
import json
import threading
import time
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

from remote.audit_log import audit_logger

_lock = threading.Lock()

class NotificationManager:
    def __init__(self):
        self._history: list[dict[str, Any]] = []
        self._listeners: set[Any] = set()  # active WebSocket instances
        self._last_event_times: dict[str, float] = {}

    def register_client(self, ws: Any) -> None:
        with _lock:
            self._listeners.add(ws)

    def unregister_client(self, ws: Any) -> None:
        with _lock:
            self._listeners.discard(ws)

    async def broadcast_event(
        self,
        event_type: str,
        title: str,
        message: str,
        severity: str = "info",
        image_path: str | Path | None = None,
        metadata: dict[str, Any] | None = None,
        cooldown_sec: float = 0.0,
    ) -> None:
        """
        Broadcasts an alert event to all connected phone clients with rate/cooldown protection.
        """
        now = time.time()
        with _lock:
            if cooldown_sec > 0:
                last = self._last_event_times.get(event_type, 0.0)
                if (now - last) < cooldown_sec:
                    return
                self._last_event_times[event_type] = now

        image_b64 = None
        if image_path:
            p = Path(image_path)
            if p.exists() and p.is_file():
                try:
                    with open(p, "rb") as f:
                        image_b64 = base64.b64encode(f.read()).decode("ascii")
                except Exception as e:
                    print(f"[Notifications] Image encode failed: {e}")

        notification_id = f"notif_{uuid.uuid4().hex[:12]}"
        record = {
            "id": notification_id,
            "timestamp": datetime.now().isoformat(),
            "type": event_type,
            "title": title,
            "message": message,
            "severity": severity,  # info | warning | critical
            "has_image": image_b64 is not None,
            "image_b64": image_b64,
            "metadata": metadata or {},
        }

        with _lock:
            self._history.insert(0, record)
            if len(self._history) > 100:
                self._history.pop()
            active_sockets = list(self._listeners)

        payload = {
            "type": "notification",
            "data": record,
        }
        raw_msg = json.dumps(payload)

        # Broadcast asynchronously to all active phone sessions
        dead_clients = []
        for ws in active_sockets:
            try:
                await ws.send_text(raw_msg)
            except Exception:
                dead_clients.append(ws)

        if dead_clients:
            with _lock:
                for d in dead_clients:
                    self._listeners.discard(d)

        audit_logger.log_event(
            "NOTIFICATION_DISPATCHED",
            f"[{event_type.upper()}] {title}: {message}",
            metadata={"severity": severity}
        )

    def dispatch_sync(
        self,
        event_type: str,
        title: str,
        message: str,
        severity: str = "info",
        image_path: str | Path | None = None,
        metadata: dict[str, Any] | None = None,
        cooldown_sec: float = 0.0,
    ) -> None:
        """Thread-safe synchronous trigger for background worker threads."""
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                asyncio.run_coroutine_threadsafe(
                    self.broadcast_event(
                        event_type=event_type,
                        title=title,
                        message=message,
                        severity=severity,
                        image_path=image_path,
                        metadata=metadata,
                        cooldown_sec=cooldown_sec,
                    ),
                    loop
                )
                return
        except Exception:
            pass

        # If no running event loop in thread, launch a fire-and-forget worker
        def _runner():
            asyncio.run(
                self.broadcast_event(
                    event_type=event_type,
                    title=title,
                    message=message,
                    severity=severity,
                    image_path=image_path,
                    metadata=metadata,
                    cooldown_sec=cooldown_sec,
                )
            )
        threading.Thread(target=_runner, daemon=True).start()

    def get_history(self, limit: int = 50) -> list[dict[str, Any]]:
        with _lock:
            # Return history without large base64 images to keep response fast
            out = []
            for item in self._history[:limit]:
                copy_item = dict(item)
                if copy_item.get("image_b64"):
                    copy_item["image_b64"] = "[IMAGE_DATA]"
                out.append(copy_item)
            return out

notification_manager = NotificationManager()
