import unittest
from unittest.mock import patch, MagicMock
import os
import sys

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from plugins import audio_matrix


class TestAudioMatrix(unittest.TestCase):
    def _create_mock_session(self, proc_name, volume=0.8, is_muted=0):
        mock_proc = MagicMock()
        mock_proc.name.return_value = proc_name

        mock_vol = MagicMock()
        mock_vol.GetMasterVolume.return_value = volume
        mock_vol.GetMute.return_value = is_muted

        mock_session = MagicMock()
        mock_session.Process = mock_proc
        mock_session._ctl.QueryInterface.return_value = mock_vol

        return mock_session, mock_vol

    @patch('plugins.audio_matrix._get_audio_sessions')
    def test_list_active_sessions(self, mock_get_sessions):
        s1, v1 = self._create_mock_session("Spotify.exe", 0.75, 0)
        s2, v2 = self._create_mock_session("Discord.exe", 0.50, 1)

        mock_get_sessions.return_value = ([s1, s2], MagicMock())

        res = audio_matrix.run({"action": "list"})
        self.assertIn("Spotify (75%)", res)
        self.assertIn("Discord (muted)", res)

    @patch('plugins.audio_matrix._get_audio_sessions')
    def test_set_volume(self, mock_get_sessions):
        s1, v1 = self._create_mock_session("Spotify.exe", 0.75, 0)
        mock_get_sessions.return_value = ([s1], MagicMock())

        res = audio_matrix.run({"action": "set_volume", "app_name": "spotify", "volume": 35})
        v1.SetMasterVolume.assert_called_once_with(0.35, None)
        v1.SetMute.assert_called_once_with(0, None)
        self.assertIn("Set Spotify volume to 35%", res)

    @patch('plugins.audio_matrix._get_audio_sessions')
    def test_mute_and_unmute(self, mock_get_sessions):
        s1, v1 = self._create_mock_session("Discord.exe", 0.5, 0)
        mock_get_sessions.return_value = ([s1], MagicMock())

        res_mute = audio_matrix.run({"action": "mute", "app_name": "Discord"})
        v1.SetMute.assert_called_with(1, None)
        self.assertIn("Muted Discord", res_mute)

        res_unmute = audio_matrix.run({"action": "unmute", "app_name": "Discord"})
        v1.SetMute.assert_called_with(0, None)
        self.assertIn("Unmuted Discord", res_unmute)

    @patch('plugins.audio_matrix._get_audio_sessions')
    def test_mute_all_except(self, mock_get_sessions):
        s1, v1 = self._create_mock_session("Game.exe", 1.0, 1)
        s2, v2 = self._create_mock_session("Spotify.exe", 0.8, 0)
        s3, v3 = self._create_mock_session("Chrome.exe", 0.6, 0)

        mock_get_sessions.return_value = ([s1, s2, s3], MagicMock())

        res = audio_matrix.run({"action": "mute_all_except", "app_name": "Game"})
        v1.SetMute.assert_called_with(0, None)
        v2.SetMute.assert_called_with(1, None)
        v3.SetMute.assert_called_with(1, None)
        self.assertIn("Isolated audio to Game", res)

    @patch('plugins.audio_matrix._get_audio_sessions')
    def test_duck_background(self, mock_get_sessions):
        s1, v1 = self._create_mock_session("VoiceChat.exe", 1.0, 0)
        s2, v2 = self._create_mock_session("Spotify.exe", 0.8, 0)
        s3, v3 = self._create_mock_session("Game.exe", 0.9, 0)

        mock_get_sessions.return_value = ([s1, s2, s3], MagicMock())

        res = audio_matrix.run({"action": "duck", "app_name": "VoiceChat", "volume": 20})
        v1.SetMute.assert_called_with(0, None)
        v2.SetMasterVolume.assert_called_with(0.2, None)
        v3.SetMasterVolume.assert_called_with(0.2, None)
        self.assertIn("Ducked background audio", res)

    @patch('plugins.audio_matrix._get_audio_sessions')
    def test_app_not_found(self, mock_get_sessions):
        s1, v1 = self._create_mock_session("Chrome.exe", 0.5, 0)
        mock_get_sessions.return_value = ([s1], MagicMock())

        res = audio_matrix.run({"action": "mute", "app_name": "NonExistentApp"})
        self.assertIn("No active audio stream found", res)


if __name__ == "__main__":
    unittest.main()
