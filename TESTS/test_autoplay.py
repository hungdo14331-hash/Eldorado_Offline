import json
import sys
import tempfile
import time
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import serve


class AutoplayPurchaseTest(unittest.TestCase):
    def setUp(self):
        self._old_save_file = serve.SAVE_FILE
        self._old_db_file = serve.DB_FILE
        self._tmp = tempfile.TemporaryDirectory()
        serve.SAVE_FILE = Path(self._tmp.name) / "autoplay_save.json"
        serve.DB_FILE = None
        serve.SAVE_FILE.write_text(
            json.dumps({"DATA1": "TEST,0,0", "bp": "1000"}),
            encoding="utf-8",
        )

    def tearDown(self):
        serve.SAVE_FILE = self._old_save_file
        serve.DB_FILE = self._old_db_file
        self._tmp.cleanup()

    def test_seven_day_package_costs_1000_bp_and_persists(self):
        before = int(time.time())
        status, raw = serve.offline_stub(
            "/ELDORADO_WEB/AutoPlay/set_autoplay.php",
            "HOST_ID=TEST&AUTO_DAY=7&AUTO_BP=1000",
        )
        after = int(time.time())

        self.assertEqual(200, status)
        self.assertEqual({"STATE": "SUCCESS"}, json.loads(raw))
        saved = json.loads(serve.SAVE_FILE.read_text(encoding="utf-8"))
        self.assertEqual("0", saved["bp"])
        self.assertEqual(1, saved["autoplay"]["paid"])
        self.assertEqual(1, saved["autoplay"]["on_off"])
        self.assertGreaterEqual(saved["autoplay"]["end"], before + 7 * 86400)
        self.assertLessEqual(saved["autoplay"]["end"], after + 7 * 86400)

        _, get_raw = serve.offline_stub(
            "/ELDORADO_WEB/AutoPlay/get_autoplay.php",
            "HOST_ID=TEST",
        )
        current = json.loads(get_raw)
        self.assertEqual("SUCCESS", current["STATE"])
        self.assertEqual(1, current["ON_OFF"])


if __name__ == "__main__":
    unittest.main()
