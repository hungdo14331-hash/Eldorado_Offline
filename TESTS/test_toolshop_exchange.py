import json
import sys
import tempfile
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import serve


class ToolshopExchangeContractTest(unittest.TestCase):
    def setUp(self):
        self._old_save_file = serve.SAVE_FILE
        self._old_db_file = serve.DB_FILE
        self._old_db_conn = serve.DB_CONN
        self._old_uid = getattr(serve._tl, "uid", None)
        self._tmp = tempfile.TemporaryDirectory()
        serve.SAVE_FILE = Path(self._tmp.name) / "toolshop_save.json"
        serve.DB_FILE = None
        serve.DB_CONN = None
        serve.SAVE_FILE.write_text(
            json.dumps({
                "DATA1": "TEST,1000000,100000",
                "USER_NAME": "TEST",
                "bp": "1000",
                "cloud_piece": "100",
                "celestial_essence": "50",
            }),
            encoding="utf-8",
        )

    def tearDown(self):
        serve.DB_CONN = self._old_db_conn
        serve.SAVE_FILE = self._old_save_file
        serve.DB_FILE = self._old_db_file
        if self._old_uid is None:
            try:
                del serve._tl.uid
            except AttributeError:
                pass
        else:
            serve._tl.uid = self._old_uid
        self._tmp.cleanup()

    def test_balances_expose_only_the_six_supported_pairs(self):
        status, raw = serve.offline_stub(
            "/ELDORADO_WEB/toolshop/get_balances.php", ""
        )
        self.assertEqual(200, status)
        response = json.loads(raw)
        pairs = [(item["from"], item["to"]) for item in response["rates"]]
        self.assertEqual(
            [
                ("GOLD", "BP"),
                ("RUBY", "BP"),
                ("GOLD", "RUBY"),
                ("RUBY", "GOLD"),
                ("RUBY", "CLOUD"),
                ("RUBY", "ESSENCE"),
            ],
            pairs,
        )

    def test_unsupported_pair_is_rejected(self):
        status, raw = serve.offline_stub(
            "/ELDORADO_WEB/toolshop/convert.php",
            "FROM=GOLD&TO=CLOUD&COUNT=120000",
        )
        self.assertEqual(200, status)
        self.assertEqual(
            {"STATE": "ERROR", "msg": "unknown pair"}, json.loads(raw)
        )

    def test_rubyfarm_page_filters_to_the_same_six_pairs(self):
        html = (PROJECT_ROOT / "ELDORADO_WEB" / "rubyfarm.html").read_text(
            encoding="utf-8"
        )
        self.assertIn("ALLOWED_CONVERT_PAIRS", html)
        for pair in (
            '"GOLD>BP"', '"RUBY>BP"', '"GOLD>RUBY"',
            '"RUBY>GOLD"', '"RUBY>CLOUD"', '"RUBY>ESSENCE"',
        ):
            self.assertIn(pair, html)
        self.assertRegex(
            html,
            r'_convertRates\s*=\s*\(bals\.rates \|\| \[\]\)\.filter\(',
        )


if __name__ == "__main__":
    unittest.main()
