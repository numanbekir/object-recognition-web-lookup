# Numan Bekir Özçelik - 07.09.2026
"""Blokların markdown metnine çevrilmesi"""

import unittest

from app.render import blocks_markdown, definition_markdown, source_urls, sources_line


class RenderTest(unittest.TestCase):
    def test_blocks_to_markdown_with_footnotes(self):
        blocks = [
            {"baslik": "Tanım", "sorgu": "x", "yapi": None,
             "paragraflar": [{"metin": "Sosisli sandviç bir sandviçtir.", "kaynak": "tr.wikipedia.org", "url": "u1"}]},
            {"baslik": "Tarif", "sorgu": "y", "paragraflar": [],
             "yapi": {"tip": "tarif", "malzemeler": ["5 sosis", "5 ekmek"], "adimlar": ["Kaynat.", "Ekle."],
                      "kaynak": "yemek.com", "url": "u2", "adim_kaynak": "nefis.com", "adim_url": "u3"}},
            {"baslik": "Çeşitleri", "sorgu": "z", "paragraflar": [],
             "yapi": {"tip": "basliklar", "ogeler": [{"baslik": "Klasik", "metin": "En yaygın olanıdır."}],
                      "kaynak": "blog.com", "url": "u4"}},
        ]
        text, sources = blocks_markdown(blocks)
        self.assertEqual(sources, ["tr.wikipedia.org", "yemek.com", "nefis.com", "blog.com"])
        self.assertIn("### ▸ Tanım", text)
        self.assertIn("bir sandviçtir. [1]", text)
        self.assertIn("- 5 sosis", text)
        self.assertIn("1. Kaynat.", text)
        self.assertIn("[2] adımlar [3]", text)
        self.assertIn("- **Klasik** En yaygın olanıdır.", text)
        self.assertEqual(sources_line(sources[:2]), "[1] tr.wikipedia.org  [2] yemek.com")
        self.assertEqual(source_urls(blocks)["nefis.com"], "u3")
        screen, _ = blocks_markdown(blocks, for_screen=True)
        self.assertEqual(screen.count("\u00a0"), 2)  # üç blok, iki ayırıcı
        self.assertIn("[\\[1\\]](u1)", screen)  # dipnot ekranda bağlantı
        self.assertNotIn("\u00a0", text)  # kayıt metni sade
        self.assertIn("bir sandviçtir. [1]", text)

    def test_definition_markdown(self):
        self.assertTrue(definition_markdown({"metin": "Tanım metni.", "kaynak": "w", "url": "u"})
                        .startswith("### ▸ Tanım"))


if __name__ == "__main__":
    unittest.main()
