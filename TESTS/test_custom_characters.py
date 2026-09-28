import importlib.util
import json
import shutil
import subprocess
import sys
import unittest
from pathlib import Path

import admin_control_backend
import serve


ROOT = Path(__file__).resolve().parent.parent
BUILDER = ROOT / "character_workshop" / "build_characters.py"
CONFIG_DIR = ROOT / "character_workshop" / "characters"
GENERATED = ROOT / "ELDORADO_WEB" / "custom_characters" / "custom_characters.generated.js"
RUNTIME = ROOT / "ELDORADO_WEB" / "custom_characters" / "custom_character_runtime.js"


def load_builder():
    spec = importlib.util.spec_from_file_location("build_characters", BUILDER)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class CustomCharacterTests(unittest.TestCase):
    def test_sample_character_build_is_reproducible_and_assets_are_complete(self):
        result = subprocess.run(
            [sys.executable, str(BUILDER), "--check"],
            cwd=ROOT,
            capture_output=True,
            text=True,
        )
        self.assertEqual(0, result.returncode, result.stdout + result.stderr)
        self.assertIn("ASTRA (115)", result.stdout)

        before = GENERATED.read_bytes()
        build = subprocess.run(
            [sys.executable, str(BUILDER)],
            cwd=ROOT,
            capture_output=True,
            text=True,
        )
        self.assertEqual(0, build.returncode, build.stdout + build.stderr)
        self.assertEqual(before, GENERATED.read_bytes(),
                         "build lai cung config phai cho ket qua byte-for-byte")

    def test_unknown_skill_and_duplicate_id_are_rejected(self):
        builder = load_builder()
        base = {
            "id": 115,
            "name": "TEST",
            "filename": "ally_115",
            "star": 6,
            "feature": "ATTACK",
            "attackType": "SINGLE",
            "size": {"width": 2, "height": 2},
            "fireSize": {"width": 2, "height": 2},
            "frames": {"wait": 1, "move": 1, "attack": 1, "beattack": 1, "fire": 1},
            "combat": {"attackFireFrame": 1, "attackLength": 100,
                       "moveSpeed": 4, "attackSpeed": 30},
            "stats": {"apStart": 1, "apEnd": 2, "hpStart": 3, "hpEnd": 4,
                      "mineralStart": 5, "mineralEnd": 6, "maxLevel": 20},
            "layout": {"centerX": 1, "centerY": 1, "gagebarX": 0, "gagebarY": 0},
            "specialAbilities": ["DOES_NOT_EXIST"],
            "skillParameters": {},
        }
        with self.assertRaisesRegex(ValueError, "DOES_NOT_EXIST"):
            builder.validate_configs([base])

        base["specialAbilities"] = []
        with self.assertRaisesRegex(ValueError, "trung ID 115"):
            builder.validate_configs([base, dict(base)])

    def test_runtime_registers_stats_collection_and_builtin_skill(self):
        node = shutil.which("node")
        if node is None:
            self.skipTest("node khong co san")
        harness = r"""
const fs = require('fs');
const vm = require('vm');
const context = {
  console,
  FEATURE: { ATTACK: 4 },
  ATTACK_TYPE: { SINGLE: 'SINGLE' },
  SPECIAL_ABILITY: { PUSH: 'PUSH' },
  INNATE_ABILITY: {},
  CHAR_OUR_TEAM: [{}],
  MAX_OUR_TEAM_NUM: 114,
  CHARBOOK_CHAR_MAX_NUM: 14,
  TXT: {},
  LANG: { init() { return 'ok'; } },
  g: { CHAR_NUM: [[], [0, 1]], STAR: [[], [], [], [], [], [], [0, 1]] },
};
context.window = context;
vm.createContext(context);
for (const file of process.argv.slice(1)) {
  vm.runInContext(fs.readFileSync(file, 'utf8'), context, { filename: file });
}
context.LANG.init();
const c = context.CHAR_OUR_TEAM[115];
if (!c || c.name !== 'ASTRA') throw new Error('missing ASTRA');
if (c.ap_start !== 220 || c.hp_end !== 18000) throw new Error('wrong stats');
if (c.special_ability[0] !== 'PUSH' || c.push_per !== 30) throw new Error('wrong skill');
if (context.MAX_OUR_TEAM_NUM !== 115) throw new Error('max id not extended');
if (!context.g.CHAR_NUM.some(group => group.includes(115))) throw new Error('collection missing 115');
if (context.TXT.char_name_115 !== 'ASTRA') throw new Error('language name missing');
console.log('custom character runtime: PASS');
"""
        result = subprocess.run(
            [node, "-e", harness, str(GENERATED), str(RUNTIME)],
            cwd=ROOT,
            capture_output=True,
            text=True,
        )
        self.assertEqual(0, result.returncode, result.stdout + result.stderr)
        self.assertIn("PASS", result.stdout)

    def test_boot_manifest_loads_custom_characters_after_core_bundle(self):
        status, manifest = serve.offline_stub("/ELDORADO_WEB/get_app_file.php", "")
        self.assertEqual(200, status)
        urls = manifest.split("|")
        core_index = next(i for i, url in enumerate(urls)
                          if "eldorado_all_20260915.min.js" in url)
        config_index = next(i for i, url in enumerate(urls)
                            if "custom_characters.generated.js" in url)
        runtime_index = next(i for i, url in enumerate(urls)
                             if "custom_character_runtime.js" in url)
        self.assertLess(core_index, config_index)
        self.assertLess(config_index, runtime_index)

    def test_admin_can_deliver_the_custom_character(self):
        self.assertIn(115, admin_control_backend.VALID_CHARACTER_IDS)


if __name__ == "__main__":
    unittest.main()
