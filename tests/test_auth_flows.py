import os
import unittest
from unittest.mock import MagicMock, patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from ankama_launcher_emulator.gui.add_account_dialog import AddAccountDialog
from ankama_launcher_emulator.gui.app import ensure_app
from ankama_launcher_emulator.gui.main_window import MainWindow


class _DummyServer:
    def launch_dofus(self, *args, **kwargs):
        return 1234

    def launch_retro(self, *args, **kwargs):
        return 4321


class _ProxyStore:
    def list_proxies(self):
        return {}

    def get_proxy(self, _proxy_id):
        return None

    def get_assignment(self, _login):
        return None

    def assign_proxy(self, _login, _proxy_id):
        return None

    def save_validated(self, _login, _proxy_url):
        return None


class AuthFlowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = ensure_app()

    @patch("ankama_launcher_emulator.gui.add_account_dialog.run_in_background")
    def test_add_account_falls_back_to_browser_when_headless_pkce_is_blocked(
        self, run_in_background
    ):
        dialog = AddAccountDialog(_ProxyStore())
        dialog._login_input.setText("demo@example.com")
        dialog._password_input.setText("hunter2")

        def fail_headless(task, on_success=None, on_error=None, parent=None):
            del task, on_success, parent
            on_error(RuntimeError("Failed to extract CSRF state from login page"))

        run_in_background.side_effect = fail_headless

        with patch.object(dialog, "_start_browser_login") as start_browser_login:
            dialog._on_add()

        start_browser_login.assert_called_once_with(
            "demo@example.com", None, None
        )

    @patch("ankama_launcher_emulator.gui.main_window.verify_proxy_ip")
    @patch("ankama_launcher_emulator.gui.main_window.build_proxy_listener")
    @patch.object(MainWindow, "_check_shield")
    def test_proxy_launch_does_not_force_oauth_refresh_before_create_token(
        self,
        check_shield,
        build_proxy_listener,
        verify_proxy_ip,
    ):
        proxy_listener = MagicMock()
        proxy_listener.start.return_value = 5555
        build_proxy_listener.return_value = (proxy_listener, "socks5://127.0.0.1:9050")

        window = MainWindow(
            _DummyServer(),
            [{"apikey": {"login": "demo@example.com"}}],
            {},
        )

        progress_updates = []
        pid = window._launch_dofus(
            "demo@example.com",
            interface_ip=None,
            proxy_url="socks5://127.0.0.1:9050",
            on_progress=progress_updates.append,
        )

        self.assertEqual(pid, 1234)
        verify_proxy_ip.assert_called_once_with("socks5://127.0.0.1:9050")
        check_shield.assert_called_once()
        self.assertEqual(progress_updates, ["Verifying proxy..."])
