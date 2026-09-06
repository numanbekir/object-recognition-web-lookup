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
        # tırnaklı çift yol da çoklu sayılmalı
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
        # üst kavramdan kategori, parça ilişkisinden bileşen gelir
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
        # insan ve zaman anlamları atlanır, nesne anlamı seçilir
        self.assertIn("köpek", self.extract("dalmatian"))
        self.assertIn("meyve", self.extract("date"))
        # farklı anlamların temaları birbirine karışmaz
        words = self.extract("mouse")
        self.assertIn("hayvan", words)
        self.assertNotIn("teknoloji", words)

    def test_scoring_drops_distant_leaks(self):
        # uzak ve genel kavramdan sızan tema elenir
        self.assertNotIn("ev eşyası", self.extract("ambulance"))

    def test_meronym_requires_sense_match(self):
        # bileşen çevirisi farklı anlamdaki karşılığa düşmez
        self.assertNotIn("drone", self.extract("bagpipe"))
        self.assertNotIn("zarf", self.extract("balloon"))

    def test_suggestion_keywords_filtered_and_labeled(self):
        extractor = KeywordExtractor()
        extractor.load()
        extractor._fetch_suggestions = lambda q: [
            f"{q} kadın", f"{q} fiyatları", f"{q} 2024", f"{q}kolik", f"{q} ve tarih"]
        # kelime kıtlığı çeken nesnede öneri istenir
        scored = extractor.extract_scored("suitcase", [])
        by_word = {item.word: item for item in scored}
        self.assertIn("bavul kadın", by_word)  # ek tam ifadeye dönüşür
        self.assertEqual(by_word["bavul kadın"].source, "arama önerisi")
        self.assertNotIn("bavul fiyatları", by_word)  # gürültü süzgeci
        self.assertNotIn("bavul 2024", by_word)  # rakamlı ek süzgeci
        self.assertNotIn("bavulkolik", by_word)  # kelime sınırı süzgeci
        self.assertNotIn("bavul ve tarih", by_word)  # bağlaçla başlayan ek
        # öneriler gerçek temaların önüne geçmez
        self.assertLess([k.word for k in scored].index("valiz"),
                        [k.word for k in scored].index("bavul kadın"))

    def test_dominant_keywords_come_before_scene(self):
        # kelimeler önce baskın nesneyi anlatmalı
        words = self.extract("laptop computer", ["book", "person", "chair"])
        self.assertIn(words[0], ("bilgisayar", "teknoloji"))
        self.assertLess(words.index("bilgisayar"), words.index("insan"))

    def test_coco_mouse_is_a_device(self):
        # köprüden gelen mouse aygıttır, kemirgen temaları üretmemeli
        words = self.extract("computer mouse")
        self.assertIn("bilgisayar", words)
        self.assertNotIn("hayvan", words)

    def test_suggestions_only_fill_scarce_lists(self):
        # diğer kaynaklar yeterliyse öneri ucuna gidilmez
        extractor = KeywordExtractor()
        extractor.load()
        extractor._fetch_suggestions = lambda q: (_ for _ in ()).throw(AssertionError(
            "kelime kıtlığı yokken öneri istendi"))
        words = extractor.extract("sandwich", [])
        self.assertGreaterEqual(len(words), config.SUGGESTION_FILL_THRESHOLD)


class PickDominantTest(unittest.TestCase):
    def test_confident_object_beats_large_background(self):
        # büyük ama güvensiz kutu emin nesneyi ezmemeli
        from app.detector import Detection, ObjectDetector
        table = Detection("table", 0.28, (0, 0, 1000, 1000))
        sandwich = Detection("sandwich", 0.52, (350, 350, 650, 650))
        picked = ObjectDetector().pick_dominant([table, sandwich], (1000, 1000))
        self.assertEqual(picked.label, "sandwich")

    def test_person_yields_to_carried_object(self):
        # insan taşıyıcıysa konu taşıdığı nesnedir
        from app.detector import Detection, ObjectDetector
        person = Detection("person", 0.74, (100, 0, 900, 1000))
        handbag = Detection("handbag", 0.29, (400, 400, 700, 800))
        picked = ObjectDetector().pick_dominant([person, handbag], (1000, 1000))
        self.assertEqual(picked.label, "handbag")

    def test_much_more_confident_small_object_wins(self):
        # belirgin daha emin küçük aday büyük kutuyu yener
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


class UmbrellaRefinementTest(unittest.TestCase):
    def _detector(self):
        from app.detector import ObjectDetector
        return ObjectDetector()

    def _detection(self, label, conf, box=(10, 10, 90, 90)):
        from app.detector import Detection
        return Detection(label, conf, box)

    def test_specific_overlapping_label_wins(self):
        detector = self._detector()
        dominant = self._detection("sandwich", 0.92)
        world = [self._detection("hamburger", 0.84, (12, 12, 88, 88)),
                 self._detection("cup", 0.80, (200, 200, 260, 260))]  # örtüşmüyor
        refined = detector._pick_refinement(dominant, world)
        self.assertEqual(refined.label, "hamburger")

    def test_same_label_or_weak_candidate_keeps_umbrella(self):
        detector = self._detector()
        dominant = self._detection("sandwich", 0.92)
        # açık dağarcık da en emin etiket olarak şemsiyeyi veriyor
        same = [self._detection("sandwich", 0.90, (12, 12, 88, 88)),
                self._detection("hamburger", 0.80, (12, 12, 88, 88))]
        self.assertIsNone(detector._pick_refinement(dominant, same))
        # ölçülen önyargı bandındaki değer inceltmeye yetmez
        biased = [self._detection("hamburger", 0.67, (12, 12, 88, 88))]
        self.assertIsNone(detector._pick_refinement(dominant, biased))

    def test_person_and_disjoint_boxes_ignored(self):
        detector = self._detector()
        dominant = self._detection("sandwich", 0.92)
        world = [self._detection("person", 0.90, (10, 10, 90, 90)),
                 self._detection("hamburger", 0.60, (300, 300, 400, 400))]
        self.assertIsNone(detector._pick_refinement(dominant, world))


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


class WebSearcherQueryTest(unittest.TestCase):
    def test_support_term_skips_anchor_phrases(self):
        from app.search import WebSearcher
        term = WebSearcher().support_term(
            "sandviç", ["sandviç ekmeği", "aperatif yemek", "atıştırmalık"])
        self.assertEqual(term, "aperatif yemek")
        self.assertEqual(WebSearcher().support_term("köpek", []), "")


    def test_anchor_plus_single_support_term(self):
        # obje adı ve tek destek kelimesi yeterlidir
        from app.search import WebSearcher
        query = WebSearcher().build_query(
            "sandviç", ["aperatif yemek", "atıştırmalık", "yemek tarifi"])
        self.assertEqual(query, "sandviç aperatif yemek")

    def test_phrase_containing_anchor_skipped(self):
        # obje adını içeren ifade sorguya tekrar girmez
        from app.search import WebSearcher
        query = WebSearcher().build_query("klavye", ["klavye dili", "elektronik"])
        self.assertEqual(query, "klavye elektronik")


class ExtractorFilterTest(unittest.TestCase):
    def setUp(self):
        from app.extractor import ContentExtractor
        self.extractor = ContentExtractor()

    def test_rule_filter(self):
        ok = self.extractor._passes_rules
        self.assertTrue(ok("Sandviç, iki ekmek dilimi arasına konulan "
                           "malzemelerle hazırlanan pratik bir yiyecektir."))
        self.assertFalse(ok("Çok kısa."))
        self.assertFalse(ok("Sandviç sever misin?" + " x" * 30))
        self.assertFalse(ok("Hemen al butonuna tıkla ve kampanyalı ürünleri "
                            "kaçırmadan sepetine ekle şimdi hemen bugün."))
        self.assertFalse(ok("Bu yüzden çoğu kişi tarafından tercih edilen bir "
                            "yöntem olarak uzun yıllardır bilinmektedir."))
        # tarif adımı talimattır, açıklama değil
        self.assertFalse(ok("Sosisleri közlendikten sonra sandviç ekmeklerinin "
                            "arasına yerleştirip üzerine sos ekleyerek koyun."))
        # okuyucuya seslenen dil elenir
        self.assertFalse(ok("Dilerseniz sandviçinizi farklı soslarla çok daha "
                            "lezzetli hale getirebilirsiniz her zaman kolayca."))
        # iki nokta başlık kalıntısıdır
        self.assertFalse(ok("Püf Noktası - Ekmek seçimi: tam buğday ekmekleri "
                            "sandviçe ekstra lezzet katan seçenekler arasındadır."))

    def test_relevance_needs_anchor(self):
        score = self.extractor._relevance(
            "sandviç hazırlarken taze ekmek kullanmak lezzeti artırır.",
            "sandviç", ["ekmek"])
        self.assertGreater(score, 0)
        off_topic = self.extractor._relevance(
            "hava durumu yarın parçalı bulutlu olacak deniyor.",
            "sandviç", ["ekmek"])
        self.assertEqual(off_topic, 0)

    def test_context_bonus_ranks_but_cannot_admit(self):
        # bağlam alaka eşiğini aşamaz, yalnız geçen cümlelerde sayılır
        class FakeResult:
            domain = "a.com"

        page_text = (
            "Sandviç, iki ekmek dilimi arasına konulan malzemelerle hazırlanan "
            "bir yiyecektir. Sandviç çeşitleri arasında sosisli sandviç de "
            "sayılmaktadır ve oldukça yaygındır. Sosisli tezgahları festival "
            "alanlarında sıkça kurulmaktadır her yıl düzenli olarak.")
        kept = self.extractor.select_sentences(
            [(FakeResult(), page_text)], "sandviç", ["ekmek"],
            ["sosisli sandviç", "atıştırmalık"])
        texts = [s.text for s in kept]
        self.assertEqual(len(kept), 2)
        # çapasız cümleyi bağlam kurtaramaz
        self.assertFalse(any(t.startswith("Sosisli tezgahları") for t in texts))
        hits = {s.text[:16]: s.context_hits for s in kept}
        self.assertEqual(hits["Sandviç, iki ekm"], 0)
        self.assertEqual(hits["Sandviç çeşitler"], 1)

    def test_deduplicate_near_copies(self):
        from app.extractor import Sentence
        first = Sentence("Sandviç iki ekmek dilimi arasına malzeme konularak "
                         "hazırlanan bir yiyecektir.", "a.com", 2.0)
        copy = Sentence("Sandviç, iki ekmek dilimi arasına malzeme konularak "
                        "hazırlanan yiyecektir.", "b.com", 1.5)
        different = Sentence("Dünyanın en uzun sandviçi festival sırasında "
                             "yüzlerce kişiyle paylaşıldı.", "c.com", 1.0)
        kept = self.extractor._deduplicate([first, copy, different])
        texts = [s.text for s in kept]
        self.assertEqual(len(kept), 2)
        self.assertIn(first.text, texts)
        self.assertIn(different.text, texts)


class ComposerTest(unittest.TestCase):
    def test_definition_first_detail_last_and_sources(self):
        from app.composer import TextComposer
        from app.extractor import Sentence
        detail = Sentence("Ortalama bir sandviç 250 kalori içerir ve 10 dakikada "
                          "hazırlanabilir.", "a.com", 1.0)
        definition = Sentence("Sandviç, iki ekmek dilimi arasına konulan "
                              "malzemelerle hazırlanan bir yiyecektir.", "b.com", 2.0)
        general = Sentence("Sandviçler pikniklerde ve okul çantalarında en çok "
                           "tercih edilen yiyecekler arasında yer alır.", "a.com", 1.5)
        text, sources, mapping = TextComposer().compose(
            [detail, definition, general], "sandviç")
        self.assertTrue(text.startswith("Sandviç, iki ekmek"))
        self.assertTrue(text.endswith("hazırlanabilir."))
        self.assertEqual(sources, ["b.com", "a.com"])
        self.assertEqual(len(mapping), 3)

    def test_alias_definition_recognized(self):
        # tanım cümlesi objenin eş adıyla kurulabilir
        from app.composer import TextComposer
        from app.extractor import Sentence
        parking = Sentence("Geri park etme sırasında direksiyon mümkün oldukça "
                           "az hareket ettirilmelidir uzmanlara göre.", "a.com", 1.0)
        definition = Sentence("Otomobil, yakıtla çalışan bir motor sayesinde "
                              "kendi kendine hareket edebilen bir taşıttır.", "b.com", 2.0)
        engine = Sentence("Genel olarak otomobiller içten yanmalı motorlarla "
                          "ve dört lastiğin dönmesiyle hareket ederek çalışır.", "c.com", 1.5)
        wheels = Sentence("Otomobillerde motor gücü şanzıman üzerinden "
                          "tekerleklere aktarılır ve taşıt böyle yol alır.", "a.com", 1.2)
        text, sources, _ = TextComposer().compose(
            [parking, engine, definition, wheels], "araba", aliases=["otomobil"])
        self.assertTrue(text.startswith("Otomobil, yakıtla"))
        # çekirdekle örtüşmeyen cümle temadan elenir
        self.assertNotIn("park etme", text)

    def test_context_hits_reorder_within_group(self):
        # bağlama değen cümle kendi grubunda öne gelir, tanım yerinde kalır.
        # bağlamsızken tüm değerler sıfır olduğundan sıralama düzeni değişmez
        from app.composer import TextComposer
        from app.extractor import Sentence
        definition = Sentence("Sandviç, iki ekmek dilimi arasına konulan "
                              "malzemelerle hazırlanan bir yiyecektir.", "a.com", 2.0)
        plain = Sentence("Sandviçler pikniklerde ve okul çantalarında sık "
                         "tercih edilen yiyecekler arasında yer alır.", "b.com", 1.5)
        contextual = Sentence("Sandviç çeşitleri arasında sosisli sandviç "
                              "önemli bir yer tutuyor.", "c.com", 1.5, context_hits=1)
        text, _, _ = TextComposer().compose(
            [definition, plain, contextual], "sandviç")
        self.assertTrue(text.startswith("Sandviç, iki ekmek"))
        self.assertLess(text.find("sosisli"), text.find("piknik"))

    def test_too_few_sentences_returns_empty(self):
        from app.composer import TextComposer
        from app.extractor import Sentence
        lone = Sentence("Sandviç pratik bir yiyecektir.", "a.com", 1.0)
        text, sources, mapping = TextComposer().compose([lone], "sandviç")
        self.assertEqual(text, "")


class ImageLoaderTest(unittest.TestCase):
    def test_svg_is_rejected_with_clear_message(self):
        # vektörel format bilinçli desteklenmiyor, mesaj bunu söylemeli
        with self.assertRaises(ImageLoadError) as ctx:
            ImageLoader().load("/tmp/logo.svg", "path")
        self.assertIn("vektörel", str(ctx.exception))


class SessionContextTest(unittest.TestCase):
    def _session(self):
        from app.session import SessionContext
        return SessionContext()

    def test_decay_and_prune(self):
        # eski ağırlıklar her turda yarılanır, tabanın altı silinir
        session = self._session()
        for name in ("aaa", "bbb", "ccc", "ddd", "eee"):
            session.add_turn(name, [name])
        weights = {e["obje"]: e["agirlik"] for e in session.entries}
        self.assertEqual(session.last_object(), "eee")
        self.assertAlmostEqual(weights["ddd"], 0.5)
        self.assertAlmostEqual(weights["bbb"], 0.125)
        self.assertNotIn("aaa", weights)  # 0.0625 < taban, budandı

    def test_repeat_object_refreshes_without_duplicate(self):
        session = self._session()
        session.add_turn("köpek", ["hayvan"])
        session.add_turn("kedi", ["hayvan"])
        session.add_turn("köpek", ["hayvan"])
        names = [e["obje"] for e in session.entries]
        self.assertEqual(names.count("köpek"), 1)
        self.assertEqual(session.last_object(), "köpek")

    def test_related_entries_sorted_and_gated(self):
        # kesişenler ağırlık sırasıyla gelir, kesişmeyen hiç gelmez
        session = self._session()
        session.add_turn("cep telefonu", ["elektronik", "teknoloji"])
        session.add_turn("köpek", ["evcil hayvan", "bakım"])
        related = session.related_entries("kulaklık", ["elektronik", "müzik"])
        self.assertEqual([e["obje"] for e in related], ["cep telefonu"])
        self.assertEqual(session.related_entries("sandviç", ["yemek"]), [])

    def test_sibling_names_detected(self):
        session = self._session()
        self.assertTrue(session.is_sibling("sosisli sandviç", "sandviç"))
        self.assertFalse(session.is_sibling("cep telefonu", "kulaklık"))

    def test_topic_needs_two_supporters(self):
        session = self._session()
        session.add_turn("cep telefonu", ["elektronik", "teknoloji"])
        self.assertIsNone(session.topic())  # tek obje konu iddia edemez
        session.add_turn("kulaklık", ["elektronik", "müzik"])
        label, weight = session.topic()
        self.assertEqual(label, "elektronik")
        self.assertAlmostEqual(weight, 1.5)

    def test_topic_label_uses_shortest_surface_form(self):
        # aynı kökün en kısa yüzey biçimi etiket olur
        session = self._session()
        session.add_turn("sandviç", ["yemek tarifi", "ekmek"])
        session.add_turn("pizza", ["yemek tarifi", "yemek"])
        label, _ = session.topic()
        self.assertEqual(label, "yemek")

    def test_summary_line_distills_state(self):
        session = self._session()
        self.assertEqual(session.summary_line(), "")
        session.add_turn("cep telefonu", ["elektronik", "teknoloji"])
        self.assertEqual(session.summary_line(), "Son nesne: cep telefonu")
        session.add_turn("kulaklık", ["elektronik", "müzik"])
        self.assertEqual(session.summary_line(),
                         "Konu: elektronik · Son nesne: kulaklık")


class StorageTest(unittest.TestCase):
    def _storage(self, directory):
        from pathlib import Path

        from app.storage import Storage
        return Storage(Path(directory) / "records.json")

    def test_append_and_reload(self):
        import json
        with tempfile.TemporaryDirectory() as directory:
            storage = self._storage(directory)
            self.assertIsNone(storage.load())
            self.assertEqual(storage.next_turn_no(), 1)
            self.assertTrue(storage.append({"tur_no": 1, "durum": "tamam", "obje": "köpek"}))
            data = json.loads(storage.path.read_text(encoding="utf-8"))
            self.assertEqual(data["oturumlar"][0]["turlar"][0]["obje"], "köpek")
            self.assertIn("basladi", data["oturumlar"][0])
            # yeni açılış yeni oturum bloğu açar, tur numarası 1'den başlar
            fresh = self._storage(directory)
            self.assertIsNone(fresh.load())
            self.assertEqual(fresh.next_turn_no(), 1)
            self.assertTrue(fresh.append({"tur_no": 1, "durum": "tamam", "obje": "kedi"}))
            data = json.loads(fresh.path.read_text(encoding="utf-8"))
            self.assertEqual(len(data["oturumlar"]), 2)
            self.assertEqual(data["oturumlar"][0]["turlar"][0]["obje"], "köpek")
            self.assertEqual(data["oturumlar"][1]["turlar"][0]["obje"], "kedi")

    def test_session_start_precedes_first_turn(self):
        # basladi açılışta damgalanır, ilk turun zamanından sonra kalamaz
        from datetime import datetime
        with tempfile.TemporaryDirectory() as directory:
            storage = self._storage(directory)
            turn_time = datetime.now().isoformat(timespec="seconds")
            storage.append({"tur_no": 1, "zaman": turn_time})
            block = storage.records["oturumlar"][0]
            self.assertLessEqual(block["basladi"], turn_time)

    def test_empty_session_leaves_no_block(self):
        # açılıp hiç tur atılmadan kapanan oturum dosyaya blok yazmaz
        import json
        with tempfile.TemporaryDirectory() as directory:
            storage = self._storage(directory)
            storage.load()
            storage.append({"tur_no": 1})
            idle = self._storage(directory)
            idle.load()  # append yok
            data = json.loads(storage.path.read_text(encoding="utf-8"))
            self.assertEqual(len(data["oturumlar"]), 1)

    def test_corrupt_file_is_sidelined(self):
        with tempfile.TemporaryDirectory() as directory:
            storage = self._storage(directory)
            storage.path.write_text("{bozuk json", encoding="utf-8")
            note = storage.load()
            self.assertIsNotNone(note)
            self.assertTrue(storage.path.with_name("records.json.bozuk").exists())
            self.assertFalse(storage.path.exists())
            self.assertTrue(storage.append({"tur_no": 1}))

    def test_unexpected_structure_is_sidelined(self):
        with tempfile.TemporaryDirectory() as directory:
            storage = self._storage(directory)
            storage.path.write_text("[1, 2, 3]", encoding="utf-8")
            self.assertIsNotNone(storage.load())
            self.assertEqual(storage.next_turn_no(), 1)

    def test_write_failure_returns_false(self):
        from pathlib import Path

        from app.storage import Storage
        storage = Storage(Path("/olmayan-dizin/records.json"))
        self.assertFalse(storage.append({"tur_no": 1}))


if __name__ == "__main__":
    unittest.main()

