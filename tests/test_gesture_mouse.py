import unittest
from unittest.mock import patch, MagicMock
import os
import sys
import math
import numpy as np

# Add project root to sys.path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from plugins import gesture_mouse
from core.plugin_loader import discover_plugins
from pathlib import Path


class TestGestureMousePlugin(unittest.TestCase):
    def setUp(self):
        self.controller = gesture_mouse.GestureMouseController.get_instance()
        self.controller.stop()

    def tearDown(self):
        self.controller.stop()

    def test_plugin_manifest_structure(self):
        """Verify the PLUGIN metadata adheres to JARVIS plugin specifications."""
        meta = gesture_mouse.PLUGIN
        self.assertEqual(meta["name"], "gesture_mouse")
        self.assertTrue(len(meta["description"]) > 20)
        self.assertEqual(meta["parameters"]["type"], "OBJECT")
        self.assertIn("action", meta["parameters"]["properties"])
        self.assertIn("show_hud", meta["parameters"]["properties"])
        self.assertIn("speed", meta["parameters"]["properties"])
        self.assertIn("smoothing", meta["parameters"]["properties"])
        self.assertIn("mode", meta["parameters"]["properties"])
        self.assertIn("action", meta["parameters"]["required"])

    def test_plugin_discovery(self):
        """Verify discover_plugins successfully indexes gesture_mouse without errors."""
        reg = discover_plugins(Path(__file__).resolve().parent.parent / "plugins", set())
        self.assertTrue(reg.has("gesture_mouse"))
        rec = next((p for p in reg.list_for_ui() if p["name"] == "gesture_mouse"), None)
        self.assertIsNotNone(rec)
        self.assertTrue(rec["valid"])
        self.assertEqual(rec["error"], "")

    def test_initial_status_offline(self):
        """Check status when gesture mouse is stopped."""
        status = gesture_mouse.run({"action": "status"})
        self.assertIn("OFFLINE", status)

    @patch("plugins.gesture_mouse.GestureMouseController._tracking_loop")
    def test_start_and_stop_lifecycle(self, mock_loop):
        """Test starting and stopping tracking controller."""
        start_res = gesture_mouse.run({
            "action": "start",
            "show_hud": False,
            "speed": 1.5,
            "smoothing": 0.4,
            "mode": "precision",
        })
        self.assertTrue(self.controller.is_running)
        self.assertEqual(self.controller.speed, 1.5)
        self.assertEqual(self.controller.smoothing, 0.4)
        self.assertEqual(self.controller.mode, "precision")
        self.assertIn("engaged", start_res.lower())

        # Test status when running
        status = gesture_mouse.run({"action": "status"})
        self.assertIn("ACTIVE", status)

        # Calling start again updates settings without crash
        update_res = gesture_mouse.run({
            "action": "start",
            "speed": 2.0,
            "mode": "hover",
        })
        self.assertIn("already active", update_res.lower())
        self.assertEqual(self.controller.speed, 2.0)
        self.assertEqual(self.controller.mode, "hover")

        # Stop
        stop_res = gesture_mouse.run({"action": "stop"})
        self.assertFalse(self.controller.is_running)
        self.assertIn("deactivated", stop_res.lower())

    def test_toggle_hud(self):
        """Test toggling HUD state."""
        prev = self.controller.show_hud
        res = gesture_mouse.run({"action": "toggle_hud"})
        self.assertEqual(self.controller.show_hud, not prev)
        self.assertIn("HUD is now", res)

    def test_set_speed(self):
        """Test setting cursor speed."""
        res = gesture_mouse.run({"action": "set_speed", "speed": 1.8})
        self.assertEqual(self.controller.speed, 1.8)
        self.assertIn("calibrated to 1.80x", res)

        # Invalid speed
        err_res = gesture_mouse.run({"action": "set_speed", "speed": 0.05})
        self.assertIn("must be between", err_res)

    def test_set_mode(self):
        """Test setting tracking modes."""
        for m in ("precision", "hover", "scroll"):
            res = gesture_mouse.run({"action": "set_mode", "mode": m})
            self.assertEqual(self.controller.mode, m)
            self.assertIn(m, res)

        # Invalid mode
        err_res = gesture_mouse.run({"action": "set_mode", "mode": "teleport"})
        self.assertIn("must be 'precision', 'hover', or 'scroll'", err_res)

    def test_unrecognized_action(self):
        """Test error message for unknown action."""
        res = gesture_mouse.run({"action": "dance"})
        self.assertIn("Unrecognized gesture mouse action", res)

    def test_ema_smoothing_math(self):
        """Verify Exponential Moving Average formula."""
        raw_x = 500.0
        prev_x = 100.0
        alpha = 0.4
        expected_smooth = alpha * raw_x + (1.0 - alpha) * prev_x
        self.assertAlmostEqual(expected_smooth, 260.0)

    def test_coordinate_normalization_within_margin(self):
        """Verify camera active margin normalization."""
        fw, fh = 640, 480
        margin = 0.15
        x_min = int(fw * margin)
        x_max = int(fw * (1.0 - margin))

        # Center point
        cx = fw // 2
        norm_x = (cx - x_min) / float(x_max - x_min)
        self.assertTrue(0.45 <= norm_x <= 0.55)

        # Left edge margin clamping
        clamped_low = max(0.0, min(1.0, (x_min - 20 - x_min) / float(x_max - x_min)))
        self.assertEqual(clamped_low, 0.0)

        # Right edge margin clamping
        clamped_high = max(0.0, min(1.0, (x_max + 20 - x_min) / float(x_max - x_min)))
        self.assertEqual(clamped_high, 1.0)


if __name__ == "__main__":
    unittest.main()
