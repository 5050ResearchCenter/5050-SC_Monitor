import unittest
from unittest.mock import Mock, patch

from gui import SCMonitorApp
from monitor_utils import WorkArea, calculate_popup_position, position_popup_window


class MonitorPositionTests(unittest.TestCase):
    def test_tip_follows_pointer_to_monitor_on_the_right(self):
        area = WorkArea(left=1920, top=0, right=3840, bottom=1040)

        position = calculate_popup_position(2500, 400, 300, 120, area)

        self.assertEqual(position, (2514, 418))

    def test_tip_preserves_negative_coordinates_on_monitor_to_the_left(self):
        area = WorkArea(left=-1920, top=-200, right=0, bottom=880)

        position = calculate_popup_position(-1000, 100, 300, 120, area)

        self.assertEqual(position, (-986, 118))

    def test_tip_is_clamped_to_current_monitor_work_area(self):
        area = WorkArea(left=1920, top=0, right=3840, bottom=1040)

        position = calculate_popup_position(3800, 1020, 300, 120, area)

        self.assertEqual(position, (3532, 912))

    @patch("gui.position_popup_window")
    @patch("gui.get_monitor_work_area")
    def test_gui_uses_monitor_containing_pointer(self, mock_work_area, mock_position):
        app = SCMonitorApp.__new__(SCMonitorApp)
        app.root = Mock()
        app.root.winfo_screenwidth.return_value = 1920
        app.root.winfo_screenheight.return_value = 1080
        tip = Mock()
        tip.winfo_reqwidth.return_value = 300
        tip.winfo_reqheight.return_value = 120
        mock_work_area.return_value = WorkArea(-1920, 0, 0, 1080)

        app._position_floating_tip(tip, -1000, 100)

        mock_work_area.assert_called_once_with(-1000, 100)
        mock_position.assert_called_once_with(
            tip,
            -986,
            118,
            300,
            120,
            tk_screen_width=1920,
            tk_screen_height=1080,
        )

    @patch("monitor_utils._set_windows_position", return_value=False)
    def test_tk_fallback_converts_absolute_negative_coordinates(self, _mock_native):
        window = Mock()

        position_popup_window(
            window,
            -986,
            -100,
            300,
            120,
            tk_screen_width=1920,
            tk_screen_height=1080,
        )

        window.geometry.assert_called_once_with("300x120-2606-1060")


if __name__ == "__main__":
    unittest.main()
