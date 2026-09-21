"""
Unit tests for remote device authentication and revocation.
"""
import unittest
from remote.auth import device_auth_manager

class TestRemoteAuth(unittest.TestCase):
    def test_register_and_validate(self):
        dev_id, raw_token = device_auth_manager.register_device("Test Pixel Phone", "Android 14", "192.168.1.50")
        self.assertTrue(dev_id.startswith("dev_"))
        self.assertTrue(raw_token.startswith("jarvis_sec_"))

        # Valid token succeeds
        self.assertTrue(device_auth_manager.validate_token(dev_id, raw_token))
        # Wrong token fails
        self.assertFalse(device_auth_manager.validate_token(dev_id, "wrong_token"))

    def test_revocation_lifecycle(self):
        dev_id, raw_token = device_auth_manager.register_device("Revoke Test Phone", "Android", "127.0.0.1")
        self.assertTrue(device_auth_manager.validate_token(dev_id, raw_token))

        # Revoke device
        self.assertTrue(device_auth_manager.revoke_device(dev_id, "Test revocation"))
        self.assertTrue(device_auth_manager.is_revoked(dev_id))

        # Validation must now fail immediately
        self.assertFalse(device_auth_manager.validate_token(dev_id, raw_token))

if __name__ == "__main__":
    unittest.main()
