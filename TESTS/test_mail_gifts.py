import importlib
import shutil
import sqlite3
import tempfile
import time
import unittest
from pathlib import Path


serve = importlib.import_module("serve")


class MailGiftValueTests(unittest.TestCase):
    def test_daily_mail_amounts(self):
        self.assertEqual(
            (("GOLD", "100000"), ("RUBY", "250"), ("BP", "50")),
            serve.MAILBOX_GIFTS,
        )

    def test_gift_mult_knob_is_gone(self):
        # The old --gift-mult scaled the daily mail and nothing else, so it was
        # removed instead of left as a flag that silently does nothing.
        self.assertFalse(hasattr(serve, "GIFT_MULT"))


class MailGiftPostingTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp()) / "gift.db"
        shutil.copy(Path(serve.BASE_DIR) / "busidol.db", self.tmp)
        self._conn, self._file = serve.DB_CONN, serve.DB_FILE
        serve.DB_CONN = sqlite3.connect(self.tmp, check_same_thread=False)
        serve.DB_FILE = self.tmp
        serve._tl.uid = "HUANDO"
        self.assertIsNotNone(serve.db_load_save("HUANDO"))

    def tearDown(self):
        serve.DB_CONN, serve.DB_FILE = self._conn, self._file

    def _posted_daily_mail(self):
        save = serve.load_save()
        save["last_gift_date"] = ""          # force a fresh daily post
        mails = serve.mailbox_ensure_daily_mail(save)
        # Daily mails carry no "why" (the handler supplies "DAILY GIFT" when it
        # renders them); they are identified by the YYYYMMDD+index SN.
        wanted = {str(time.strftime("%Y%m%d")) + str(i)
                  for i in range(1, len(serve.MAILBOX_GIFTS) + 1)}
        return {(m["what"], m["what_value"]) for m in mails if str(m["sn"]) in wanted}

    def test_daily_mail_posts_the_table_unscaled(self):
        self.assertEqual(
            {("GOLD", "100000"), ("RUBY", "250"), ("BP", "50")},
            self._posted_daily_mail(),
        )

    def test_daily_mail_sn_is_numeric(self):
        # get_reward2_mailbox parses SN with parseInt(), so it must stay numeric.
        save = serve.load_save()
        save["last_gift_date"] = ""
        for mail in serve.mailbox_ensure_daily_mail(save):
            if str(mail["sn"]) in {str(time.strftime("%Y%m%d")) + str(i)
                                   for i in range(1, len(serve.MAILBOX_GIFTS) + 1)}:
                self.assertTrue(str(mail["sn"]).isdigit(), mail["sn"])


class OfflineGiftValueTests(unittest.TestCase):
    def test_offline_gift_amounts(self):
        tmp = Path(tempfile.mkdtemp()) / "og.db"
        shutil.copy(Path(serve.BASE_DIR) / "busidol.db", tmp)
        conn, file = serve.DB_CONN, serve.DB_FILE
        serve.DB_CONN = sqlite3.connect(tmp, check_same_thread=False)
        serve.DB_FILE = tmp
        serve._tl.uid = "HUANDO"
        try:
            save = serve.load_save()
            save["offline_gift_sent"] = ""    # force a re-seed
            mails = serve.mailbox_ensure_offline_gift(save)
        finally:
            serve.DB_CONN, serve.DB_FILE = conn, file

        amounts = {(m["what"], m["what_value"]) for m in mails
                   if m.get("why") == "OFFLINE GIFT"}
        self.assertEqual(
            {("GOLD", "100000"), ("RUBY", "250"), ("BP", "50")},
            amounts,
        )

    def test_offline_gift_keeps_only_the_lowest_character(self):
        # 97 and 99 were removed at the user's request; 96 stays.
        tmp = Path(tempfile.mkdtemp()) / "og2.db"
        shutil.copy(Path(serve.BASE_DIR) / "busidol.db", tmp)
        conn, file = serve.DB_CONN, serve.DB_FILE
        serve.DB_CONN = sqlite3.connect(tmp, check_same_thread=False)
        serve.DB_FILE = tmp
        serve._tl.uid = "HUANDO"
        try:
            save = serve.load_save()
            save["offline_gift_sent"] = ""
            mails = serve.mailbox_ensure_offline_gift(save)
        finally:
            serve.DB_CONN, serve.DB_FILE = conn, file

        chars = {m["what_value"] for m in mails if m["what"] == "CHAR"}
        self.assertEqual({"96"}, chars)
        self.assertEqual((96,), serve.OFFLINE_GIFT_CHARS)


if __name__ == "__main__":
    unittest.main()
