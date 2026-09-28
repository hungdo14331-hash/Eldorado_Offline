"""Client-side asset guards. The minified client is a build artefact we patch by
hand, so these tests exist to catch a bad splice and a silently restored filter.

`S_GUILD_CHAT_KEYBOARD.check_not_allowed` shipped an ~18 KB profanity list and
substring-matched chat against it, refusing to send. Removed 28/09/2026 at the
user's request; the server has never had a word check, so this function was the
only gate. It is the single choke point for both input paths that can block: the
on-screen keyboard OK button (`input_ch`) and the native keyboard
(`open_chat_input`). `chat_input_result` skips it and goes straight to
`send_chat`, so it never blocked anything.
"""
import shutil
import subprocess
import unittest
from pathlib import Path

CLIENT_JS = (Path(__file__).resolve().parent.parent / "ELDORADO_WEB"
             / "javascript_min" / "eldorado_all_20260915.min.js")
PROFANITY_MARKERS = ("bastardized", "sh!t", "c*nt", "motherfuckers")


class GuildChatFilterRemovedTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.src = CLIENT_JS.read_text(encoding="utf-8")

    def test_check_not_allowed_never_blocks(self):
        body = 'S_GUILD_CHAT_KEYBOARD.check_not_allowed=function(n){return!1}'
        self.assertIn(body, self.src, "ham filter chat da quay lai")

    def test_profanity_list_is_gone(self):
        for marker in PROFANITY_MARKERS:
            self.assertNotIn(marker, self.src, marker)

    def test_call_sites_are_intact(self):
        """The gate is neutralised, not deleted: both input paths still call it,
        so a later upstream patch cannot silently re-add the check."""
        self.assertEqual(2, self.src.count("check_not_allowed("),
                         "so lai 2 noi goi (input_ch, open_chat_input)")

    def test_client_js_still_parses(self):
        node = shutil.which("node")
        if node is None:
            self.skipTest("node khong co san")
        proc = subprocess.run([node, "--check", str(CLIENT_JS)],
                              capture_output=True, text=True)
        self.assertEqual(0, proc.returncode, proc.stderr)


if __name__ == "__main__":
    unittest.main()
