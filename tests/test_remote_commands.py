"""
Unit tests for structured command routing and remote assistant queries.
"""
import unittest
import asyncio
from remote.commands import remote_command_router

class TestRemoteCommands(unittest.TestCase):
    def setUp(self):
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)

    def tearDown(self):
        self.loop.close()

    def test_system_status_command(self):
        cmd = {
            "request_id": "req_001",
            "type": "command",
            "command": "system_status",
            "arguments": {},
        }
        res = self.loop.run_until_complete(
            remote_command_router.handle_command(cmd, device_id="test_dev")
        )
        self.assertEqual(res["status"], "success")
        self.assertIn("CPU is", res["message"])
        self.assertIn("telemetry", res)

    def test_voice_query_cpu_intent(self):
        cmd = {
            "request_id": "req_002",
            "type": "command",
            "command": "voice_query",
            "arguments": {"query": "What is my CPU usage?", "include_audio": False},
        }
        res = self.loop.run_until_complete(
            remote_command_router.handle_command(cmd, device_id="test_dev")
        )
        self.assertEqual(res["status"], "success")
        self.assertIn("CPU is", res["message"])

    def test_voice_query_shutdown_intent(self):
        cmd = {
            "request_id": "req_003",
            "type": "command",
            "command": "voice_query",
            "arguments": {"query": "JARVIS, shut down my lab laptop", "include_audio": False},
        }
        res = self.loop.run_until_complete(
            remote_command_router.handle_command(cmd, device_id="test_dev")
        )
        self.assertEqual(res["status"], "confirmation_required")
        self.assertIn("challenge", res)

    def test_unknown_command(self):
        cmd = {
            "request_id": "req_004",
            "type": "command",
            "command": "nonexistent_command_xyz",
            "arguments": {},
        }
        res = self.loop.run_until_complete(
            remote_command_router.handle_command(cmd, device_id="test_dev")
        )
        self.assertEqual(res["status"], "error")

if __name__ == "__main__":
    unittest.main()
