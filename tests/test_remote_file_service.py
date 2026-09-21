"""
Unit tests for safe file search, path traversal protection, and transfer preparation.
"""
import unittest
import tempfile
from pathlib import Path
from remote.file_service import remote_file_service, FileSecurityError

class TestRemoteFileService(unittest.TestCase):
    def test_path_traversal_blocking(self):
        # Attempt to escape with ../
        self.assertFalse(remote_file_service.is_safe_path("../../../Windows/System32"))
        self.assertFalse(remote_file_service.is_safe_path("C:/Windows/System32/cmd.exe"))
        self.assertFalse(remote_file_service.is_safe_path("C:/Windows"))

    def test_sensitive_files_blocking(self):
        # Sensitive files must never be safe
        self.assertFalse(remote_file_service.is_safe_path("config/api_keys.json"))
        self.assertFalse(remote_file_service.is_safe_path(".env"))
        self.assertFalse(remote_file_service.is_safe_path("id_rsa"))

    def test_safe_search_and_prepare_transfer(self):
        # Create a test folder inside user home documents or current repo
        test_dir = Path("f:/jarvis/jarvis/data/test_transfer_folder")
        test_dir.mkdir(parents=True, exist_ok=True)
        pdf1 = test_dir / "report1.pdf"
        pdf2 = test_dir / "report2.pdf"
        pdf1.write_text("Test PDF content 1", encoding="utf-8")
        pdf2.write_text("Test PDF content 2", encoding="utf-8")

        try:
            # Safe path check
            self.assertTrue(remote_file_service.is_safe_path(test_dir))

            # Prepare bundle transfer
            prep = remote_file_service.prepare_transfer(str(test_dir), "pdf", device_id="test_dev")
            self.assertIn("transfer_id", prep)
            self.assertEqual(prep["file_count"], 2)
            self.assertIn("sha256", prep)

            # Retrieve transfer
            t_data = remote_file_service.get_transfer(prep["transfer_id"])
            self.assertIsNotNone(t_data)
            self.assertTrue(Path(t_data["file_path"]).exists())
        finally:
            pdf1.unlink(missing_ok=True)
            pdf2.unlink(missing_ok=True)
            test_dir.rmdir()

if __name__ == "__main__":
    unittest.main()
