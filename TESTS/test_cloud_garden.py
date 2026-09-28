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


class CloudGardenContractTest(unittest.TestCase):
    def setUp(self):
        self._old_save_file = serve.SAVE_FILE
        self._old_db_file = serve.DB_FILE
        self._old_db_conn = serve.DB_CONN
        self._old_require_login = serve.REQUIRE_LOGIN
        self._old_uid = getattr(serve._tl, "uid", None)
        self._tmp = tempfile.TemporaryDirectory()
        serve.SAVE_FILE = Path(self._tmp.name) / "cloud_garden_save.json"
        serve.DB_FILE = None
        serve.SAVE_FILE.write_text(
            json.dumps({"DATA1": "TEST,0,1000", "USER_NAME": "TEST"}),
            encoding="utf-8",
        )

    def tearDown(self):
        if serve.DB_CONN is not self._old_db_conn and serve.DB_CONN is not None:
            serve.DB_CONN.close()
        serve.DB_CONN = self._old_db_conn
        serve.SAVE_FILE = self._old_save_file
        serve.DB_FILE = self._old_db_file
        serve.REQUIRE_LOGIN = self._old_require_login
        if self._old_uid is None:
            try:
                del serve._tl.uid
            except AttributeError:
                pass
        else:
            serve._tl.uid = self._old_uid
        self._tmp.cleanup()

    def test_ranking_get_char_ap_info_matches_both_client_consumers(self):
        status, raw = serve.offline_stub(
            "/ELDORADO_WEB/ServerSide/cloud_garden/cloud_garden_ranking.php",
            "MODE=RANKING_GET",
        )

        self.assertEqual(200, status)
        response = json.loads(raw)
        self.assertEqual("SUCCESS", response["STATE"])
        char_ap_info = response["CHAR_AP_INFO"]
        self.assertIsInstance(char_ap_info, dict)

        # Ranking UI reads char_down/char_up before it can hide the loader.
        # Gameplay later reads down/up from the same response object.
        for key in ("char_down", "char_up", "down", "up"):
            self.assertIn(key, char_ap_info)
            self.assertIsInstance(char_ap_info[key], str)

    def test_ranking_get_grants_daily_free_tickets_before_the_first_click(self):
        status, raw = serve.offline_stub(
            "/ELDORADO_WEB/cloud_garden/cloud_garden_ranking.php",
            "MODE=RANKING_GET",
        )
        self.assertEqual(200, status)
        response = json.loads(raw)
        self.assertEqual("3", response["cur_ticket"])
        saved = json.loads(serve.SAVE_FILE.read_text(encoding="utf-8"))
        self.assertEqual(time.strftime("%Y%m%d"), saved["cloud_ticket_day"])
        self.assertEqual("3", saved["cloud_ticket_left"])

    def test_paid_entry_works_after_three_free_entries(self):
        for _ in range(3):
            status, raw = serve.offline_stub(
                "/ELDORADO_WEB/cloud_garden/cloud_garden_ranking.php",
                "MODE=GAME_TICKET",
            )
            self.assertEqual(200, status)
            self.assertEqual("OK", json.loads(raw)["TYPE"])
        status, raw = serve.offline_stub(
            "/ELDORADO_WEB/cloud_garden/cloud_garden_ranking.php",
            "MODE=RANKING_GET",
        )
        self.assertEqual(200, status)
        self.assertEqual("0", json.loads(raw)["cur_ticket"])
        status, raw = serve.offline_stub(
            "/ELDORADO_WEB/cloud_garden/cloud_garden_ranking.php",
            "MODE=GAME_RUBY",
        )
        self.assertEqual(200, status)
        paid = json.loads(raw)
        self.assertEqual("SUCCESS", paid["STATE"])
        self.assertEqual("OK", paid["TYPE"])
        self.assertEqual("900", paid["after_ruby"])

    def test_ranking_window_does_not_block_match_outside_reset_period(self):
        status, raw = serve.offline_stub(
            "/ELDORADO_WEB/cloud_garden/cloud_garden_ranking.php",
            "MODE=RANKING_GET",
        )
        self.assertEqual(200, status)
        response = json.loads(raw)
        now = int(time.time())
        reset_start = int(response["RANKING_SHOW_TIMESTAMP"])
        reset_end = int(response["RANKING_PLAY_TIMESTAMP"])
        self.assertGreater(reset_start, 0)
        self.assertGreater(reset_end, reset_start)
        self.assertFalse(reset_start <= now < reset_end)

    def test_ranking_get_lists_best_scores_from_all_accounts(self):
        db_path = Path(self._tmp.name) / "cloud_garden.db"
        serve.init_db(db_path)
        serve.REQUIRE_LOGIN = False

        serve._tl.uid = "ALICE"
        serve.SAVE_FILE = Path(self._tmp.name) / "unused.json"
        serve.offline_stub(
            "/ELDORADO_WEB/cloud_garden/cloud_garden_ranking.php",
            "MODE=GAME_END&SCORE=500",
        )
        serve._tl.uid = "BOB"
        serve.offline_stub(
            "/ELDORADO_WEB/cloud_garden/cloud_garden_ranking.php",
            "MODE=GAME_END&SCORE=800",
        )

        serve._tl.uid = "ALICE"
        status, raw = serve.offline_stub(
            "/ELDORADO_WEB/cloud_garden/cloud_garden_ranking.php",
            "MODE=RANKING_GET",
        )
        self.assertEqual(200, status)
        response = json.loads(raw)
        self.assertEqual("2", response["MY_RANKING"])
        self.assertEqual("500", response["MY_SCORE"])
        self.assertEqual(
            [("BOB", "800"), ("ALICE", "500")],
            [(row["NAME"], str(row["SCORE"])) for row in response["RANKING_ARR"][1:]],
        )

    def test_ranking_array_has_client_placeholder_at_index_zero(self):
        serve.offline_stub(
            "/ELDORADO_WEB/cloud_garden/cloud_garden_ranking.php",
            "MODE=GAME_END&SCORE=321",
        )
        status, raw = serve.offline_stub(
            "/ELDORADO_WEB/cloud_garden/cloud_garden_ranking.php",
            "MODE=RANKING_GET",
        )
        self.assertEqual(200, status)
        ranking = json.loads(raw)["RANKING_ARR"]
        self.assertEqual(2, len(ranking))
        self.assertEqual(0, ranking[0]["RANKING"])
        self.assertEqual("", ranking[0]["NAME"])
        self.assertEqual("321", str(ranking[1]["SCORE"]))


if __name__ == "__main__":
    unittest.main()
