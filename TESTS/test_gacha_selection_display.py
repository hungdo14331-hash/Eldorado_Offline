import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
INDEX = ROOT / "ELDORADO_WEB" / "source_20240722" / "index__mobile.html"


class GachaSelectionDisplayTest(unittest.TestCase):
    def test_item_selection_draws_show_bp_prices_and_icon(self):
        source = INDEX.read_text(encoding="utf-8")

        self.assertIn("__eldItemGachaBpDisplay", source)
        self.assertIn("this.type_num === 26 ? 1000 : 10000", source)
        self.assertIn("image/ui/40_package_store/co_bp.png", source)
        self.assertIn('utilGetNumber_withComma(String(bpPrice)) + " BP"', source)
        self.assertNotIn("cp_selectionpop_bt_rubyicon.png", source)

    def test_ruby_item_gacha_does_not_apply_ep_grade_override(self):
        source = INDEX.read_text(encoding="utf-8")

        # Ruby item packages are the five native offers: 10, 50, 50, 300,
        # and 300 Ruby. They must keep the game's original grade roll.
        self.assertIn("EP_GRADE override disabled for Ruby item gacha", source)
        self.assertNotIn("c.calculate = function", source)
        self.assertNotIn("item_gacha_ep_status", source)
        self.assertNotIn("Math.random() * 3", source)


if __name__ == "__main__":
    unittest.main()
