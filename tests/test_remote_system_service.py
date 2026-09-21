"""
Unit tests for system telemetry, app allowlists, and dangerous action challenges.
"""
import unittest
from remote.system_service import remote_system_service

class TestRemoteSystemService(unittest.TestCase):
    def test_telemetry_fields(self):
        tel = remote_system_service.get_telemetry()
        self.assertIn("cpu_percent", tel)
        self.assertIn("ram_percent", tel)
        self.assertIn("gpu", tel)
        self.assertIn("battery", tel)
        self.assertIn("disk", tel)
        self.assertGreaterEqual(tel["cpu_percent"], 0.0)

    def test_app_allowlist_blocking(self):
        # Arbitrary/malicious executable must be blocked
        res = remote_system_service.launch_application("malicious_worm.exe", device_id="test_dev")
        self.assertEqual(res["status"], "error")
        self.assertIn("allowlist", res["message"].lower())

    def test_dangerous_challenge_lifecycle(self):
        # Request shutdown challenge
        chal = remote_system_service.create_dangerous_challenge("shutdown", device_id="test_dev")
        self.assertEqual(chal["status"], "confirmation_required")
        chal_id = chal["challenge_id"]

        # Fake challenge ID must fail
        fake_res = remote_system_service.verify_and_execute_challenge("chal_fake_999", device_id="test_dev")
        self.assertEqual(fake_res["status"], "error")

if __name__ == "__main__":
    unittest.main()
