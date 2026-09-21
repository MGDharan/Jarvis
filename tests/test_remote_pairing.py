"""
Unit tests for remote pairing manager.
"""
import unittest
import time
from remote.pairing import pairing_manager

class TestRemotePairing(unittest.TestCase):
    def test_create_session(self):
        session = pairing_manager.create_pairing_session()
        self.assertIn("pairing_token", session)
        self.assertIn("gateway_url", session)
        self.assertTrue(session["pairing_token"].startswith("pair_"))
        self.assertGreater(session["expires_at"], time.time())

    def test_consume_valid_token(self):
        session = pairing_manager.create_pairing_session()
        token = session["pairing_token"]
        # First use must succeed
        self.assertTrue(pairing_manager.validate_and_consume_token(token))
        # Second use must fail (single-use)
        self.assertFalse(pairing_manager.validate_and_consume_token(token))

    def test_invalid_token(self):
        self.assertFalse(pairing_manager.validate_and_consume_token("pair_fake_12345"))

if __name__ == "__main__":
    unittest.main()
