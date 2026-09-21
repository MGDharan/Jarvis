"""
plugins/sentry_mode.py — Autonomous Room & Desk Sentry Plugin for JARVIS.

Provides autonomous surveillance using the webcam. When armed, JARVIS monitors
the room for motion or human entry, captures timestamped security snapshots,
records incidents, and speaks security warnings in real time.
"""
from __future__ import annotations

import json
import os
import sys
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Optional

try:
    import cv2
    _CV2_AVAILABLE = True
except ImportError:
    _CV2_AVAILABLE = False


def _base_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    return Path(__file__).resolve().parent.parent


BASE_DIR = _base_dir()
SNAPSHOTS_DIR = BASE_DIR / "snapshots" / "sentry"
CONFIG_PATH = BASE_DIR / "config" / "api_keys.json"

PLUGIN = {
    "name": "sentry_mode",
    "description": (
        "Activates or manages autonomous room and desk surveillance using the webcam. "
        "Features motion detection, intruder alerts, snapshot logging, and disarming. "
        "Use this whenever the user says 'enter sentry mode', 'arm sentry mode', 'watch my room', "
        "'watch my desk', 'disarm sentry mode', 'disable sentry', 'security status', or 'check sentry incidents'."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "action": {
                "type": "STRING",
                "description": "'arm' | 'disarm' | 'status' | 'clear_incidents'",
            },
            "countdown": {
                "type": "INTEGER",
                "description": "Seconds to wait before arming to allow user to leave (default: 5).",
            },
            "sensitivity": {
                "type": "STRING",
                "description": "Motion sensitivity: 'low' | 'medium' | 'high' (default: 'medium').",
            },
        },
        "required": ["action"],
    },
}


class SentryController:
    _instance: Optional[SentryController] = None

    @classmethod
    def get_instance(cls) -> SentryController:
        if cls._instance is None:
            cls._instance = SentryController()
        return cls._instance

    def __init__(self):
        self.state = "DISARMED"  # DISARMED | ARMING | ARMED | TRIGGERED
        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._lock = threading.Lock()
        self.incidents: list[dict] = []
        self.last_incident_time: float = 0.0
        self.sensitivity = "medium"
        self.camera_index = 0
        self.player = None

        # Load camera index from config if available
        self._load_config()

    def _load_config(self):
        try:
            if CONFIG_PATH.exists():
                cfg = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
                self.camera_index = int(cfg.get("camera_index", 0))
        except Exception:
            self.camera_index = 0

    def arm(self, countdown: int = 5, sensitivity: str = "medium", player=None) -> str:
        with self._lock:
            if self.state in ("ARMED", "ARMING"):
                return f"Sentry mode is already {self.state.lower()}."

            if not _CV2_AVAILABLE:
                return "Sentry mode cannot start: OpenCV (cv2) is not installed."

            self.sensitivity = sensitivity.lower() if sensitivity else "medium"
            self.player = player
            self.state = "ARMING"
            self._stop_event.clear()

            SNAPSHOTS_DIR.mkdir(parents=True, exist_ok=True)

            self._thread = threading.Thread(
                target=self._surveillance_loop,
                args=(countdown,),
                daemon=True,
                name="SentrySurveillanceThread",
            )
            self._thread.start()

            return (
                f"Sentry mode initiated. You have {countdown} seconds to vacate the area. "
                f"Surveillance will engage automatically on {self.sensitivity} sensitivity."
            )

    def disarm(self) -> str:
        with self._lock:
            if self.state == "DISARMED":
                return "Sentry mode is not currently active."

            self._stop_event.set()
            self.state = "DISARMED"

            if self._thread and self._thread.is_alive():
                self._thread.join(timeout=2.0)
                self._thread = None

            incident_count = len(self.incidents)
            return f"Sentry mode disarmed. Stand down confirmed. {incident_count} incidents recorded during this session."

    def get_status(self) -> str:
        with self._lock:
            count = len(self.incidents)
            if self.state == "DISARMED":
                return f"Sentry mode is offline (disarmed). Total incidents logged: {count}."
            elif self.state == "ARMING":
                return "Sentry mode is currently counting down to arm."
            else:
                last_txt = ""
                if self.incidents:
                    last_time = self.incidents[-1]["timestamp"]
                    last_txt = f" Most recent alert logged at {last_time}."
                return f"Sentry mode is ACTIVE and monitoring ({self.sensitivity} sensitivity). {count} incidents detected.{last_txt}"

    def clear_incidents(self) -> str:
        with self._lock:
            count = len(self.incidents)
            self.incidents.clear()
            return f"Cleared {count} recorded sentry incident logs."

    def _surveillance_loop(self, countdown: int):
        # 1. Countdown phase
        for _ in range(max(1, countdown)):
            if self._stop_event.is_set():
                self.state = "DISARMED"
                return
            time.sleep(1.0)

        with self._lock:
            if self._stop_event.is_set():
                self.state = "DISARMED"
                return
            self.state = "ARMED"

        if self.player:
            try:
                self.player.write_log("SYS: [Sentry] Armed and scanning.")
            except Exception:
                pass

        # Sensitivity thresholds (pixel area of detected motion)
        thresholds = {
            "high": 1000,
            "medium": 2500,
            "low": 5000,
        }
        min_contour_area = thresholds.get(self.sensitivity, 2500)

        # Open camera (CAP_DSHOW for fastest Windows startup)
        cap = None
        try:
            if sys.platform == "win32":
                cap = cv2.VideoCapture(self.camera_index, cv2.CAP_DSHOW)
            else:
                cap = cv2.VideoCapture(self.camera_index)

            if not cap.isOpened():
                if sys.platform == "win32":
                    cap = cv2.VideoCapture(self.camera_index)

            if not cap.isOpened():
                self.state = "DISARMED"
                if self.player:
                    try:
                        self.player.write_log("SYS: [Sentry] Error: Unable to access camera device.")
                    except Exception:
                        pass
                return

            # Warmup frames
            for _ in range(5):
                cap.read()
                time.sleep(0.1)

            prev_gray = None
            alert_cooldown = 10.0  # minimum seconds between audible voice alerts

            while not self._stop_event.is_set():
                ret, frame = cap.read()
                if not ret or frame is None:
                    time.sleep(0.1)
                    continue

                # Prepare frame for motion analysis
                gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
                gray = cv2.GaussianBlur(gray, (21, 21), 0)

                if prev_gray is None:
                    prev_gray = gray
                    continue

                # Frame differencing
                frame_diff = cv2.absdiff(prev_gray, gray)
                thresh = cv2.threshold(frame_diff, 25, 255, cv2.THRESH_BINARY)[1]
                thresh = cv2.dilate(thresh, None, iterations=2)

                contours, _ = cv2.findContours(
                    thresh.copy(), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
                )

                motion_detected = False
                max_area = 0

                for c in contours:
                    area = cv2.contourArea(c)
                    if area > min_contour_area:
                        motion_detected = True
                        if area > max_area:
                            max_area = area

                prev_gray = gray

                if motion_detected:
                    now = time.time()
                    if (now - self.last_incident_time) > alert_cooldown:
                        self.last_incident_time = now
                        self.state = "TRIGGERED"

                        timestamp_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                        file_ts = datetime.now().strftime("%Y%m%d_%H%M%S")
                        snapshot_path = SNAPSHOTS_DIR / f"sentry_{file_ts}.jpg"

                        # Draw alert overlay on captured snapshot
                        alert_frame = frame.copy()
                        cv2.putText(
                            alert_frame,
                            f"JARVIS SENTRY ALERT: {timestamp_str}",
                            (20, 40),
                            cv2.FONT_HERSHEY_SIMPLEX,
                            0.7,
                            (0, 0, 255),
                            2,
                        )
                        cv2.imwrite(str(snapshot_path), alert_frame)

                        incident_record = {
                            "timestamp": timestamp_str,
                            "file": str(snapshot_path),
                            "area": int(max_area),
                        }
                        self.incidents.append(incident_record)

                        # Dispatch snapshot alert to Telegram / Discord bridge if available
                        try:
                            from plugins.telegram_bridge import TelegramBridge
                            bridge = TelegramBridge.get_instance()
                            if bridge.token and (bridge.chat_id or bridge.discord_webhook):
                                bridge.notify_sentry_alert(str(snapshot_path), incident_num=len(self.incidents))
                        except Exception:
                            pass

                        # Dispatch push notification to paired Android phone
                        try:
                            from remote.notifications import notification_manager
                            notification_manager.dispatch_sync(
                                event_type="motion_detected",
                                title="🚨 Motion Detected in Lab",
                                message=f"Movement detected at {timestamp_str}. Snapshot captured.",
                                severity="critical",
                                image_path=snapshot_path,
                                cooldown_sec=15.0
                            )
                        except Exception:
                            pass

                        # Announce alert via JARVIS
                        alert_msg = "Security alert: Unauthorized motion detected in the workspace. Snapshot recorded."
                        if self.player:
                            try:
                                self.player.write_log(f"ALERT: [Sentry] Motion detected! Snapshot saved: {snapshot_path.name}")
                                if hasattr(self.player, "request_say") and callable(self.player.request_say):
                                    self.player.request_say(alert_msg)
                            except Exception:
                                pass

                time.sleep(0.15)  # ~6.6 FPS inspection loop keeps CPU usage near 1%

        except Exception as e:
            if self.player:
                try:
                    self.player.write_log(f"SYS: [Sentry] Surveillance error: {e}")
                except Exception:
                    pass
        finally:
            if cap:
                cap.release()
            self.state = "DISARMED"


def run(parameters: dict, player=None, session_memory=None) -> str:
    action = parameters.get("action", "").lower().strip()
    countdown = parameters.get("countdown", 5)
    sensitivity = parameters.get("sensitivity", "medium")

    try:
        countdown = int(countdown)
    except (ValueError, TypeError):
        countdown = 5

    controller = SentryController.get_instance()

    if action in ("arm", "activate", "start", "enable"):
        result = controller.arm(countdown=countdown, sensitivity=sensitivity, player=player)
    elif action in ("disarm", "deactivate", "stop", "disable", "stand_down"):
        result = controller.disarm()
    elif action in ("status", "check"):
        result = controller.get_status()
    elif action in ("clear", "clear_incidents", "reset"):
        result = controller.clear_incidents()
    else:
        result = f"Unknown sentry mode action '{action}'. Valid actions are arm, disarm, status, and clear_incidents."

    if player:
        try:
            player.write_log(f"JARVIS: {result}")
        except Exception:
            pass

    return result
