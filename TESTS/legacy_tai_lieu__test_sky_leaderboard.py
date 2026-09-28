import json
import sys
import tempfile
import unittest

from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import serve


class SkyLeaderboardTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self.tmp.close()
        serve.init_db(self.tmp.name)

    def tearDown(self):
        if serve.DB_CONN:
            serve.DB_CONN.close()
            serve.DB_CONN = None
            serve.DB_FILE = None

    def test_shared_best_score_persists_and_nonce_is_single_use(self):
        serve._tl.uid = "alice"
        serve.sky_record_start("alice", "nonce-a")
        self.assertTrue(serve.sky_record_result("alice", "nonce-a", 12, "W"))
        self.assertFalse(serve.sky_record_result("alice", "nonce-a", 99, "W"))

        serve._tl.uid = "bob"
        serve.sky_record_start("bob", "nonce-b")
        self.assertTrue(serve.sky_record_result("bob", "nonce-b", 25, "W"))

        rows = serve.sky_ranking()
        self.assertEqual([r["clear_wave"] for r in rows], [25, 12])
        self.assertEqual([r["user_id"] for r in rows], ["bob", "alice"])


if __name__ == "__main__":
    unittest.main()
