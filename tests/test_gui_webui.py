import unittest
from unittest.mock import Mock, patch

from gui import SCMonitorApp


class WebUIToggleTests(unittest.TestCase):
    @staticmethod
    def make_app(enabled):
        app = SCMonitorApp.__new__(SCMonitorApp)
        app.root = Mock()
        app._webui_var = Mock()
        app._webui_var.get.return_value = enabled
        app._btn_webui = Mock()
        app._webui_server = None
        app._webui_starting = False
        app._sc_store = Mock()
        app.set_status = Mock()
        return app

    def test_turning_off_stops_the_server(self):
        app = self.make_app(False)
        server = Mock()
        app._webui_server = server

        app._toggle_webui()

        server.stop.assert_called_once_with()
        self.assertIsNone(app._webui_server)

    @patch("gui.webbrowser.open")
    def test_successful_start_opens_browser_and_updates_toggle(self, open_browser):
        app = self.make_app(True)
        server = Mock()

        app._finish_webui_start(server, "http://127.0.0.1:12345/", None)

        self.assertIs(app._webui_server, server)
        app._webui_var.set.assert_called_once_with(True)
        open_browser.assert_called_once_with("http://127.0.0.1:12345/")

    @patch("gui.messagebox.showerror")
    def test_missing_database_rejects_start(self, show_error):
        app = self.make_app(True)
        app._sc_store = None

        app._toggle_webui()

        app._webui_var.set.assert_called_once_with(False)
        show_error.assert_called_once()

    @patch("gui.threading.Thread")
    def test_start_keeps_toggle_enabled_and_uses_stable_text(self, thread_class):
        app = self.make_app(True)

        app._toggle_webui()

        app._btn_webui.config.assert_called_once_with(text="🌐 WebUI: 开")
        thread_class.return_value.start.assert_called_once_with()

    def test_click_during_start_restores_selected_state(self):
        app = self.make_app(False)
        app._webui_starting = True

        app._toggle_webui()

        app._webui_var.set.assert_called_once_with(True)
        app._btn_webui.config.assert_not_called()


if __name__ == "__main__":
    unittest.main()
