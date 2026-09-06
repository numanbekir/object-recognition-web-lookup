# Numan Bekir Özçelik - 04.09.2026
"""Fonksiyonlar için birim testleri"""

import tempfile
import unittest

from app import config
from app.image_loader import ImageLoader, ImageLoadError
from app.keywords import KeywordExtractor
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


class KeywordExtractorTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.extractor = KeywordExtractor()
        cls.extractor.load()

    def extract(self, label, secondary=()):
        return self.extractor.extract(label, list(secondary), use_suggestions=False)

    def test_turkish_name_with_fallback(self):
        self.assertEqual(self.extractor.turkish_name("bus"), "otobüs")
        # haritada olmayan etiket olduğu gibi döner, sorgu boş kalmaz
        self.assertEqual(self.extractor.turkish_name("bilinmeyen"), "bilinmeyen")

    def test_category_and_ingredient_sources(self):
        # sandviç: üst kavramdan kategori, meronym ilişkisinden bileşen gelir
        words = self.extract("sandwich")
        self.assertIn("aperatif yemek", words)
        self.assertIn("ekmek", words)
        self.assertLessEqual(len(words), config.MAX_KEYWORDS)

    def test_secondary_object_adds_scene_theme(self):
        words = self.extract("bus", ["person"])
        self.assertIn("toplu taşıma", words)
        self.assertIn("insan", words)

    def test_no_duplicates_and_cap(self):
        words = self.extract("apple", ["banana", "orange", "guitar", "dog"])
        self.assertEqual(len(words), len(set(words)))
        self.assertLessEqual(len(words), config.MAX_KEYWORDS)

    def test_sense_selection_skips_nonphysical_meanings(self):
        # dalmatian: ilk anlam Dalmaçyalı insan; alan filtresi köpeğe düşürmeli
        self.assertIn("köpek", self.extract("dalmatian"))
        # date: takvim anlamı atlanır, meyve anlamı seçilir
        self.assertIn("meyve", self.extract("date"))
        # mouse: hayvan anlamı; aygıt temaları karışmamalı
        words = self.extract("mouse")
        self.assertIn("hayvan", words)
        self.assertNotIn("teknoloji", words)

    def test_scoring_drops_distant_leaks(self):
        # wheeled_vehicle -> container kenarından sızan uzak tema elenmeli
        self.assertNotIn("ev eşyası", self.extract("ambulance"))

    def test_meronym_requires_sense_match(self):
        # gaydanın "drone" parçası uçan cihaz çevirisine düşmemeli
        self.assertNotIn("drone", self.extract("bagpipe"))
        # balonun "envelope" gövdesi mektup zarfı çevirisine düşmemeli
        self.assertNotIn("zarf", self.extract("balloon"))

    def test_suggestion_keywords_filtered_and_labeled(self):
        extractor = KeywordExtractor()
        extractor.load()
        extractor._fetch_suggestions = lambda q: [
            f"{q} kadın", f"{q} fiyatları", f"{q} 2024", f"{q}kolik", f"{q} ve tarih"]
        # suitcase kelime kıtlığı çeker (<3), öneri ancak bu durumda istenir
        scored = extractor.extract_scored("suitcase", [])
        by_word = {item.word: item for item in scored}
        # ek tam ifadeye dönüşür: "kadın" değil "bavul kadın"
        self.assertIn("bavul kadın", by_word)
        self.assertEqual(by_word["bavul kadın"].source, "arama önerisi")
        self.assertNotIn("bavul fiyatları", by_word)  # gürültü süzgeci
        self.assertNotIn("bavul 2024", by_word)  # rakamlı ek süzgeci
        self.assertNotIn("bavulkolik", by_word)  # bitişik türev, kelime sınırı süzgeci
        self.assertNotIn("bavul ve tarih", by_word)  # bağlaçla başlayan kırık ek
        # öneriler dolgudur: gerçek temaların önüne geçemez
        self.assertLess([k.word for k in scored].index("valiz"),
                        [k.word for k in scored].index("bavul kadın"))

    def test_dominant_keywords_come_before_scene(self):
        # kitaplıklı masadaki dizüstü: kelimeler önce dizüstünü anlatmalı
        words = self.extract("laptop computer", ["book", "person", "chair"])
        self.assertIn(words[0], ("bilgisayar", "teknoloji"))
        self.assertLess(words.index("bilgisayar"), words.index("insan"))

    def test_coco_mouse_is_a_device(self):
        # COCO köprüsünden gelen mouse aygıttır, kemirgen temaları üretmemeli
        words = self.extract("computer mouse")
        self.assertIn("bilgisayar", words)
        self.assertNotIn("hayvan", words)

    def test_suggestions_only_fill_scarce_lists(self):
        # diğer kaynaklar yeterliyken öneri ucuna hiç gidilmemeli
        extractor = KeywordExtractor()
        extractor.load()
        extractor._fetch_suggestions = lambda q: (_ for _ in ()).throw(AssertionError(
            "kelime kıtlığı yokken öneri istendi"))
        words = extractor.extract("sandwich", [])
        self.assertGreaterEqual(len(words), config.SUGGESTION_FILL_THRESHOLD)


class PickDominantTest(unittest.TestCase):
    def test_confident_object_beats_large_background(self):
        # masa/koltuk gibi büyük düşük güvenli kutu, emin nesneyi ezmemeli
        from app.detector import Detection, ObjectDetector
        table = Detection("table", 0.28, (0, 0, 1000, 1000))
        sandwich = Detection("sandwich", 0.52, (350, 350, 650, 650))
        picked = ObjectDetector().pick_dominant([table, sandwich], (1000, 1000))
        self.assertEqual(picked.label, "sandwich")

    def test_person_yields_to_carried_object(self):
        # elinde çantayla poz veren insan: konu insan değil çantadır
        from app.detector import Detection, ObjectDetector
        person = Detection("person", 0.74, (100, 0, 900, 1000))
        handbag = Detection("handbag", 0.29, (400, 400, 700, 800))
        picked = ObjectDetector().pick_dominant([person, handbag], (1000, 1000))
        self.assertEqual(picked.label, "handbag")

    def test_much_more_confident_small_object_wins(self):
        # kazağın üstündeki papyon: belirgin daha emin küçük aday büyük kutuyu yener
        from app.detector import Detection, ObjectDetector
        sweater = Detection("sweater", 0.43, (100, 100, 900, 1900))
        bow_tie = Detection("bow-tie", 0.64, (400, 300, 600, 500))
        picked = ObjectDetector().pick_dominant([sweater, bow_tie], (1000, 2000))
        self.assertEqual(picked.label, "bow-tie")

    def test_person_alone_stays_dominant(self):
        # sahnede yalnızca insan varsa insan cevaptır, reddedilmez
        from app.detector import Detection, ObjectDetector
        person = Detection("person", 0.74, (200, 100, 800, 900))
        picked = ObjectDetector().pick_dominant([person], (1000, 1000))
        self.assertEqual(picked.label, "person")


class CocoBridgeTest(unittest.TestCase):
    def test_every_mapped_label_has_turkish_name(self):
        # COCO'dan gelen her etiket Türkçe ad haritasında karşılık bulmalı
        import json
        from app.detector import COCO_TO_VOCAB
        from app import config
        names = json.loads(config.OBJECT_NAMES_TR_PATH.read_text(encoding="utf-8"))
        for target in COCO_TO_VOCAB.values():
            self.assertIn(target, names, target)
        self.assertIn("hot dog", names)  # köprüden aynen geçen COCO sınıfı


class ImageLoaderTest(unittest.TestCase):
    def test_svg_is_rejected_with_clear_message(self):
        # vektörel format bilinçli desteklenmiyor, mesaj bunu söylemeli
        with self.assertRaises(ImageLoadError) as ctx:
            ImageLoader().load("/tmp/logo.svg", "path")
        self.assertIn("vektörel", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()

