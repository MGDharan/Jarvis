import unittest
from unittest.mock import patch, MagicMock
import os
import sys
import numpy as np

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from plugins import sentry_mode


class TestSentryMode(unittest.TestCase):
    def setUp(self):
        self.controller = sentry_mode.SentryController.get_instance()
        self.controller.disarm()
        self.controller.incidents.clear()

    def tearDown(self):
        self.controller.disarm()
        self.controller.incidents.clear()

    def test_initial_status_disarmed(self):
        res = sentry_mode.run({"action": "status"})
        self.assertIn("offline", res.lower())

    @patch('plugins.sentry_mode.SentryController._surveillance_loop')
    def test_arm_sentry_mode(self, mock_loop):
        res = sentry_mode.run({"action": "arm", "countdown": 3, "sensitivity": "high"})
        self.assertEqual(self.controller.state, "ARMING")
        self.assertIn("Sentry mode initiated", res)
        self.assertIn("3 seconds", res)
        self.assertEqual(self.controller.sensitivity, "high")

    @patch('plugins.sentry_mode.SentryController._surveillance_loop')
    def test_disarm_sentry_mode(self, mock_loop):
        sentry_mode.run({"action": "arm", "countdown": 1})
        self.assertEqual(self.controller.state, "ARMING")

        res = sentry_mode.run({"action": "disarm"})
        self.assertEqual(self.controller.state, "DISARMED")
        self.assertIn("Stand down confirmed", res)

    def test_clear_incidents(self):
        self.controller.incidents.append({"timestamp": "2026-09-07 10:00:00", "file": "test.jpg", "area": 3000})
        self.assertEqual(len(self.controller.incidents), 1)

        res = sentry_mode.run({"action": "clear_incidents"})
        self.assertIn("Cleared 1", res)
        self.assertEqual(len(self.controller.incidents), 0)

    @patch('cv2.VideoCapture')
    def test_motion_detection_trigger(self, mock_vid_cap):
        mock_cap = MagicMock()
        mock_cap.isOpened.return_value = True

        # Create two consecutive frames: first black, second with a bright white rectangle (motion)
        frame1 = np.zeros((480, 640, 3), dtype=np.uint8)
        frame2 = np.zeros((480, 640, 3), dtype=np.uint8)
        frame2[100:300, 100:300] = 255  # Large moving block

        # Warmup frames (black), followed by reference frame (black), then motion frame (white block)
        warmup = [(True, frame1.copy()) for _ in range(7)]
        motion = [(True, frame2.copy()) for _ in range(5)]
        frames = warmup + motion

        def read_side_effect():
            if frames:
                return frames.pop(0)
            self.controller._stop_event.set()
            return (False, None)

        mock_cap.read.side_effect = read_side_effect
        mock_vid_cap.return_value = mock_cap

        mock_player = MagicMock()
        self.controller.player = mock_player
        self.controller.sensitivity = "high"
        self.controller._stop_event.clear()

        # Run surveillance loop directly with 0 countdown
        self.controller._surveillance_loop(countdown=0)

        # Verify incident was logged
        self.assertGreater(len(self.controller.incidents), 0)
        self.assertEqual(self.controller.state, "DISARMED")  # Finishes in disarmed state


if __name__ == "__main__":
    unittest.main()
