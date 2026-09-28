import json
import sys
import tempfile
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import serve


class FourGodsPersuasionCostTest(unittest.TestCase):
    def setUp(self):
        self._old_save_file = serve.SAVE_FILE
        self._old_db_file = serve.DB_FILE
        self._tmp = tempfile.TemporaryDirectory()
        serve.SAVE_FILE = Path(self._tmp.name) / "four_gods_save.json"
        serve.DB_FILE = None
        serve.SAVE_FILE.write_text(
            json.dumps({
                "DATA1": "TEST,0,0",
                "USER_NAME": "TEST",
                "cloud_piece": "100",
            }),
            encoding="utf-8",
        )

    def tearDown(self):
        serve.SAVE_FILE = self._old_save_file
        serve.DB_FILE = self._old_db_file
        self._tmp.cleanup()

    def test_boot_and_all_four_gods_use_20_cloud_pieces(self):
        _, boot_raw = serve.offline_stub(
            "/ELDORADO_WEB/cnm_exist_host_in_server.php",
            "HOST_ID=TEST",
        )
        self.assertEqual("20", json.loads(boot_raw).get("DRAGON_NEED_CLOUD"))

        expected_cloud = ["80", "60", "40", "20"]
        for god_type, remaining in zip((1, 2, 3, 4), expected_cloud):
            _, raw = serve.offline_stub(
                "/ELDORADO_WEB/temple/update_dragon_info.php",
                f"MODE=UPDATE&TYPE={god_type}&GAGE=0&EVENT=yes&CLOUD=999999",
            )
            response = json.loads(raw)
            self.assertEqual("FAIL", response["STATE"])
            self.assertEqual(remaining, response["CLOUD"])

        saved = json.loads(serve.SAVE_FILE.read_text(encoding="utf-8"))
        self.assertEqual("20", saved["cloud_piece"])
        self.assertEqual(
            {"95": 1, "101": 1, "102": 1, "103": 1},
            saved["temple_gauge"],
        )

    def test_insufficient_cloud_does_not_advance_or_spend(self):
        save = json.loads(serve.SAVE_FILE.read_text(encoding="utf-8"))
        save["cloud_piece"] = "19"
        serve.SAVE_FILE.write_text(json.dumps(save), encoding="utf-8")

        _, raw = serve.offline_stub(
            "/ELDORADO_WEB/temple/update_dragon_info.php",
            "MODE=UPDATE&TYPE=1&GAGE=0&EVENT=yes&CLOUD=999999",
        )

        response = json.loads(raw)
        self.assertEqual("NOTICE", response["STATE"])
        self.assertEqual("19", response["CLOUD"])
        saved = json.loads(serve.SAVE_FILE.read_text(encoding="utf-8"))
        self.assertEqual("19", saved["cloud_piece"])
        self.assertNotIn("temple_gauge", saved)


if __name__ == "__main__":
    unittest.main()
