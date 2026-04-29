import unittest
from unittest.mock import MagicMock, patch

from ankama_launcher_emulator.server.handler import AnkamaLauncherHandler
from ankama_launcher_emulator.server.server import AnkamaLauncherServer


class ServerStartupTests(unittest.TestCase):
    @patch("ankama_launcher_emulator.server.server.RetroTextSocketServer")
    @patch("ankama_launcher_emulator.server.server.Thread")
    @patch("ankama_launcher_emulator.server.server.TServer.TThreadedServer")
    @patch("ankama_launcher_emulator.server.server.TSocket.TServerSocket")
    def test_start_skips_process_scan_when_port_is_available(
        self,
        server_socket_cls,
        threaded_server_cls,
        thread_cls,
        retro_text_socket_server_cls,
    ):
        server = AnkamaLauncherServer(AnkamaLauncherHandler())

        with patch.object(server, "_port_is_available", return_value=True):
            with patch.object(server, "_stop_existing_launcher_on_port") as stop_existing:
                server.start()

        stop_existing.assert_not_called()
        server_socket_cls.assert_called_once()
        threaded_server_cls.assert_called_once()
        thread_cls.assert_called_once()
        retro_text_socket_server_cls.return_value.start.assert_called_once_with()

    @patch("ankama_launcher_emulator.server.server.RetroTextSocketServer")
    @patch("ankama_launcher_emulator.server.server.Thread")
    @patch("ankama_launcher_emulator.server.server.TServer.TThreadedServer")
    @patch("ankama_launcher_emulator.server.server.TSocket.TServerSocket")
    def test_start_cleans_up_existing_listener_when_port_is_busy(
        self,
        server_socket_cls,
        threaded_server_cls,
        thread_cls,
        retro_text_socket_server_cls,
    ):
        server = AnkamaLauncherServer(AnkamaLauncherHandler())

        with patch.object(server, "_port_is_available", return_value=False):
            with patch.object(server, "_stop_existing_launcher_on_port") as stop_existing:
                server.start()

        stop_existing.assert_called_once_with()
        server_socket_cls.assert_called_once()
        threaded_server_cls.assert_called_once()
        thread_cls.assert_called_once()
        retro_text_socket_server_cls.return_value.start.assert_called_once_with()
