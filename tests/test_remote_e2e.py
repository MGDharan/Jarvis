"""
End-to-End integration tests for Mobile Remote Gateway API.
"""
import unittest
from fastapi.testclient import TestClient
from remote.gateway import RemoteGateway
from remote.pairing import pairing_manager
from remote.auth import device_auth_manager

class TestRemoteE2E(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.gateway = RemoteGateway()
        cls.client = TestClient(cls.gateway.app)

    def test_health_check(self):
        resp = self.client.get("/api/health")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json().get("status"), "online")

    def test_pairing_handshake_flow(self):
        # 1. Create short-lived pairing session
        session = pairing_manager.create_pairing_session()
        token = session["pairing_token"]

        # 2. Perform handshake POST
        resp = self.client.post(
            "/api/pair/handshake",
            json={
                "pairing_token": token,
                "device_name": "E2E Test Android Phone",
                "device_model": "Pixel 8"
            }
        )
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertEqual(body["status"], "success")
        self.assertIn("device_id", body)
        self.assertIn("auth_token", body)

        device_id = body["device_id"]
        auth_token = body["auth_token"]

        # 3. Device should be authorized
        self.assertTrue(device_auth_manager.validate_token(device_id, auth_token))

        # 4. Same token cannot be reused (single use)
        reused_resp = self.client.post(
            "/api/pair/handshake",
            json={
                "pairing_token": token,
                "device_name": "Replay Attacker Phone",
                "device_model": "Android"
            }
        )
        self.assertEqual(reused_resp.status_code, 403)

        # 5. Revocation test
        self.assertTrue(device_auth_manager.revoke_device(device_id))
        self.assertFalse(device_auth_manager.validate_token(device_id, auth_token))

if __name__ == "__main__":
    unittest.main()
