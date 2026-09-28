#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Regression: asset anh thieu phai tra PNG hop le, khong phai 404.

Client dem anh bang `img.onload` (LOIMG_CHAR_OUR_NUM.<AC>.cur++, LOIMG_ETC_OUR).
Anh 404 chi bat `onerror` nen `cur` khong bao gio du `tot`, ham
`interval_test_our` tu hien lai moi 100ms vo han, `flag_LOIMG_CHAR_OUR` keo
0 va `S_GAME` khong bao gio chay -> dung may giua tran. Trai lai va vao
chay lai duoc vi luc do asset da vao browser cache.

Sua o server: anh thieu -> 200 + PNG 1x1 giai duoc => `onload` bat, game
chay tiep, chi khong ve ra frame do. Asset khong phai anh van phai 404 de
loi that con lo.
"""
import struct
import unittest
import zlib
from http.server import ThreadingHTTPServer
from urllib.error import HTTPError
from urllib.request import urlopen

import serve


def _walk_png_chunks(blob):
    assert blob[:8] == b"\x89PNG\r\n\x1a\n", "bad PNG signature"
    off, chunks = 8, []
    while off < len(blob):
        (length,) = struct.unpack(">I", blob[off:off + 4])
        kind = blob[off + 4:off + 8]
        data = blob[off + 8:off + 8 + length]
        (crc,) = struct.unpack(">I", blob[off + 8 + length:off + 12 + length])
        assert zlib.crc32(kind + data) & 0xFFFFFFFF == crc, "CRC fail in %r" % kind
        chunks.append((kind, data))
        off += 12 + length
    return chunks


class PlaceholderPngTests(unittest.TestCase):
    def test_placeholder_is_a_decodable_png(self):
        # Bytes sai -> browser bat onerror -> bug dong treo quay lai.
        chunks = _walk_png_chunks(serve.BLANK_PNG)
        self.assertEqual(chunks[0][0], b"IHDR")
        self.assertEqual(chunks[-1][0], b"IEND")
        width, height, depth, colour = struct.unpack(">IIBB", chunks[0][1][:10])
        self.assertEqual((width, height), (1, 1))
        self.assertEqual(depth, 8)
        self.assertEqual(colour, 6)  # RGBA

    def test_placeholder_pixel_is_fully_transparent(self):
        # Mot PNG 1x1 mau xanh/opacity se bi dan thanh mot mau xanh dai
        # khi ve len canvas -> phai trong suot that, khong phai "1x1 hop le".
        idat = b"".join(d for k, d in _walk_png_chunks(serve.BLANK_PNG)
                        if k == b"IDAT")
        raw = zlib.decompress(idat)
        self.assertEqual(raw, b"\x00" + b"\x00\x00\x00\x00",
                         "scanline phai la filter 0 + RGBA(0,0,0,0)")
        _px_r, _px_g, _px_b, px_a = raw[1], raw[2], raw[3], raw[4]
        self.assertEqual(px_a, 0, "alpha phai bang 0 de frame khong bi ve")

    def test_image_ext_stays_inside_static_ext(self):
        # Nhanh placeholder chi chay khi suffix nam trong STATIC_EXT; neu
        # IMAGE_EXT loai ra phan tu STATIC_EXT thi nhanh do khong bao gio chay.
        self.assertTrue(serve.IMAGE_EXT)
        self.assertFalse(serve.IMAGE_EXT - serve.STATIC_EXT)

    def test_every_image_ext_has_a_content_type(self):
        for ext in serve.IMAGE_EXT:
            self.assertTrue(serve.guess_ct("a" + ext).startswith("image/"),
                            "guess_ct sai cho %s" % ext)


class MissingAssetHttpTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # fetch_and_cache -> None: giu test offline, khong goi live host.
        cls._real_fetch = serve.fetch_and_cache
        serve.fetch_and_cache = lambda rel_path: None
        cls.srv = ThreadingHTTPServer(("127.0.0.1", 0), serve.Handler)
        cls.srv.daemon_threads = True
        cls.base = "http://127.0.0.1:%d" % cls.srv.server_address[1]
        cls.thread = __import__("threading").Thread(
            target=cls.srv.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.srv.shutdown()
        cls.srv.server_close()
        serve.fetch_and_cache = cls._real_fetch

    def _get(self, path):
        try:
            with urlopen(self.base + path, timeout=10) as r:
                return r.status, dict(r.headers), r.read()
        except HTTPError as e:
            e.close()
            return e.code, dict(e.headers), b""

    def test_missing_image_returns_200_png(self):
        status, headers, body = self._get("/image/char/__khong_ton_tai_1.png")
        self.assertEqual(status, 200)
        self.assertEqual(headers.get("Content-Type"), "image/png")
        self.assertEqual(body, serve.BLANK_PNG)
        _walk_png_chunks(body)  # browser phai decode duoc

    def test_missing_image_never_404s(self):
        for path in ("/image/a.jpg", "/image/b.jpeg", "/image/c.gif",
                     "/image/d.webp", "/image/e.bmp", "/image/f.ico",
                     "/image/g.svg"):
            status, headers, body = self._get(path)
            self.assertEqual(status, 200, path)
            self.assertEqual(body, serve.BLANK_PNG, path)

    def test_missing_code_still_404s(self):
        # Khong giu loi that: script/style/font thieu van phai bao loi.
        for path in ("/__khong_ton_tai_1.js", "/__khong_ton_tai_2.css",
                     "/__khong_ton_tai_3.woff2"):
            status, _, _ = self._get(path)
            self.assertEqual(status, 404, path)

    def test_alias_serves_real_art_instead_of_placeholder(self):
        # boss_img1.png (World Boss) khong ton tai o ban goc: 404 tren host
        # goc va o moi ban sao local. Serve.py redirect sang boss_img2.png de
        # man xep hang boss co hinh thay vi mot cho trong. Phai chay tren ca
        # hai goc asset vi client co the yeu cau bat ky goc nao.
        for root in ("ELDORADO_WEB/source_20240722", "ELDORADO_WEB"):
            rel = "/%s/image/ui/21_boss/boss_img1.png" % root
            want = (serve.BASE_DIR / rel.replace("boss_img1.png", "boss_img2.png")
                    .lstrip("/")).read_bytes()
            status, headers, body = self._get(rel)
            self.assertEqual(status, 200, rel)
            self.assertEqual(headers.get("Content-Type"), "image/png", rel)
            self.assertEqual(body, want, "alias phai tra dung file anh that: " + rel)
            self.assertNotEqual(body, serve.BLANK_PNG,
                                "khong duoc rut ve placeholder: " + rel)
            width, height = struct.unpack(">II", _walk_png_chunks(body)[0][1][:8])
            self.assertGreater(max(width, height), 1,
                               "anh 1x1 la placeholder, khong phai art that: " + rel)

    def test_every_alias_target_exists_on_disk(self):
        # Sai chinh ta trong ASSET_ALIAS se lam nhanh MISS chay im lang ->
        # anh placeholder ma khong ai bao loi. Khoa invariant nay lai.
        for target in serve.ASSET_ALIAS.values():
            path = (serve.BASE_DIR / "ELDORADO_WEB" / "source_20240722"
                    / target.lstrip("/"))
            self.assertTrue(path.is_file(),
                            "ASSET_ALIAS tro toi file khong ton tai: %s" % target)


if __name__ == "__main__":
    unittest.main()
