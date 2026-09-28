import importlib
import unittest


serve = importlib.import_module("serve")


class HardModeParseTests(unittest.TestCase):
    def test_parses_stage_and_jewels(self):
        self.assertEqual(
            (7, "1,1,1,1,1,1,1,1,1,1"),
            serve._eldorado_hard_parse("7||1,1,1,1,1,1,1,1,1,1"),
        )

    def test_missing_or_junk_falls_back_to_zero(self):
        for bad in ("", "201", "junk", "||", "x||1,2"):
            self.assertEqual(0, serve._eldorado_hard_parse(bad)[0], bad)

    def test_stage_201_is_full_unlock_not_a_seed_value(self):
        # 200 hard stages, so 201 means "everything open" and must only ever
        # appear after 200 real clears -- never as a fresh-save seed.
        self.assertEqual(201, serve.ELDORADO_HARD_ALL_OPEN)
        self.assertEqual(1, serve.ELDORADO_HARD_FIRST_STAGE)

    def test_default_jewels_have_ten_slots(self):
        self.assertEqual(10, len(serve.ELDORADO_HARD_JEWEL_DEFAULT.split(",")))


class HardModeProgressionTests(unittest.TestCase):
    def claim(self, saved, claimed):
        return serve._eldorado_hard_apply_claim(saved, claimed)

    def test_clearing_next_stage_advances_one(self):
        self.assertEqual((2, True), self.claim(1, 2))
        self.assertEqual((6, True), self.claim(5, 6))

    def test_replaying_cleared_stage_keeps_progress(self):
        self.assertEqual((5, True), self.claim(5, 5))
        self.assertEqual((5, True), self.claim(5, 3))
        self.assertEqual((5, True), self.claim(5, 1))

    def test_forged_jump_is_rejected_and_writes_nothing(self):
        # accepted=False is what makes the caller skip the save entirely, so a
        # forged POST cannot clobber the jewel list either.
        for saved, forged in ((1, 201), (1, 50), (1, 999), (5, 100)):
            self.assertEqual((saved, False), self.claim(saved, forged), (saved, forged))

    def test_progression_cannot_skip_ahead_by_repeated_posts(self):
        stage = 1
        for _ in range(3):
            stage, _accepted = self.claim(stage, 201)
        self.assertEqual(1, stage)

    def test_absurd_and_negative_inputs_are_clamped(self):
        self.assertEqual((1, True), self.claim(1, -5))
        self.assertEqual((201, True), self.claim(200, 5000))

    def test_full_playthrough_of_200_stages_still_reaches_201(self):
        # The clamp must not block legitimate progression at the end of the map.
        stage = 1
        for _ in range(200):
            stage, accepted = self.claim(stage, stage + 1)
            self.assertTrue(accepted)
        self.assertEqual(201, stage)

    def test_corrupt_saved_stage_is_treated_as_first_stage(self):
        self.assertEqual((2, True), self.claim(0, 2))
        self.assertEqual((1, True), self.claim(0, 1))

    def test_stored_stage_is_forced_into_valid_range(self):
        self.assertEqual(1, serve._eldorado_hard_clamp_progress(0))
        self.assertEqual(1, serve._eldorado_hard_clamp_progress(-40))
        self.assertEqual(201, serve._eldorado_hard_clamp_progress(99999))


if __name__ == "__main__":
    unittest.main()
