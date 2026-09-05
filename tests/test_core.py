# Numan Bekir Özçelik - 04.09.2026
"""Fonksiyonlar için birim testleri"""

import tempfile
import unittest

from app.image_loader import ImageLoader, ImageLoadError
from main import classify_input, clean_input


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


class ImageLoaderTest(unittest.TestCase):
    def test_svg_is_rejected_with_clear_message(self):
        # vektörel format bilinçli desteklenmiyor, mesaj bunu söylemeli
        with self.assertRaises(ImageLoadError) as ctx:
            ImageLoader().load("/tmp/logo.svg", "path")
        self.assertIn("vektörel", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()

