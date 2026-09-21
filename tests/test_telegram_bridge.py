"""
tests/test_telegram_bridge.py — Comprehensive Unit Tests for Telegram & Discord Remote Uplink.
"""
from __future__ import annotations

import json
import os
import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, mock_open, patch

# Ensure repo root is on sys.path
BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from plugins import telegram_bridge
from plugins.telegram_bridge import TelegramBridge, PLUGIN, run


class TestTelegramBridge(unittest.TestCase):
    def setUp(self):
        TelegramBridge._instance = None
        self.bridge = TelegramBridge.get_instance()
        self.bridge.token = "123456:TEST_BOT_TOKEN"
        self.bridge.chat_id = "987654321"
        self.bridge.pair_code = "TEST1234"
        self.bridge.discord_webhook = "https://discord.com/api/webhooks/test"

    def tearDown(self):
        if self.bridge.is_running:
            self.bridge.stop()
        TelegramBridge._instance = None

    def test_plugin_schema(self):
        """Verify plugin conforms to JARVIS plugin contract."""
        self.assertEqual(PLUGIN["name"], "telegram_bridge")
        self.assertIn("description", PLUGIN)
        self.assertIn("parameters", PLUGIN)
        self.assertIn("action", PLUGIN["parameters"]["properties"])

    def test_singleton_instance(self):
        inst1 = TelegramBridge.get_instance()
        inst2 = TelegramBridge.get_instance()
        self.assertIs(inst1, inst2)

    @patch("plugins.telegram_bridge.requests.post")
    def test_send_message_success(self, mock_post):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_post.return_value = mock_resp

        result = self.bridge.send_message("Hello from JARVIS")
        self.assertTrue(result)
        # Should post to both Telegram and Discord
        self.assertEqual(mock_post.call_count, 2)
        telegram_call = mock_post.call_args_list[0]
        self.assertIn("https://api.telegram.org/bot123456:TEST_BOT_TOKEN/sendMessage", telegram_call[0][0])
        self.assertEqual(telegram_call[1]["json"]["text"], "Hello from JARVIS")

    @patch("plugins.telegram_bridge.requests.post")
    def test_send_message_retry_plain_text(self, mock_post):
        """If Markdown parse fails (400), it should retry without parse_mode."""
        resp_fail = MagicMock()
        resp_fail.status_code = 400
        resp_ok = MagicMock()
        resp_ok.status_code = 200

        mock_post.side_effect = [resp_fail, resp_ok, resp_ok]

        result = self.bridge.send_message("Unescaped _ markdown")
        self.assertTrue(result)
        retry_call = mock_post.call_args_list[1]
        self.assertNotIn("parse_mode", retry_call[1]["json"])

    @patch("plugins.telegram_bridge.Path.exists", return_value=True)
    @patch("builtins.open", new_callable=mock_open, read_data=b"fake_image_bytes")
    @patch("plugins.telegram_bridge.requests.post")
    def test_send_photo_success(self, mock_post, mock_file, mock_exists):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_post.return_value = mock_resp

        result = self.bridge.send_photo("/fake/path/snapshot.jpg", caption="Test photo")
        self.assertTrue(result)
        self.assertEqual(mock_post.call_count, 2)  # Telegram + Discord mirror

    def test_send_photo_missing_file(self):
        result = self.bridge.send_photo("/nonexistent/file.jpg")
        self.assertFalse(result)

    def test_pairing_unauthorized_chat(self):
        """Unpaired device sending a command is prompted to pair."""
        self.bridge.chat_id = "111111"
        res = self.bridge.execute_command(chat_id="999999", raw_text="/status")
        self.assertIn("This device is not authorized", res)
        self.assertIn("/pair", res)

    @patch.object(TelegramBridge, "save_chat_id")
    def test_pairing_flow_success(self, mock_save):
        self.bridge.chat_id = ""
        self.bridge.pair_code = "SECRET_PASS"
        res = self.bridge.execute_command(chat_id="555555", raw_text="/pair SECRET_PASS", user_name="Tony")
        self.assertIn("Pairing Successful", res)
        mock_save.assert_called_once_with("555555")

    def test_pairing_flow_invalid_code(self):
        self.bridge.chat_id = ""
        self.bridge.pair_code = "SECRET_PASS"
        res = self.bridge.execute_command(chat_id="555555", raw_text="/pair WRONG_CODE")
        self.assertIn("Invalid Pairing Code", res)

    def test_authorized_command_help(self):
        res = self.bridge.execute_command(chat_id="987654321", raw_text="/help")
        self.assertIn("JARVIS Remote Uplink Control Center", res)
        self.assertIn("/status", res)
        self.assertIn("/screenshot", res)

    def test_authorized_command_status(self):
        res = self.bridge.execute_command(chat_id="987654321", raw_text="/status")
        self.assertIn("JARVIS System Telemetry Report", res)

    @patch("plugins.telegram_bridge.ImageGrab.grab")
    @patch.object(TelegramBridge, "send_photo", return_value=True)
    def test_authorized_command_screenshot(self, mock_send_photo, mock_grab):
        mock_img = MagicMock()
        mock_grab.return_value = mock_img

        res = self.bridge.execute_command(chat_id="987654321", raw_text="/screenshot")
        self.assertIn("Screenshot dispatched", res)
        mock_send_photo.assert_called_once()

    @patch("sys.platform", "win32")
    @patch("ctypes.windll.user32.LockWorkStation", create=True)
    def test_authorized_command_lock(self, mock_lock):
        res = self.bridge.execute_command(chat_id="987654321", raw_text="/lock")
        self.assertIn("Workstation Locked", res)
        mock_lock.assert_called_once()

    @patch("plugins.sentry_mode.SentryController.get_instance")
    def test_authorized_command_sentry(self, mock_sentry_get):
        mock_ctrl = MagicMock()
        mock_ctrl.arm.return_value = "Sentry armed in 3s."
        mock_ctrl.disarm.return_value = "Sentry disarmed."
        mock_ctrl.status.return_value = "Sentry active."
        mock_sentry_get.return_value = mock_ctrl

        res_arm = self.bridge.execute_command(chat_id="987654321", raw_text="/sentry on")
        self.assertIn("Sentry armed in 3s", res_arm)

        res_disarm = self.bridge.execute_command(chat_id="987654321", raw_text="/sentry off")
        self.assertIn("Sentry disarmed", res_disarm)

        res_status = self.bridge.execute_command(chat_id="987654321", raw_text="/sentry status")
        self.assertIn("Sentry active", res_status)

    @patch.object(TelegramBridge, "send_photo", return_value=True)
    def test_sentry_alert_hook(self, mock_send_photo):
        ok = self.bridge.notify_sentry_alert("/path/to/intruder.jpg", incident_num=3)
        self.assertTrue(ok)
        mock_send_photo.assert_called_once()
        args, kwargs = mock_send_photo.call_args
        self.assertEqual(args[0], "/path/to/intruder.jpg")
        self.assertIn("Incident #3", kwargs["caption"])

    def test_run_dispatcher(self):
        with patch.object(self.bridge, "send_message", return_value=True):
            res = run({"action": "send_message", "message": "Test notification"})
            self.assertIn("Message sent to your phone", res)

        with patch.object(self.bridge, "status", return_value="Telegram Bridge is ONLINE."):
            res = run({"action": "status"})
            self.assertIn("ONLINE", res)

        res_err = run({"action": "invalid_action"})
        self.assertIn("Error: Unknown action", res_err)

    def test_start_and_stop_lifecycle(self):
        with patch("threading.Thread") as mock_thread_cls:
            mock_th = MagicMock()
            mock_thread_cls.return_value = mock_th

            res_start = self.bridge.start()
            self.assertIn("Telegram bridge activated", res_start)
            self.assertTrue(self.bridge.is_running)

            res_stop = self.bridge.stop()
            self.assertIn("Telegram bridge stopped", res_stop)
            self.assertFalse(self.bridge.is_running)


if __name__ == "__main__":
    unittest.main()
