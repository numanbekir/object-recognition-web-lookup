# Numan Bekir Özçelik - 06.09.2026
"""Ağ ve model gerektirmeyen birim testleri"""

import json
import tempfile
import unittest
from pathlib import Path

from app.extractor import ContentExtractor, cosine, stems
from app.search import SearchResult, WebSearcher
from app.session import SessionContext
from app.storage import Storage
from app.vision import VisionModel
from app import config
from main import classify_input, find_sources, normalize_schemeless, split_source_text

ROLES = {"aile", "alan", "nitelik", "kullanım", "bileşen", "malzeme"}


class InputTest(unittest.TestCase):
    def test_url_and_quit(self):
        self.assertEqual(classify_input("https://x.com/a.jpg"), ("url", "https://x.com/a.jpg"))
        self.assertEqual(classify_input(" q "), ("quit", ""))
        self.assertEqual(classify_input(""), ("empty", ""))

    def test_schemeless_and_missing(self):
        self.assertEqual(normalize_schemeless("www.x.com/a.jpg"), "https://www.x.com/a.jpg")
        self.assertEqual(classify_input("/yok/boyle/bir/dosya.png")[0], "missing_file")
        self.assertEqual(classify_input("ftp://x.com/a.jpg")[0], "bad_scheme")

    def test_source_with_question(self):
        self.assertEqual(split_source_text("/tmp/a.jpg kalorisi ne kadar"), ("/tmp/a.jpg", "kalorisi ne kadar"))
        self.assertEqual(split_source_text("https://x.com/a.jpg"), ("", "https://x.com/a.jpg"))
        self.assertEqual(split_source_text("kalorisi ne kadar"), ("", "kalorisi ne kadar"))
        self.assertEqual(split_source_text("a.jpg b.png"), ("", "a.jpg b.png"))  # iki kaynak, ayrılmaz

    def test_text_and_multi(self):
        self.assertEqual(classify_input("fiyatları ne kadar"), ("text", "fiyatları ne kadar"))
        self.assertEqual(len(find_sources("a.jpg b.png")), 2)
        self.assertEqual(classify_input("a.jpg b.png")[0], "multi")


class VocabularyTest(unittest.TestCase):
    """Veri dosyaları elle düzenlenir, tutarsızlık burada yakalanır."""

    def test_every_theme_word_has_a_role(self):
        themes = json.loads(config.THEME_MAP_PATH.read_text(encoding="utf-8"))
        roles = json.loads(config.WORD_ROLES_PATH.read_text(encoding="utf-8"))
        words = {word for values in themes.values() for word in values}
        self.assertEqual(sorted(words - set(roles)), [], "rolü olmayan kelime")
        self.assertEqual(sorted(set(roles) - words), [], "haritada geçmeyen kelime")
        self.assertEqual(sorted(set(roles.values()) - ROLES), [], "tanımsız rol")

    def test_object_names_are_unique_and_turkish(self):
        names = json.loads(config.OBJECT_NAMES_TR_PATH.read_text(encoding="utf-8"))
        self.assertEqual(len(names), len(set(names)))
        self.assertTrue(all(value.strip() for value in names.values()))


class VisionRankingTest(unittest.TestCase):
    def test_rank_orders_descending(self):
        self.assertEqual(VisionModel.rank([0.1, 0.7, 0.2], ["a", "b", "c"], 2),
                         [("b", 0.7), ("c", 0.2)])

    def test_merge_opinions(self):
        unsure = [("sweatshirt", 0.40), ("shoe", 0.30)]
        self.assertEqual(VisionModel.merge_opinions(unsure, "shoe", 0.55), "shoe")  # adaylarda, düşük eşik
        self.assertIsNone(VisionModel.merge_opinions(unsure, "shoe", 0.4))  # sınıflandırıcı emin değil
        self.assertIsNone(VisionModel.merge_opinions(unsure, "pitcher", 0.7))  # aday değil, yüksek eşik
        self.assertEqual(VisionModel.merge_opinions(unsure, "pitcher", 0.9), "pitcher")
        self.assertIsNone(VisionModel.merge_opinions([("shoe", 0.8)], "boot", 0.9))  # sıfır atış emin
        self.assertIsNone(VisionModel.merge_opinions(unsure, "", 0.9))  # obje listesinde karşılığı yok

    def test_reconcile_picks_theme_backed_candidate_when_unsure(self):
        names = {"sweatshirt": "spor giyim", "shoe": "ayakkabı", "trousers": "pantolon"}
        candidates = [("sweatshirt", 0.47), ("shoe", 0.30), ("trousers", 0.05)]
        themes = [("sneaker", 0.51), ("shoe", 0.08), ("travel", 0.02)]
        self.assertEqual(VisionModel.reconcile(candidates, themes, names), "shoe")
        confident = [("sweatshirt", 0.80), ("shoe", 0.10)]
        self.assertIsNone(VisionModel.reconcile(confident, themes, names))  # güven yüksek, dokunulmaz
        self.assertIsNone(VisionModel.reconcile(candidates, [("travel", 0.9)], names))  # tema objede yok

    def test_keywords_skip_object_name_and_duplicates(self):
        themes = {"bag": ["çanta", "aksesuar"], "travel": ["seyahat"],
                  "fashion_accessory": ["aksesuar", "moda"], "toy": ["oyuncak"]}
        keys = sorted(themes)  # bag, fashion_accessory, toy, travel
        scores = [0.5, 0.3, 0.001, 0.2]
        words = [k.word for k in VisionModel.keywords_from_themes(
            scores, keys, themes, "sırt çantası", 5)]
        # tema başına önce bir kelime, obje adı olan çanta ve zayıf tema oyuncak yok
        self.assertEqual(words, ["aksesuar", "seyahat", "moda"])

    def test_minimum_keywords_filled_from_weaker_themes(self):
        themes = {"pizza": ["hamurlu yemek"], "cheese": ["peynir"], "food": ["yemek"], "toy": ["oyuncak"]}
        keys = sorted(themes)  # cheese, food, pizza, toy
        scores = [0.02, 0.01, 0.9, 0.001]  # yalnız pizza eşiği geçer
        words = [k.word for k in VisionModel.keywords_from_themes(scores, keys, themes, "pizza", 5)]
        self.assertEqual(words[:3], ["hamurlu yemek", "peynir", "yemek"])


class SessionTest(unittest.TestCase):
    def test_shared_context_and_window(self):
        session = SessionContext(window=2)
        session.add_turn("sırt çantası", ["aksesuar", "seyahat"], "ürün")
        self.assertEqual(session.shared_context("el çantası", ["moda", "aksesuar"], "ürün"),
                         ("sırt çantası", "aksesuar"))
        self.assertIsNone(session.shared_context("pizza", ["fast food"], "yemek"))
        self.assertIsNone(session.shared_context("telefon", ["teknoloji"], "ürün"))  # varsayılan aile yetmez
        session.add_turn("el çantası", ["moda"], "ürün")
        session.add_turn("pizza", ["fast food"], "yemek")
        self.assertEqual([e["obje"] for e in session.entries], ["el çantası", "pizza"])

    def test_family_link_and_chain(self):
        session = SessionContext()
        session.add_turn("zürafa", ["hayvan", "doğa"], "canlı")
        session.add_turn("aslan", ["yaban hayatı"], "canlı")
        self.assertEqual(session.shared_context("maymun", ["orman"], "canlı"), ("aslan", None))
        session.add_turn("maymun", ["orman"], "canlı")
        self.assertEqual(session.chain("canlı"), ["zürafa", "aslan", "maymun"])
        session.add_turn("keman", ["müzik"], "enstrüman")
        self.assertEqual(session.turn_count, 4)  # pencere üç tutsa da sayaç dörttür
        self.assertEqual(session.chain("enstrüman"), ["keman"])
        self.assertEqual(session.chain("canlı"), [])

    def test_memory_of_shown_sources_and_repeats(self):
        session = SessionContext()
        session.remember_shown(["https://a.com/x", ""])
        self.assertEqual(session.shown_urls, {"https://a.com/x"})
        session.add_turn("pizza", ["sos"])
        session.add_turn("pizza", ["peynir"])
        self.assertEqual(session.times_seen("pizza"), 2)
        self.assertEqual(session.times_seen("keman"), 0)


class ExtractorTest(unittest.TestCase):
    def test_passage_selection(self):
        page_a = SearchResult("a", "https://a.com/x")
        page_b = SearchResult("b", "https://b.com/y")
        good = ("Sandviç, iki dilim ekmek arasına peynir, sebze ya da et konularak hazırlanan "
                "pratik bir yiyecektir ve dünyanın hemen her mutfağında farklı biçimleriyle bulunur.")
        noise = ("Sandviç sepete eklendi, siparişinizi tamamlamak için ödeme adımına geçin ve "
                 "kampanyalı ürünleri kaçırmayın diye hemen üye olun lütfen.")
        offtopic = ("Pizza hamuru mayalandıktan sonra ince açılır, domates sosu sürülür ve "
                    "fırında yüksek ısıda kısa sürede pişirilir, sonra dilimlenerek servis edilir.")
        pages = [(page_a, good + "\n" + noise), (page_b, offtopic + "\n" + good + " Ek bilgi.")]
        passages = ContentExtractor().select_passages(pages, "sandviç", ["ekmek"], limit=3)
        texts = [p.text for p in passages]
        self.assertEqual(len(passages), 1)  # aynı paragraf ikinci kaynaktan teklendi
        self.assertTrue(texts[0].startswith("Sandviç, iki dilim"))

    def test_clean_strips_recipe_boilerplate(self):
        text = ("C: Sandviç pratik bir yiyecektir ve her öğünde tüketilebilir. "
                "Peki; sandviç nasıl yapılır? İşte tarifi ve malzemeleri... Afiyet olsun!")
        self.assertEqual(ContentExtractor.clean(text),
                         "Sandviç pratik bir yiyecektir ve her öğünde tüketilebilir.")
        glued = "Cruise Gemisi Nasıl Bir Gemidir?: İçinde konaklama olanağı bulunan gemilerdir."
        self.assertEqual(ContentExtractor.clean(glued), "İçinde konaklama olanağı bulunan gemilerdir.")

    def test_block_hints_and_threshold(self):
        page = SearchResult("x", "https://x.com/a")
        history = ("Keman ilk kez 16. yüzyılda İtalya'da ortaya çıkmış, Cremona'daki ustaların "
                   "elinde bugünkü biçimini almış ve iki yüzyıl içinde tüm Avrupa'ya yayılmıştır.")
        lesson = ("Keman dersleri her yaştan öğrenciye açıktır ve kurslarda haftalık programlar "
                  "dahilinde başlangıç seviyesinden ileri seviyeye kadar eğitim verilmektedir.")
        hints = ["tarih", "yüzyıl", "ilk", "ortaya", "köken"]
        passages = ContentExtractor().select_passages(
            [(page, history + "\n" + lesson)], "keman", hints, limit=2,
            hint_stems=stems(" ".join(hints)), min_hint_hits=2, min_score=0.12)
        self.assertEqual([p.text for p in passages], [history])  # ders paragrafı iki kök taşımıyor

    def test_anchor_terms(self):
        from app.extractor import anchor_terms
        self.assertEqual(anchor_terms("sosisli sandviç"), ["sosis", "sandv"])
        self.assertEqual(anchor_terms("el çantası"), ["el çanta"])
        self.assertTrue(ContentExtractor._passes_rules(
            "Sosis ve sandviç ekmeği ile hazırlanan bu yiyecek, pratik bir öğün olarak dünyanın "
            "her yerinde severek tüketilir ve çeşitli soslarla zenginleştirilir.", ["sosis", "sandv"]))
        self.assertFalse(ContentExtractor._passes_rules(
            "Alet çantası, çeşitli el aletlerini saklamak ve taşımak için kullanılan dayanıklı "
            "bir çantadır ve ustalar tarafından her gün işe götürülür.", ["el çanta"]))

    def test_stems_tolerate_suffixes(self):
        self.assertEqual(stems("sandviçler sandviçin"), ["sandv", "sandv"])

    def test_cosine(self):
        self.assertAlmostEqual(cosine({"a": 1.0, "b": 1.0}, {"a": 1.0, "b": 1.0}), 1.0)
        self.assertEqual(cosine({"a": 1.0}, {"b": 1.0}), 0.0)
        self.assertEqual(cosine({}, {"b": 1.0}), 0.0)

    def test_similarity_prefers_rare_shared_stems(self):
        page = SearchResult("x", "https://x.com/a")
        about = ("Keman yapımında kullanılan akçaağaç ve ladin, çalgının sesini belirleyen "
                 "en önemli malzemelerdir ve ustalar bu ağaçları yıllarca kurutarak ahşabın "
                 "nemini dengeler, ardından gövdeyi ince tabakalar halinde oyarak biçimlendirir.")
        generic = ("Keman dersleri her yaştan öğrenciye açıktır ve kurslarda haftalık programlar "
                   "dahilinde başlangıç seviyesinden ileri seviyeye kadar eğitim verilmektedir, "
                   "dersler bireysel ya da grup halinde düzenlenebilmektedir.")
        passages = ContentExtractor().select_passages(
            [(page, about + "\n" + generic)], "keman", ["ahşap", "malzeme"], limit=2)
        self.assertTrue(passages[0].text.startswith("Keman yapımında"))


class SearchTest(unittest.TestCase):
    def test_title_priority(self):
        self.assertGreater(SearchResult("Keman nedir? Tarihçesi", "https://a.com").priority(),
                           SearchResult("Keman fiyatları ve modelleri", "https://b.com").priority())

    def test_build_query(self):
        self.assertEqual(WebSearcher.build_query("el çantası", "aksesuar"), "el çantası aksesuar")
        self.assertEqual(WebSearcher.build_query("çanta", "çanta"), "çanta")
        self.assertEqual(WebSearcher.build_query("pizza", user_text="kalori"), "pizza kalori")


class StorageTest(unittest.TestCase):
    def test_append_creates_session_block(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "records.json"
            storage = Storage(path)
            storage.load()
            self.assertTrue(storage.append({"tur_no": 1, "durum": "tamam"}))
            data = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(len(data["oturumlar"][0]["turlar"]), 1)
            self.assertEqual(storage.next_turn_no(), 2)


if __name__ == "__main__":
    unittest.main()
