#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Regression: _eldorado_lang_of — lay LANG code tu DATA1[3].

Không hardcode `2` (English) nữa trong payload xep hang Sky: client doc
ngon ngu tu DATA1[3], nen bang xep hang phai bao veo dung ma do.
"""
import unittest

import serve


class EldoradoLangOfTests(unittest.TestCase):
    def test_reads_vietnamese_from_index_3(self):
        d1 = "huando,25500000,5500,3,KR,1,2"
        self.assertEqual(serve._eldorado_lang_of(d1.split(",")), 3)

    def test_reads_english_when_saved_as_english(self):
        d1 = "huando,25500000,5500,2,KR,1,2"
        self.assertEqual(serve._eldorado_lang_of(d1.split(",")), 2)

    def test_preserves_other_languages(self):
        for code in (1, 4, 5, 6):
            d1 = "n,g,r,%d,KR,1,2" % code
            self.assertEqual(serve._eldorado_lang_of(d1.split(",")), code)

    def test_missing_index_falls_back_to_vietnamese(self):
        self.assertEqual(serve._eldorado_lang_of([]), 3)
        self.assertEqual(serve._eldorado_lang_of(["n", "g"]), 3)

    def test_garbage_falls_back_to_vietnamese(self):
        self.assertEqual(serve._eldorado_lang_of(["n", "g", "r", "abc"]), 3)
        self.assertEqual(serve._eldorado_lang_of(["n", "g", "r", ""]), 3)
        self.assertEqual(serve._eldorado_lang_of(["n", "g", "r", "-4"]), 3)
        self.assertEqual(serve._eldorado_lang_of(["n", "g", "r", "99"]), 3)


if __name__ == "__main__":
    unittest.main()
