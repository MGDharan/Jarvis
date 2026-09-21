"""
plugins/gesture_mouse.py — OpenCV Hand Gesture Mouse Controller for JARVIS.

Enables touchless mouse control using real-time computer vision:
- Steering: Point index finger or move hand to guide the cursor.
- Left Click: Peace / V-sign (2 fingers) or rapid tap.
- Right Click: 3 fingers up.
- Drag & Drop: Clench fist (0 fingers) to drag, open hand to release.
- Scroll: Move hand vertically while in 2-finger mode.
- Cyberpunk HUD: Real-time neon camera feed showing tracking, gestures, and coordinates.

Runs safely in a background daemon thread with zero external neural net dependencies.
"""
from __future__ import annotations

import json
import math
import os
import sys
import threading
import time
from pathlib import Path
from typing import Optional, Tuple

try:
    import cv2
    import numpy as np
    _CV2_AVAILABLE = True
except ImportError:
    _CV2_AVAILABLE = False

try:
    import pyautogui
    pyautogui.FAILSAFE = False
    pyautogui.PAUSE = 0.001
    _PYAUTOGUI_AVAILABLE = True
except ImportError:
    _PYAUTOGUI_AVAILABLE = False


def _base_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    return Path(__file__).resolve().parent.parent


BASE_DIR = _base_dir()
CONFIG_PATH = BASE_DIR / "config" / "api_keys.json"

PLUGIN = {
    "name": "gesture_mouse",
    "description": (
        "Controls the mouse cursor and desktop actions using OpenCV webcam hand gesture tracking. "
        "Supports cursor movement, left click (peace sign), right click (3 fingers), "
        "drag-and-drop (fist), scrolling, and a live cyberpunk HUD overlay. "
        "Trigger phrases: 'start gesture mouse', 'start gesture mouse with HUD', 'enable hand tracking', "
        "'control mouse with hand', 'open air mouse', 'stop gesture mouse', 'disable hand tracking', "
        "'toggle gesture hud', 'gesture mouse status', 'set gesture mouse speed'. "
        "Use this tool whenever the user asks for gesture mouse, hand tracking mouse, or air mouse. "
        "Do NOT call hud_overlay when the user asks for gesture mouse."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "action": {
                "type": "STRING",
                "description": (
                    "Command action: 'start' | 'stop' | 'status' | 'toggle_hud' | "
                    "'set_speed' | 'set_mode'"
                ),
            },
            "show_hud": {
                "type": "BOOLEAN",
                "description": "Show visual camera HUD overlay on screen (default: false).",
            },
            "speed": {
                "type": "NUMBER",
                "description": "Cursor speed multiplier (e.g. 1.0, 1.5, 2.0).",
            },
            "smoothing": {
                "type": "NUMBER",
                "description": "Motion smoothing factor from 0.1 (very smooth) to 0.9 (raw).",
            },
            "mode": {
                "type": "STRING",
                "description": "Tracking mode: 'precision' (1-finger tip) | 'hover' (hand centroid) | 'scroll'.",
            },
            "camera_index": {
                "type": "INTEGER",
                "description": "Webcam device index (default: 0).",
            },
        },
        "required": ["action"],
    },
}


class GestureMouseController:
    """Thread-safe singleton controller for OpenCV hand gesture mouse navigation."""

    _instance: Optional[GestureMouseController] = None

    @classmethod
    def get_instance(cls) -> GestureMouseController:
        if cls._instance is None:
            cls._instance = GestureMouseController()
        return cls._instance

    def __init__(self):
        self._lock = threading.Lock()
        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None

        # Configuration
        self.camera_index = 0
        self.speed = 1.25
        self.smoothing = 0.40  # EMA alpha
        self.mode = "precision"  # "precision" | "hover" | "scroll"
        self.show_hud = False
        self.active_margin = 0.15  # 15% inner boundary margin for easy edge reaches
        self.deadzone = 3.0  # pixels to ignore small hand tremors

        # Runtime states
        self.is_running = False
        self.is_dragging = False
        self.fps = 0.0
        self.current_gesture = "IDLE"
        self.last_click_time = 0.0
        self.click_cooldown = 0.45  # seconds
        self.last_scroll_time = 0.0
        self.prev_screen_x = -1.0
        self.prev_screen_y = -1.0
        self.stats = {
            "clicks": 0,
            "right_clicks": 0,
            "drags": 0,
            "scrolls": 0,
            "frames_processed": 0,
        }
        self.player = None

        self._load_config()

    def _load_config(self):
        try:
            if CONFIG_PATH.exists():
                cfg = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
                self.camera_index = int(cfg.get("camera_index", 0))
        except Exception:
            self.camera_index = 0

    def start(
        self,
        show_hud: bool = False,
        speed: Optional[float] = None,
        smoothing: Optional[float] = None,
        mode: Optional[str] = None,
        camera_index: Optional[int] = None,
        player=None,
    ) -> str:
        with self._lock:
            if not _CV2_AVAILABLE or not _PYAUTOGUI_AVAILABLE:
                return "Sir, OpenCV and PyAutoGUI are required for gesture mouse tracking."

            if self.is_running:
                # Update runtime parameters if already running
                if show_hud is not None:
                    self.show_hud = show_hud
                if speed is not None and speed > 0:
                    self.speed = float(speed)
                if smoothing is not None and 0.05 <= smoothing <= 0.95:
                    self.smoothing = float(smoothing)
                if mode in ("precision", "hover", "scroll"):
                    self.mode = mode
                return (
                    f"Gesture mouse is already active. Updated settings: "
                    f"mode={self.mode}, speed={self.speed:.2f}, HUD={'on' if self.show_hud else 'off'}."
                )

            if speed is not None and speed > 0:
                self.speed = float(speed)
            if smoothing is not None and 0.05 <= smoothing <= 0.95:
                self.smoothing = float(smoothing)
            if mode in ("precision", "hover", "scroll"):
                self.mode = mode
            if camera_index is not None:
                self.camera_index = int(camera_index)
            self.show_hud = bool(show_hud)
            self.player = player

            self._stop_event.clear()
            self.is_running = True
            self.prev_screen_x = -1.0
            self.prev_screen_y = -1.0
            self.is_dragging = False

            self._thread = threading.Thread(
                target=self._tracking_loop,
                daemon=True,
                name="GestureMouseTrackingThread",
            )
            self._thread.start()

            hud_str = "with HUD visualizer enabled" if self.show_hud else "in background mode"
            return (
                f"Air gesture mouse tracking engaged {hud_str}. "
                f"Hold your hand in front of the camera to navigate, peace sign to click, or fist to drag."
            )

    def stop(self) -> str:
        with self._lock:
            if not self.is_running:
                return "Gesture mouse tracking is not currently active."

            self._stop_event.set()
            self.is_running = False

            # Release drag if currently dragging
            if self.is_dragging and _PYAUTOGUI_AVAILABLE:
                try:
                    pyautogui.mouseUp()
                except Exception:
                    pass
                self.is_dragging = False

            if self._thread and self._thread.is_alive():
                self._thread.join(timeout=2.0)
                self._thread = None

            try:
                if _CV2_AVAILABLE:
                    cv2.destroyAllWindows()
            except Exception:
                pass

            return (
                f"Gesture mouse tracking deactivated. Processed {self.stats['frames_processed']} frames, "
                f"{self.stats['clicks']} left clicks, {self.stats['right_clicks']} right clicks."
            )

    def toggle_hud(self) -> str:
        with self._lock:
            self.show_hud = not self.show_hud
            if not self.show_hud and _CV2_AVAILABLE:
                try:
                    cv2.destroyAllWindows()
                except Exception:
                    pass
            return f"Gesture mouse HUD is now {'enabled' if self.show_hud else 'disabled'}."

    def set_speed(self, speed: float) -> str:
        with self._lock:
            if speed <= 0.1 or speed > 5.0:
                return "Speed must be between 0.2 and 5.0."
            self.speed = float(speed)
            return f"Gesture mouse speed calibrated to {self.speed:.2f}x."

    def set_mode(self, mode: str) -> str:
        with self._lock:
            m = mode.lower().strip()
            if m not in ("precision", "hover", "scroll"):
                return "Mode must be 'precision', 'hover', or 'scroll'."
            self.mode = m
            return f"Gesture mouse mode switched to '{self.mode}'."

    def get_status(self) -> str:
        with self._lock:
            if not self.is_running:
                return "Gesture mouse is currently OFFLINE."
            return (
                f"Gesture mouse is ACTIVE ({self.fps:.1f} FPS, mode: {self.mode}). "
                f"Current gesture: {self.current_gesture}. "
                f"HUD: {'ON' if self.show_hud else 'OFF'}. "
                f"Stats: {self.stats['clicks']} clicks, {self.stats['right_clicks']} right clicks, "
                f"{self.stats['drags']} drags."
            )

    # ── Computer Vision Core ──────────────────────────────────────────────────

    def _tracking_loop(self):
        """Webcam capture and gesture evaluation loop."""
        cap = None
        api_pref = cv2.CAP_DSHOW if sys.platform == "win32" else cv2.CAP_ANY

        try:
            cap = cv2.VideoCapture(self.camera_index, api_pref)
            if not cap.isOpened():
                cap = cv2.VideoCapture(self.camera_index)

            if not cap.isOpened():
                if self.player:
                    try:
                        self.player.write_log(f"ERR: [GestureMouse] Could not open camera {self.camera_index}.")
                    except Exception:
                        pass
                self.is_running = False
                return

            cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
            cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)

            screen_w, screen_h = pyautogui.size()
            kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))

            # Skin detection bounds in YCrCb color space (illumination robust)
            lower_ycrcb = np.array([0, 133, 77], dtype=np.uint8)
            upper_ycrcb = np.array([255, 175, 127], dtype=np.uint8)

            prev_time = time.time()
            frame_count = 0
            prev_scroll_y = None

            while not self._stop_event.is_set():
                ret, frame = cap.read()
                if not ret or frame is None:
                    time.sleep(0.01)
                    continue

                frame_count += 1
                self.stats["frames_processed"] += 1
                now = time.time()
                dt = now - prev_time
                if dt >= 1.0:
                    self.fps = frame_count / dt
                    frame_count = 0
                    prev_time = now

                # Mirror frame horizontally so hand moves naturally
                frame = cv2.flip(frame, 1)
                fh, fw = frame.shape[:2]

                # Active boundary box (margin around camera feed)
                x_min = int(fw * self.active_margin)
                x_max = int(fw * (1.0 - self.active_margin))
                y_min = int(fh * self.active_margin)
                y_max = int(fh * (1.0 - self.active_margin))

                # Color conversion & skin thresholding
                ycrcb = cv2.cvtColor(frame, cv2.COLOR_BGR2YCrCb)
                mask = cv2.inRange(ycrcb, lower_ycrcb, upper_ycrcb)

                # Morphological noise removal
                mask = cv2.erode(mask, kernel, iterations=1)
                mask = cv2.dilate(mask, kernel, iterations=2)
                mask = cv2.GaussianBlur(mask, (5, 5), 0)

                contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

                detected_hand = False
                hand_contour = None
                fingertip_pt = None
                centroid_pt = None
                finger_count = 0
                gesture_label = "SEARCHING"

                if contours:
                    # Filter for candidate hand contour
                    valid_contours = [c for c in contours if cv2.contourArea(c) > 5500]
                    if valid_contours:
                        hand_contour = max(valid_contours, key=cv2.contourArea)
                        detected_hand = True

                if detected_hand and hand_contour is not None:
                    # Centroid from moments
                    m = cv2.moments(hand_contour)
                    if m["m00"] > 0:
                        cx = int(m["m10"] / m["m00"])
                        cy = int(m["m01"] / m["m00"])
                        centroid_pt = (cx, cy)

                    # Topmost point (the pointing index fingertip)
                    topmost = tuple(hand_contour[hand_contour[:, :, 1].argmin()][0])
                    fingertip_pt = topmost

                    # Convex Hull & Defect Analysis for Finger Counting
                    hull_indices = cv2.convexHull(hand_contour, returnPoints=False)
                    valid_defects = []

                    if hull_indices is not None and len(hull_indices) > 3:
                        try:
                            defects = cv2.convexityDefects(hand_contour, hull_indices)
                            if defects is not None:
                                for i in range(defects.shape[0]):
                                    s_idx, e_idx, f_idx, d_val = defects[i, 0]
                                    start = tuple(hand_contour[s_idx][0])
                                    end = tuple(hand_contour[e_idx][0])
                                    far = tuple(hand_contour[f_idx][0])

                                    # Triangle side lengths
                                    a = math.hypot(end[0] - start[0], end[1] - start[1])
                                    b = math.hypot(far[0] - start[0], far[1] - start[1])
                                    c = math.hypot(end[0] - far[0], end[1] - far[1])

                                    # Cosine theorem for angle at the defect valley
                                    if b * c > 0:
                                        cos_angle = (b**2 + c**2 - a**2) / (2 * b * c)
                                        cos_angle = max(-1.0, min(1.0, cos_angle))
                                        angle = math.degrees(math.acos(cos_angle))

                                        # Valley between fingers typically < 85 deg, depth > 12000
                                        if angle <= 85.0 and d_val > 12000:
                                            valid_defects.append((start, end, far))
                        except Exception:
                            pass

                    defect_count = len(valid_defects)

                    # Distinguish Fist vs 1 Finger when defect_count == 0
                    if defect_count == 0:
                        bx, by, bw, bh = cv2.boundingRect(hand_contour)
                        aspect_ratio = float(bw) / float(bh) if bh > 0 else 1.0
                        hand_extent = float(cv2.contourArea(hand_contour)) / (bw * bh) if (bw * bh) > 0 else 0.5
                        tip_dist = math.hypot(topmost[0] - cx, topmost[1] - cy) if centroid_pt else 0

                        # A pointed finger has high vertical elongation and tip is far from centroid
                        if tip_dist > (bh * 0.42) and aspect_ratio < 0.95 and hand_extent < 0.65:
                            finger_count = 1
                        else:
                            finger_count = 0  # Fist
                    else:
                        finger_count = min(5, defect_count + 1)

                    # Map gesture
                    if finger_count == 0:
                        gesture_label = "FIST (DRAG)"
                    elif finger_count == 1:
                        gesture_label = "1 FINGER (STEER)"
                    elif finger_count == 2:
                        gesture_label = "PEACE (CLICK/SCROLL)"
                    elif finger_count == 3:
                        gesture_label = "3 FINGERS (RIGHT CLICK)"
                    elif finger_count >= 4:
                        gesture_label = "PALM (HOVER)"

                    self.current_gesture = gesture_label

                    # Target tracking point based on mode
                    target_pt = fingertip_pt if (self.mode == "precision" and finger_count == 1) else (centroid_pt or fingertip_pt)

                    # ── Cursor Motion & Gestures Dispatch ──────────────────────
                    if target_pt:
                        tx, ty = target_pt

                        # Normalize within active margin box
                        norm_x = (tx - x_min) / float(x_max - x_min)
                        norm_y = (ty - y_min) / float(y_max - y_min)
                        norm_x = max(0.0, min(1.0, norm_x))
                        norm_y = max(0.0, min(1.0, norm_y))

                        raw_screen_x = norm_x * screen_w
                        raw_screen_y = norm_y * screen_h

                        # EMA Smoothing
                        if self.prev_screen_x < 0 or self.prev_screen_y < 0:
                            smooth_x = raw_screen_x
                            smooth_y = raw_screen_y
                        else:
                            alpha = self.smoothing
                            smooth_x = alpha * raw_screen_x + (1.0 - alpha) * self.prev_screen_x
                            smooth_y = alpha * raw_screen_y + (1.0 - alpha) * self.prev_screen_y

                        # Deadzone filter against hand micro-tremors
                        dist_moved = math.hypot(smooth_x - self.prev_screen_x, smooth_y - self.prev_screen_y)
                        if dist_moved >= self.deadzone:
                            clamped_x = int(max(0, min(screen_w - 1, smooth_x)))
                            clamped_y = int(max(0, min(screen_h - 1, smooth_y)))

                            try:
                                pyautogui.moveTo(clamped_x, clamped_y)
                                self.prev_screen_x = smooth_x
                                self.prev_screen_y = smooth_y
                            except Exception:
                                pass

                    # ── Gesture Actions ────────────────────────────────────────
                    # 1. Fist: Drag and drop
                    if finger_count == 0:
                        if not self.is_dragging:
                            try:
                                pyautogui.mouseDown()
                                self.is_dragging = True
                                self.stats["drags"] += 1
                            except Exception:
                                pass
                    else:
                        if self.is_dragging:
                            try:
                                pyautogui.mouseUp()
                                self.is_dragging = False
                            except Exception:
                                pass

                    # 2. Peace Sign (2 fingers): Left Click or Scroll
                    if finger_count == 2:
                        if self.mode == "scroll":
                            curr_y = target_pt[1] if target_pt else cy
                            if prev_scroll_y is not None:
                                delta_y = prev_scroll_y - curr_y
                                if abs(delta_y) > 15:
                                    scroll_clicks = int(delta_y * 3.5)
                                    try:
                                        pyautogui.scroll(scroll_clicks)
                                        self.stats["scrolls"] += 1
                                    except Exception:
                                        pass
                            prev_scroll_y = curr_y
                        else:
                            prev_scroll_y = None
                            if now - self.last_click_time >= self.click_cooldown:
                                try:
                                    pyautogui.click()
                                    self.last_click_time = now
                                    self.stats["clicks"] += 1
                                except Exception:
                                    pass
                    else:
                        prev_scroll_y = None

                    # 3. 3 Fingers: Right Click
                    if finger_count == 3:
                        if now - self.last_click_time >= self.click_cooldown:
                            try:
                                pyautogui.rightClick()
                                self.last_click_time = now
                                self.stats["right_clicks"] += 1
                            except Exception:
                                pass

                else:
                    self.current_gesture = "SEARCHING"
                    if self.is_dragging:
                        try:
                            pyautogui.mouseUp()
                            self.is_dragging = False
                        except Exception:
                            pass

                # ── Visual Cyberpunk HUD Overlay ──────────────────────────────
                if self.show_hud:
                    hud_frame = frame.copy()

                    # Neon control bounding box with corner brackets
                    cv2.rectangle(hud_frame, (x_min, y_min), (x_max, y_max), (60, 60, 60), 1)
                    bracket_len = 22
                    color_neon_cyan = (255, 255, 0)
                    color_neon_green = (0, 255, 128)
                    color_neon_pink = (180, 0, 255)

                    # Corner brackets
                    cv2.line(hud_frame, (x_min, y_min), (x_min + bracket_len, y_min), color_neon_cyan, 2)
                    cv2.line(hud_frame, (x_min, y_min), (x_min, y_min + bracket_len), color_neon_cyan, 2)
                    cv2.line(hud_frame, (x_max, y_min), (x_max - bracket_len, y_min), color_neon_cyan, 2)
                    cv2.line(hud_frame, (x_max, y_min), (x_max, y_min + bracket_len), color_neon_cyan, 2)
                    cv2.line(hud_frame, (x_min, y_max), (x_min + bracket_len, y_max), color_neon_cyan, 2)
                    cv2.line(hud_frame, (x_min, y_max), (x_min, y_max - bracket_len), color_neon_cyan, 2)
                    cv2.line(hud_frame, (x_max, y_max), (x_max - bracket_len, y_max), color_neon_cyan, 2)
                    cv2.line(hud_frame, (x_max, y_max), (x_max, y_max - bracket_len), color_neon_cyan, 2)

                    # Hand contour & tracking points
                    if detected_hand and hand_contour is not None:
                        cv2.drawContours(hud_frame, [hand_contour], -1, color_neon_cyan, 2)
                        hull = cv2.convexHull(hand_contour)
                        cv2.drawContours(hud_frame, [hull], -1, color_neon_green, 1)

                        if centroid_pt:
                            cv2.circle(hud_frame, centroid_pt, 7, color_neon_pink, -1)
                        if fingertip_pt:
                            cv2.circle(hud_frame, fingertip_pt, 9, (0, 0, 255), -1)
                            cv2.circle(hud_frame, fingertip_pt, 13, (0, 255, 255), 2)

                    # Cyberpunk Top Banner
                    cv2.rectangle(hud_frame, (0, 0), (fw, 44), (20, 20, 24), -1)
                    cv2.putText(
                        hud_frame,
                        f"JARVIS AIR MOUSE | {self.current_gesture}",
                        (14, 28),
                        cv2.FONT_HERSHEY_SIMPLEX,
                        0.62,
                        (0, 255, 255),
                        2,
                    )
                    cv2.putText(
                        hud_frame,
                        f"{self.fps:.0f} FPS",
                        (fw - 95, 28),
                        cv2.FONT_HERSHEY_SIMPLEX,
                        0.55,
                        (0, 255, 128),
                        2,
                    )

                    # Bottom Status Bar
                    cv2.rectangle(hud_frame, (0, fh - 30), (fw, fh), (20, 20, 24), -1)
                    mode_info = f"MODE: {self.mode.upper()}  SPEED: {self.speed:.1f}x  [Q] Close HUD"
                    cv2.putText(
                        hud_frame,
                        mode_info,
                        (14, fh - 10),
                        cv2.FONT_HERSHEY_SIMPLEX,
                        0.45,
                        (180, 180, 180),
                        1,
                    )

                    cv2.imshow("JARVIS Air Gesture Mouse HUD", hud_frame)
                    key = cv2.waitKey(1) & 0xFF
                    if key in (ord("q"), ord("Q"), 27):  # 'q' or ESC closes HUD
                        self.show_hud = False
                        cv2.destroyAllWindows()
                    elif key in (ord("m"), ord("M")):
                        modes = ["precision", "hover", "scroll"]
                        cur_idx = modes.index(self.mode) if self.mode in modes else 0
                        self.mode = modes[(cur_idx + 1) % len(modes)]
                else:
                    time.sleep(0.005)

        except Exception as e:
            if self.player:
                try:
                    self.player.write_log(f"ERR: [GestureMouse] Exception in tracking loop: {e}")
                except Exception:
                    pass
        finally:
            if cap:
                try:
                    cap.release()
                except Exception:
                    pass
            try:
                if _CV2_AVAILABLE:
                    cv2.destroyAllWindows()
            except Exception:
                pass
            self.is_running = False
            self.is_dragging = False


def run(parameters: dict, player=None, session_memory=None) -> str:
    """Entry point for JARVIS plugin invocation."""
    action = str(parameters.get("action", "status")).lower().strip()
    controller = GestureMouseController.get_instance()

    try:
        if action in ("start", "enable", "on", "activate"):
            show_hud = bool(parameters.get("show_hud", False))
            speed = parameters.get("speed")
            smoothing = parameters.get("smoothing")
            mode = parameters.get("mode")
            cam_idx = parameters.get("camera_index")
            res = controller.start(
                show_hud=show_hud,
                speed=speed,
                smoothing=smoothing,
                mode=mode,
                camera_index=cam_idx,
                player=player,
            )
        elif action in ("stop", "disable", "off", "deactivate"):
            res = controller.stop()
        elif action in ("toggle_hud", "hud", "preview"):
            res = controller.toggle_hud()
        elif action in ("status", "info", "check"):
            res = controller.get_status()
        elif action in ("set_speed", "speed"):
            spd = float(parameters.get("speed", 1.25))
            res = controller.set_speed(spd)
        elif action in ("set_mode", "mode"):
            md = str(parameters.get("mode", "precision"))
            res = controller.set_mode(md)
        else:
            res = f"Unrecognized gesture mouse action: '{action}'. Available: start, stop, status, toggle_hud, set_speed, set_mode."

    except Exception as e:
        res = f"Sir, gesture mouse encountered an issue: {e}"

    if player:
        try:
            player.write_log(f"JARVIS: {res}")
        except Exception:
            pass

    return res
