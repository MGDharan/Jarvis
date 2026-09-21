import unittest
from unittest.mock import patch, MagicMock
from pathlib import Path
import tempfile
import shutil

from plugins.software_dev_controller import (
    _sanitize_name,
    _derive_project_name,
    _get_login_page_files,
    _get_generic_web_files,
    _get_python_files,
    run,
    PLUGIN,
)


class TestSoftwareDevController(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_plugin_declaration(self):
        self.assertEqual(PLUGIN["name"], "software_dev_controller")
        self.assertIn("parameters", PLUGIN)
        self.assertIn("action", PLUGIN["parameters"]["properties"])
        self.assertIn("login page", PLUGIN["description"].lower())

    def test_sanitize_and_derive_name(self):
        self.assertEqual(_sanitize_name("My Great App!"), "my-great-app")
        self.assertEqual(_sanitize_name("Test@#$%Project"), "testproject")
        
        # Keyword derivations
        self.assertEqual(_derive_project_name("create_project", "build a modern login page", None), "login-page")
        self.assertEqual(_derive_project_name("create_project", "create an analytics dashboard", None), "analytics-dashboard")
        self.assertEqual(_derive_project_name("create_project", "make a todo app with react", None), "todo-app")
        self.assertEqual(_derive_project_name("create_project", "something custom", "my-custom-tool"), "my-custom-tool")

    def test_template_generators(self):
        login_files = _get_login_page_files()
        self.assertIn("index.html", login_files)
        self.assertIn("style.css", login_files)
        self.assertIn("app.js", login_files)
        self.assertIn("README.md", login_files)
        self.assertIn("NEXUS", login_files["index.html"])
        self.assertIn("glass-card", login_files["style.css"])

        generic_files = _get_generic_web_files("Calculator", "A simple calculator")
        self.assertIn("index.html", generic_files)
        self.assertIn("Calculator", generic_files["index.html"])

        py_files = _get_python_files("cli-tool", "Command line utility")
        self.assertIn("main.py", py_files)
        self.assertIn("requirements.txt", py_files)

    @patch("plugins.software_dev_controller.PROJECTS_DIR")
    @patch("plugins.software_dev_controller.subprocess.Popen")
    @patch("plugins.software_dev_controller.webbrowser.open")
    def test_create_login_project(self, mock_browser, mock_popen, mock_projects_dir):
        mock_projects_dir.__truediv__.side_effect = lambda x: Path(self.temp_dir) / x
        mock_projects_dir.__str__.return_value = self.temp_dir

        params = {
            "action": "create_project",
            "prompt": "build modern login page",
            "open_browser": True
        }

        mock_player = MagicMock()
        response = run(params, player=mock_player)

        self.assertIn("login-page", response)
        project_folder = Path(self.temp_dir) / "login-page"
        self.assertTrue(project_folder.exists())
        self.assertTrue((project_folder / "index.html").exists())
        self.assertTrue((project_folder / "style.css").exists())
        self.assertTrue((project_folder / "app.js").exists())
        self.assertTrue((project_folder / ".agents" / "rules.md").exists())

        # Verify browser and ide were invoked
        mock_browser.assert_called_once()
        mock_popen.assert_called()

    @patch("plugins.software_dev_controller.PROJECTS_DIR")
    @patch("plugins.software_dev_controller.subprocess.Popen")
    @patch("plugins.software_dev_controller.webbrowser.open")
    def test_create_python_project(self, mock_browser, mock_popen, mock_projects_dir):
        mock_projects_dir.__truediv__.side_effect = lambda x: Path(self.temp_dir) / x
        mock_projects_dir.__str__.return_value = self.temp_dir

        params = {
            "action": "create_project",
            "project_name": "data-processor",
            "project_type": "python",
            "prompt": "Python data ETL processor",
            "open_browser": False
        }

        response = run(params)
        self.assertIn("data-processor", response)
        project_folder = Path(self.temp_dir) / "data-processor"
        self.assertTrue(project_folder.exists())
        self.assertTrue((project_folder / "main.py").exists())
        self.assertTrue((project_folder / "requirements.txt").exists())
        mock_browser.assert_not_called()

    def test_unknown_action(self):
        res = run({"action": "invalid_command_xyz"})
        self.assertIn("Unknown action", res)


if __name__ == "__main__":
    unittest.main()
