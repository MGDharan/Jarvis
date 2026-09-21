"""
HUD Overlay Plugin — Iron Man-style always-on transparent overlay.

Shows on top of ALL windows (frameless, click-through, always-on-top):
  • Live clock + date
  • CPU / RAM / GPU / NET metrics (updates every 2 s)
  • Current JARVIS state (LISTENING / SPEAKING / THINKING …)
  • Active app name
  • Last JARVIS message (scrolling ticker)
  • Corner arc decoration + scan-line animation

Say "enable HUD", "show overlay", "turn on heads up display" → activates.
Say "disable HUD", "hide overlay", "close overlay"           → deactivates.

Requires: PyQt6 (already in requirements)
"""

from __future__ import annotations

import math
import platform
import sys
import threading
import time
from pathlib import Path

# ── Qt imports ────────────────────────────────────────────────────────────────
try:
    from PyQt6.QtCore import (
        Qt, QTimer, QPointF, QRectF, pyqtSignal, QObject,
    )
    from PyQt6.QtGui import (
        QColor, QPainter, QPen, QBrush, QFont, QLinearGradient,
        QConicalGradient, QFontDatabase,
    )
    from PyQt6.QtWidgets import QApplication, QWidget
    _QT_OK = True
except ImportError:
    _QT_OK = False

try:
    import psutil
    _PSUTIL = True
except ImportError:
    _PSUTIL = False

# ── PLUGIN manifest ───────────────────────────────────────────────────────────
PLUGIN = {
    "name": "hud_overlay",
    "description": (
        "Toggles an Iron Man / JARVIS heads-up display (HUD) overlay — "
        "a transparent always-on-top window showing live system stats, "
        "clock, JARVIS state, and last spoken text. "
        "Trigger phrases: 'enable HUD', 'show overlay', 'turn on HUD', "
        "'heads up display on', 'disable HUD', 'hide overlay', 'close HUD', "
        "'turn off heads up display'."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "action": {
                "type": "STRING",
                "description": "'on' to show the HUD, 'off' to hide it.",
            },
            "position": {
                "type": "STRING",
                "description": (
                    "Corner to anchor: 'top-right' (default), 'top-left', "
                    "'bottom-right', 'bottom-left', or 'center'."
                ),
            },
        },
        "required": ["action"],
    },
}

# ── Shared state (set by JARVIS main loop) ────────────────────────────────────
_shared: dict = {
    "state":        "INITIALISING",
    "last_message": "",
    "active_app":   "",
}

def update_hud_state(state: str) -> None:
    """Called by the plugin_say / set_state bridge to keep HUD in sync."""
    _shared["state"] = state

def update_hud_message(msg: str) -> None:
    """Called when JARVIS speaks — updates the ticker line."""
    if msg:
        _shared["last_message"] = msg[:120]

def update_hud_app(app: str) -> None:
    """Called by app_tracker to show the active foreground app."""
    _shared["active_app"] = app


# ─────────────────────────────────────────────────────────────────────────────
# HUD Widget
# ─────────────────────────────────────────────────────────────────────────────

_HUD_W = 320
_HUD_H = 420

_C = {
    "bg":      QColor(0, 8, 18, 195),     # near-black, slightly transparent
    "pri":     QColor(0, 212, 255, 220),  # cyan
    "pri_dim": QColor(0, 100, 130, 160),
    "acc":     QColor(255, 107, 0, 200),  # orange accent
    "acc2":    QColor(255, 204, 0, 200),  # yellow
    "green":   QColor(0, 255, 136, 220),
    "red":     QColor(255, 51, 85, 220),
    "text":    QColor(143, 252, 255, 220),
    "dim":     QColor(58, 138, 154, 180),
    "border":  QColor(13, 51, 71, 200),
}


def _qc(key: str) -> QColor:
    return _C.get(key, _C["text"])


class _HUDWidget(QWidget):
    """Frameless, click-through, always-on-top transparent HUD window."""

    def __init__(self, position: str = "top-right"):
        super().__init__()
        self._position = position
        self._tick = 0
        self._scan = 0.0
        self._metrics = {"cpu": 0.0, "mem": 0.0, "gpu": -1.0, "net": 0.0}
        self._metric_thread_running = True
        self._ticker_offset = 0
        self._ticker_tmr_count = 0

        # Window flags: frameless + always on top + transparent + click-through
        flags = (
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
            | Qt.WindowType.WindowTransparentForInput
        )
        self.setWindowFlags(flags)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.setFixedSize(_HUD_W, _HUD_H)

        self._position_window()

        # Metric update thread
        threading.Thread(target=self._metric_loop, daemon=True).start()

        # Animation timer ~30 fps
        self._tmr = QTimer(self)
        self._tmr.timeout.connect(self._step)
        self._tmr.start(33)

    def _position_window(self):
        try:
            screen = QApplication.primaryScreen().availableGeometry()
            pad = 12
            pos = self._position.lower()
            if pos == "top-left":
                x, y = pad, pad
            elif pos == "bottom-right":
                x, y = screen.width() - _HUD_W - pad, screen.height() - _HUD_H - pad
            elif pos == "bottom-left":
                x, y = pad, screen.height() - _HUD_H - pad
            elif pos == "center":
                x, y = (screen.width() - _HUD_W) // 2, (screen.height() - _HUD_H) // 2
            else:  # top-right default
                x, y = screen.width() - _HUD_W - pad, pad
            self.move(x, y)
        except Exception:
            self.move(50, 50)

    def _metric_loop(self):
        """Background thread: update metrics every 2 seconds."""
        _last_net = None
        _last_net_t = 0.0
        while self._metric_thread_running:
            try:
                if _PSUTIL:
                    cpu = psutil.cpu_percent(interval=None)
                    mem = psutil.virtual_memory().percent
                    nc  = psutil.net_io_counters()
                    now = time.time()
                    if _last_net is not None and now - _last_net_t > 0:
                        dt  = now - _last_net_t
                        net = ((nc.bytes_sent - _last_net.bytes_sent) +
                               (nc.bytes_recv - _last_net.bytes_recv)) / dt / (1024 * 1024)
                    else:
                        net = 0.0
                    _last_net   = nc
                    _last_net_t = now
                    self._metrics["cpu"] = cpu
                    self._metrics["mem"] = mem
                    self._metrics["net"] = net
            except Exception:
                pass
            time.sleep(2.0)

    def _step(self):
        self._tick += 1
        self._scan  = (self._scan + 1.8) % 360
        self._ticker_tmr_count += 1
        if self._ticker_tmr_count >= 4:  # scroll every 4 frames (~120ms)
            self._ticker_offset += 2
            self._ticker_tmr_count = 0
        self.update()

    def closeEvent(self, e):
        self._metric_thread_running = False
        self._tmr.stop()
        super().closeEvent(e)

    # ── Paint ─────────────────────────────────────────────────────────────────

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        W, H = self.width(), self.height()

        # ── Background ────────────────────────────────────────────────────────
        p.setBrush(QBrush(_C["bg"]))
        p.setPen(QPen(_C["pri_dim"], 1.5))
        p.drawRoundedRect(QRectF(1, 1, W - 2, H - 2), 8, 8)

        # ── Corner arc decorations ─────────────────────────────────────────
        _arc_r = 18
        _arc_pen = QPen(_C["pri"], 2)
        p.setPen(_arc_pen)
        for (bx, by, start) in [
            (0, 0, 90), (W, 0, 0), (0, H, 180), (W, H, 270)
        ]:
            p.drawArc(QRectF(bx - _arc_r, by - _arc_r, _arc_r * 2, _arc_r * 2),
                      start * 16, 90 * 16)

        # ── Top header: JARVIS + clock ────────────────────────────────────
        y = 18
        p.setFont(QFont("Courier New", 11, QFont.Weight.Bold))
        p.setPen(QPen(_C["pri"], 1))
        p.drawText(QRectF(12, y, W - 24, 20), Qt.AlignmentFlag.AlignLeft, "J.A.R.V.I.S")

        clock_str = time.strftime("%H:%M:%S")
        p.setFont(QFont("Courier New", 11, QFont.Weight.Bold))
        p.drawText(QRectF(12, y, W - 24, 20), Qt.AlignmentFlag.AlignRight, clock_str)

        y += 20
        date_str = time.strftime("%A  %d %b %Y")
        p.setFont(QFont("Courier New", 7))
        p.setPen(QPen(_C["dim"], 1))
        p.drawText(QRectF(12, y, W - 24, 14), Qt.AlignmentFlag.AlignLeft, date_str)

        # ── Divider line ──────────────────────────────────────────────────
        y += 18
        p.setPen(QPen(_C["pri_dim"], 1))
        p.drawLine(QPointF(12, y), QPointF(W - 12, y))
        y += 8

        # ── State pill ────────────────────────────────────────────────────
        state = _shared.get("state", "IDLE")
        _state_map = {
            "LISTENING":  (_C["green"],  "● LISTENING"),
            "SPEAKING":   (_C["acc"],    "▶ SPEAKING"),
            "THINKING":   (_C["acc2"],   "◈ THINKING"),
            "PROCESSING": (_C["acc2"],   "▷ PROCESSING"),
            "MUTED":      (_C["red"],    "⊘ MUTED"),
            "CONNECTING": (_C["pri"],    "⟳ CONNECTING"),
        }
        s_col, s_txt = _state_map.get(state.upper(), (_C["dim"], f"● {state}"))
        _pill_rect = QRectF(12, y, W - 24, 20)
        p.setBrush(QBrush(QColor(s_col.red(), s_col.green(), s_col.blue(), 35)))
        p.setPen(QPen(s_col, 1))
        p.drawRoundedRect(_pill_rect, 4, 4)
        p.setFont(QFont("Courier New", 8, QFont.Weight.Bold))
        p.drawText(_pill_rect, Qt.AlignmentFlag.AlignCenter, s_txt)
        y += 28

        # ── System metrics ────────────────────────────────────────────────
        p.setFont(QFont("Courier New", 7, QFont.Weight.Bold))
        p.setPen(QPen(_C["pri"], 1))
        p.drawText(QRectF(12, y, W - 24, 14), Qt.AlignmentFlag.AlignLeft, "SYS METRICS")
        y += 16

        _metrics_display = [
            ("CPU",  self._metrics["cpu"],  _C["pri"],  f"{self._metrics['cpu']:.0f}%"),
            ("MEM",  self._metrics["mem"],  _C["acc2"], f"{self._metrics['mem']:.0f}%"),
            ("GPU",  self._metrics.get("gpu", -1), _C["acc"],
             f"{self._metrics.get('gpu', -1):.0f}%" if self._metrics.get("gpu", -1) >= 0 else "N/A"),
            ("NET",  min(100, self._metrics["net"] * 10), _C["green"],
             f"{self._metrics['net']:.1f}MB/s"),
        ]

        bar_w   = W - 80
        bar_h   = 6
        bar_x   = 48
        lbl_w   = 34

        for label, pct, col, val_str in _metrics_display:
            # Label
            p.setFont(QFont("Courier New", 7))
            p.setPen(QPen(_C["dim"], 1))
            p.drawText(QRectF(12, y, lbl_w, 14), Qt.AlignmentFlag.AlignLeft, label)

            # Bar background
            bg_col = QColor(col.red(), col.green(), col.blue(), 30)
            p.setBrush(QBrush(bg_col))
            p.setPen(Qt.PenStyle.NoPen)
            p.drawRoundedRect(QRectF(bar_x, y + 3, bar_w, bar_h), 2, 2)

            # Bar fill
            fill = max(0, min(100, pct))
            if fill > 0:
                fill_col = QColor(col.red(), col.green(), col.blue(), 200)
                p.setBrush(QBrush(fill_col))
                p.drawRoundedRect(QRectF(bar_x, y + 3, bar_w * fill / 100, bar_h), 2, 2)

            # Value
            p.setFont(QFont("Courier New", 7, QFont.Weight.Bold))
            p.setPen(QPen(col, 1))
            p.drawText(QRectF(bar_x + bar_w + 4, y, 48, 14),
                       Qt.AlignmentFlag.AlignLeft, val_str)
            y += 18

        y += 4
        p.setPen(QPen(_C["pri_dim"], 1))
        p.drawLine(QPointF(12, y), QPointF(W - 12, y))
        y += 8

        # ── Active app ────────────────────────────────────────────────────
        app_name = _shared.get("active_app", "")
        if app_name:
            p.setFont(QFont("Courier New", 7, QFont.Weight.Bold))
            p.setPen(QPen(_C["dim"], 1))
            p.drawText(QRectF(12, y, 60, 14), Qt.AlignmentFlag.AlignLeft, "APP")
            p.setFont(QFont("Courier New", 7))
            p.setPen(QPen(_C["text"], 1))
            p.drawText(QRectF(74, y, W - 86, 14), Qt.AlignmentFlag.AlignLeft,
                       app_name[:32])
            y += 18

        # ── Scanning arc (decorative animation) ──────────────────────────
        sr    = 38
        s_cx  = W - sr - 14
        s_cy  = y + sr + 4
        s_rect = QRectF(s_cx - sr, s_cy - sr, sr * 2, sr * 2)

        # Ring
        p.setPen(QPen(_C["pri_dim"], 1))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawEllipse(s_rect)

        # Sweep
        p.setPen(QPen(_C["pri"], 2))
        p.drawArc(s_rect, int(self._scan * 16), 60 * 16)
        p.setPen(QPen(_C["acc"], 1))
        p.drawArc(s_rect, int((self._scan + 180) * 16), 40 * 16)

        # Inner text
        p.setFont(QFont("Courier New", 7, QFont.Weight.Bold))
        p.setPen(QPen(_C["pri"], 1))
        p.drawText(QRectF(s_cx - sr, s_cy - 8, sr * 2, 16),
                   Qt.AlignmentFlag.AlignCenter, "SCAN")

        # ── Last message ticker ───────────────────────────────────────────
        y = H - 42
        p.setPen(QPen(_C["pri_dim"], 1))
        p.drawLine(QPointF(12, y), QPointF(W - 12, y))
        y += 6

        msg = _shared.get("last_message", "")
        if msg:
            ticker_text = f"  {msg}  ···  {msg}  "
            p.setFont(QFont("Courier New", 7))
            p.setPen(QPen(_C["text"], 1))
            # Clip to text area
            p.setClipRect(QRectF(12, y, W - 24, 14))
            # Scroll by offsetting x
            char_w = 7  # approx px per char at 7pt courier
            total_w = len(ticker_text) * char_w
            offset = self._ticker_offset % max(1, total_w)
            p.drawText(QPointF(12 - offset, y + 10), ticker_text + ticker_text)
            p.setClipping(False)

        # ── Bottom corner labels ──────────────────────────────────────────
        y = H - 18
        p.setFont(QFont("Courier New", 6))
        p.setPen(QPen(_C["dim"], 1))
        p.drawText(QRectF(12, y, W - 24, 14), Qt.AlignmentFlag.AlignLeft,  "MARK LI")
        p.drawText(QRectF(12, y, W - 24, 14), Qt.AlignmentFlag.AlignRight, "v2.5")


# ── Module-level HUD instance ─────────────────────────────────────────────────
_hud_widget: "_HUDWidget | None" = None
_hud_lock = threading.Lock()


def _launch_hud(position: str) -> None:
    """Must be called from the Qt main thread via QTimer.singleShot."""
    global _hud_widget
    app = QApplication.instance()
    if app is None:
        return
    if _hud_widget is not None:
        try:
            _hud_widget.close()
        except Exception:
            pass
    _hud_widget = _HUDWidget(position=position)
    _hud_widget.show()


def _close_hud() -> None:
    global _hud_widget
    if _hud_widget is not None:
        try:
            _hud_widget.close()
        except Exception:
            pass
        _hud_widget = None


# ── Plugin entry point ────────────────────────────────────────────────────────

def run(parameters: dict, player=None, session_memory=None) -> str:
    global _hud_widget

    if not _QT_OK:
        return "PyQt6 is not installed — cannot show HUD."

    action   = parameters.get("action", "on").strip().lower()
    position = parameters.get("position", "top-right").strip().lower()

    if action in ("off", "hide", "close", "disable"):
        if _hud_widget is None:
            return "HUD overlay is already off."
        # Schedule close on Qt main thread
        try:
            from PyQt6.QtCore import QTimer as _QT
            _QT.singleShot(0, _close_hud)
        except Exception:
            _close_hud()
        if player:
            player.write_log("JARVIS: HUD overlay deactivated.")
        return "HUD overlay deactivated, sir."

    # action == on
    if _hud_widget is not None and _hud_widget.isVisible():
        return f"HUD overlay is already active, sir."

    if not _PSUTIL:
        if player:
            player.write_log("WRN: psutil not installed — metrics unavailable in HUD.")

    try:
        from PyQt6.QtCore import QTimer as _QT
        _QT.singleShot(0, lambda: _launch_hud(position))
    except Exception as e:
        return f"Could not launch HUD: {e}"

    if player:
        player.write_log(f"JARVIS: HUD overlay activated ({position}).")

    return (
        f"Heads-up display is now active, sir. "
        f"Positioned at {position}, showing live metrics and system state."
    )
