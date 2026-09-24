import unittest
import tkinter as tk
from ui.components.search_box import SearchBox
from ui.components.buttons import PrimaryButton


class TestSearchBoxAndPrimaryButtonUX(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        try:
            cls.root = tk.Tk()
            cls.root.withdraw()
            cls.has_tk = True
        except Exception:
            cls.has_tk = False

    @classmethod
    def tearDownClass(cls):
        if getattr(cls, "has_tk", False):
            try:
                cls.root.destroy()
            except Exception:
                pass

    def setUp(self):
        if not self.has_tk:
            self.skipTest("Tkinter display not available")

    def test_primary_button_add_plus_binding(self):
        btn = PrimaryButton(self.root, text="Test")
        # Check bindtable for <Enter> and <Leave>
        enter_binds = btn.bind("<Enter>")
        leave_binds = btn.bind("<Leave>")
        self.assertTrue(len(enter_binds) > 0)
        self.assertTrue(len(leave_binds) > 0)
        btn.destroy()

    def test_search_box_keyboard_navigation(self):
        selected = []
        sb = SearchBox(
            self.root,
            universe=["COMB.N0000", "JKH.N0000"],
            on_select=lambda symbol: selected.append(symbol)
        )
        sb.set("COMB")
        sb._do_search()

        # Check popup opened
        self.assertIsNotNone(sb._popup)

        # Test Down arrow focuses listbox
        res = sb._on_arrow_down()
        self.assertEqual(res, "break")
        self.assertEqual(sb._listbox.curselection(), (0,))

        # Test Escape from listbox closes popup
        res_esc = sb._on_listbox_escape()
        self.assertEqual(res_esc, "break")
        self.assertIsNone(sb._popup)

        # Test Escape from entry closes popup
        sb._do_search()
        self.assertIsNotNone(sb._popup)
        res_esc2 = sb._on_escape()
        self.assertEqual(res_esc2, "break")
        self.assertIsNone(sb._popup)

        sb.destroy()


if __name__ == "__main__":
    unittest.main()
