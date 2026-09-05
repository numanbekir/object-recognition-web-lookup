# Numan Bekir Özçelik - 04.09.2026
"""Fonksiyonlar için birim testleri"""

import tempfile
import unittest

from app.image_loader import ImageLoader, ImageLoadError
from main import (classify_input, clean_input, is_single_source,
                  is_unsupported_file, normalize_schemeless)


class CleanInputTest(unittest.TestCase):
    def test_strips_whitespace_and_quotes(self):
        # sürükle-bırak ile gelen tırnaklı yol temizlenmeli
        self.assertEqual(clean_input("  '/tmp/foto çanta.jpg'  "), "/tmp/foto çanta.jpg")
        self.assertEqual(clean_input('"deneme"'), "deneme")

    def test_keeps_inner_quotes(self):
        # metnin içindeki tırnaklara dokunulmamalı
        self.assertEqual(clean_input("cantanin 'ozel' modeli"), "cantanin 'ozel' modeli")


class ClassifyInputTest(unittest.TestCase):
    def test_empty_and_quit(self):
        # boş girdi tur harcamadan yeniden sorulur, çıkış kelimeleri büyük/küçük harf tanımaz
        self.assertEqual(classify_input("   ")[0], "empty")
        self.assertEqual(classify_input("q")[0], "quit")
        self.assertEqual(classify_input("EXIT")[0], "quit")

    def test_http_url(self):
        # url değiştirilmeden indirme dalına gitmeli
        kind, value = classify_input("https://ornek.com/foto.jpg")
        self.assertEqual(kind, "url")
        self.assertEqual(value, "https://ornek.com/foto.jpg")

    def test_rejects_unsupported_scheme(self):
        # yalnızca http/https kabul edilir
        self.assertEqual(classify_input("ftp://ornek.com/foto.jpg")[0], "bad_scheme")
        self.assertEqual(classify_input("data:image/png;base64,AAAA")[0], "bad_scheme")

    def test_existing_file(self):
        # diskte gerçekten var olan dosya path sayılır, uzantıya bakılmaz
        with tempfile.NamedTemporaryFile(suffix=".jpg") as f:
            kind, value = classify_input(f.name)
            self.assertEqual(kind, "path")
            self.assertEqual(value, f.name)

    def test_file_scheme_becomes_local_path(self):
        # bazı terminaller sürüklenen dosyayı file:// önekiyle verir
        with tempfile.NamedTemporaryFile(suffix=".png") as f:
            kind, value = classify_input(f"file://{f.name}")
            self.assertEqual(kind, "path")

    def test_backslash_escaped_path(self):
        # bazı terminaller sürüklenen yolu "foto\ 1.jpg" gibi kaçışlar
        import os
        import tempfile
        with tempfile.TemporaryDirectory() as folder:
            real = os.path.join(folder, "foto 1.jpg")
            open(real, "w").close()
            escaped = real.replace(" ", "\\ ")
            kind, value = classify_input(escaped)
            self.assertEqual(kind, "path")
            self.assertEqual(value, real)

    def test_missing_image_file_is_not_text(self):
        # yanlış yazılmış dosya yolu aramaya gitmemeli
        self.assertEqual(classify_input("./yok/boyle/foto.jpg")[0], "missing_file")

    def test_plain_text(self):
        # url veya dosya olmayan girdi rafine arama metnidir
        self.assertEqual(classify_input("fiyatları ne kadar")[0], "text")

    def test_input_length_limit(self):
        # aşırı uzun girdi hiç işlenmeden reddedilir
        self.assertEqual(classify_input("a" * 5000)[0], "too_long")

    def test_long_word_does_not_crash(self):
        # 255+ karakterlik kelime dosya yoklamasında OSError fırlatmamalı
        long_text = "x" * 300 + " deneme " + "y" * 300
        self.assertEqual(classify_input(long_text)[0], "text")
        self.assertFalse(is_unsupported_file(long_text))


class SchemelessUrlTest(unittest.TestCase):
    def test_www_prefix_becomes_url(self):
        kind, value = classify_input("www.testimage.com/image")
        self.assertEqual(kind, "url")
        self.assertEqual(value, "https://www.testimage.com/image")

    def test_domain_with_path_becomes_url(self):
        self.assertEqual(classify_input("testimage.com/image")[0], "url")

    def test_bare_domain_known_tld(self):
        self.assertEqual(classify_input("testimage.com")[0], "url")

    def test_local_filename_is_not_url(self):
        # foto.jpg alan adına benzese de görsel dosyasıdır
        self.assertEqual(classify_input("./yok/foto.jpg")[0], "missing_file")

    def test_dotted_word_is_text(self):
        self.assertEqual(normalize_schemeless("geldi.mi"), None)


class MultiSourceTest(unittest.TestCase):
    def test_two_urls_rejected(self):
        self.assertEqual(classify_input("https://a.com/bir.jpg https://b.com/iki.png")[0], "multi")

    def test_two_quoted_files_rejected(self):
        # tırnaklı çift yol da çoklu sayılmalı (shlex tırnak-güvenli)
        with tempfile.NamedTemporaryFile(suffix=".jpg") as f1, \
                tempfile.NamedTemporaryFile(suffix=".png") as f2:
            self.assertEqual(classify_input(f"'{f1.name}' '{f2.name}'")[0], "multi")

    def test_spaced_missing_path_is_not_multi(self):
        # boşluklu tek dosya adı yanlışlıkla çoklu sayılmamalı
        self.assertEqual(classify_input("./foto bir.jpg")[0], "missing_file")


class SourceToolsTest(unittest.TestCase):
    def test_single_source(self):
        self.assertTrue(is_single_source("https://a.com/foto.jpg"))
        self.assertTrue(is_single_source("foto.jpg"))
        self.assertFalse(is_single_source("fiyatları ne kadar"))
        self.assertFalse(is_single_source("a.jpg b.jpg"))

    def test_unsupported_file(self):
        # var olan görsel-dışı dosya girişte reddedilir, görsel ve olmayan dosya edilmez
        with tempfile.NamedTemporaryFile(suffix=".txt") as txt:
            self.assertTrue(is_unsupported_file(txt.name))
        with tempfile.NamedTemporaryFile(suffix=".jpg") as jpg:
            self.assertFalse(is_unsupported_file(jpg.name))
        self.assertFalse(is_unsupported_file("./yok/dosya.txt"))
        self.assertFalse(is_unsupported_file("fiyatları ne kadar"))


class ImageLoaderTest(unittest.TestCase):
    def test_svg_is_rejected_with_clear_message(self):
        # vektörel format bilinçli desteklenmiyor, mesaj bunu söylemeli
        with self.assertRaises(ImageLoadError) as ctx:
            ImageLoader().load("/tmp/logo.svg", "path")
        self.assertIn("vektörel", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()

