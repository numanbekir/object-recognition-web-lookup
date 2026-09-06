# Numan Bekir Özçelik - 06.09.2026
"""Ağ ve model gerektirmeyen birim testleri: python3 -m unittest"""

import json
import tempfile
import unittest
from pathlib import Path

from app.extractor import ContentExtractor, stems
from app.search import SearchResult, WebSearcher
from app.session import SessionContext
from app.storage import Storage
from app.vision import VisionModel
from main import classify_input, find_sources, normalize_schemeless


class InputTest(unittest.TestCase):
    def test_url_and_quit(self):
        self.assertEqual(classify_input("https://x.com/a.jpg"), ("url", "https://x.com/a.jpg"))
        self.assertEqual(classify_input(" q "), ("quit", ""))
        self.assertEqual(classify_input(""), ("empty", ""))

    def test_schemeless_and_missing(self):
        self.assertEqual(normalize_schemeless("www.x.com/a.jpg"), "https://www.x.com/a.jpg")
        self.assertEqual(classify_input("/yok/boyle/bir/dosya.png")[0], "missing_file")
        self.assertEqual(classify_input("ftp://x.com/a.jpg")[0], "bad_scheme")

    def test_text_and_multi(self):
        self.assertEqual(classify_input("fiyatları ne kadar"), ("text", "fiyatları ne kadar"))
        self.assertEqual(len(find_sources("a.jpg b.png")), 2)
        self.assertEqual(classify_input("a.jpg b.png")[0], "multi")


class VisionRankingTest(unittest.TestCase):
    def test_rank_orders_descending(self):
        self.assertEqual(VisionModel.rank([0.1, 0.7, 0.2], ["a", "b", "c"], 2),
                         [("b", 0.7), ("c", 0.2)])

    def test_keywords_skip_object_name_and_duplicates(self):
        themes = {"bag": ["çanta", "aksesuar"], "travel": ["seyahat"],
                  "fashion_accessory": ["aksesuar", "moda"], "toy": ["oyuncak"]}
        keys = sorted(themes)  # bag, fashion_accessory, toy, travel
        scores = [0.5, 0.3, 0.001, 0.2]
        words = [k.word for k in VisionModel.keywords_from_themes(
            scores, keys, themes, "sırt çantası", 5)]
        # tema başına önce bir kelime, çanta (obje adı) ve oyuncak (zayıf tema) yok
        self.assertEqual(words, ["aksesuar", "seyahat", "moda"])


class SessionTest(unittest.TestCase):
    def test_shared_context_and_window(self):
        session = SessionContext(window=2)
        session.add_turn("sırt çantası", ["aksesuar", "seyahat"])
        self.assertEqual(session.shared_context("el çantası", ["moda", "aksesuar"]),
                         ("sırt çantası", "aksesuar"))
        self.assertIsNone(session.shared_context("pizza", ["fast food"]))
        session.add_turn("el çantası", ["moda"])
        session.add_turn("pizza", ["fast food"])
        self.assertEqual([e["obje"] for e in session.entries], ["el çantası", "pizza"])
        self.assertIn("→", session.summary_line())


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

    def test_stems_tolerate_suffixes(self):
        self.assertEqual(stems("sandviçler sandviçin"), ["sandv", "sandv"])


class SearchTest(unittest.TestCase):
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
