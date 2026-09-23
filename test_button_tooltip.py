import unittest
from unittest.mock import MagicMock, patch
from ui.components.buttons import IconButton
from ui.components.tooltip import ToolTip

class TestIconButtonTooltip(unittest.TestCase):
    @patch("ui.components.buttons.ThemeManager.tokens")
    @patch("ui.components.buttons.ThemeManager.register_listener")
    @patch("ui.components.tooltip.ToolTip.__init__", return_value=None)
    @patch("tkinter.Button.bind")
    @patch("tkinter.Button.__init__", return_value=None)
    def test_icon_button_tooltip_initialization(self, mock_btn_init, mock_bind, mock_tooltip_init, mock_reg, mock_tokens):
        mock_tokens.return_value = {
            "surface": "#ffffff",
            "text": "#000000",
            "surface_hi": "#f0f0f0",
            "accent": "#0078d4",
            "border": "#e0e0e0",
        }
        mock_parent = MagicMock()

        button_with_tooltip = IconButton(mock_parent, icon="🔍", tooltip="Search stocks")
        self.assertTrue(hasattr(button_with_tooltip, "_tooltip_obj"))
        self.assertIsInstance(button_with_tooltip._tooltip_obj, ToolTip)
        mock_tooltip_init.assert_called_once_with(button_with_tooltip, "Search stocks")

        button_without_tooltip = IconButton(mock_parent, icon="⚙️")
        self.assertFalse(hasattr(button_without_tooltip, "_tooltip_obj"))

if __name__ == "__main__":
    unittest.main()
