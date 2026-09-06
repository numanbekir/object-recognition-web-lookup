# Numan Bekir Özçelik - 06.09.2026
"""Html yapısından liste, adım ve alt başlık çıkarımı için çevrimdışı örnekler"""

import unittest

from app.extractor import stems
from app.search import parse_wiki_sections
from app.structure import (best_sections, extract_lists, extract_sections, extract_steps,
                           pick_list, score_sections)

RECIPE_HTML = """
<html><body><nav><ul><li>Ana sayfa</li><li>Tarifler</li><li>Üye ol</li></ul></nav>
<article>
<h2>Sosisli Sandviç Tarifi İçin Malzemeler</h2>
<ul><li>6 adet sosis</li><li>6 adet sandviç ekmeği</li><li>2 yemek kaşığı salça</li><li>Ketçap</li></ul>
<h2>Sosisli Sandviç Tarifi Nasıl Yapılır?</h2>
<p>Geniş bir tencerede salçayı ve yağı kavurun, ardından sıcak suyu ekleyin.</p>
<p>Sosisleri çapraz çizip salçalı suda on beş dakika kısık ateşte pişirin.</p>
<p>Ekmekleri boydan kesip sosisleri yerleştirin ve soslarla servis edin.</p>
<h2>Yorumlar</h2><ul><li>Harika</li><li>Denedim</li><li>Süper</li></ul>
</article></body></html>
"""

TYPES_HTML = """
<html><body><main>
<h2>Kompakt Fotoğraf Makineleri</h2><p>Kompakt fotoğraf makineleri taşınabilirlik açısından en pratik seçenektir. Küçük gövdeleri vardır.</p>
<h2>DSLR Fotoğraf Makineleri</h2><p>DSLR makineler profesyonel çekimlerde tercih edilen aynalı sistemlerdir. Lens değiştirilebilir.</p>
<h2>Aynasız Fotoğraf Makineleri</h2><p>Aynasız makineler DSLR kalitesini daha hafif bir gövdede sunar ve sessiz çalışır.</p>
<h2>En İyi Fotoğraf Makinesi Fiyatları</h2><p>Fiyatlar modele göre değişir ve kampanya dönemlerinde düşer, indirimleri takip edin.</p>
</main></body></html>
"""

WIKI_HTML = """
<div class="mw-parser-output"><p>Pizza İtalyan kökenli bir yemektir ve dünyada yaygındır.</p>
<div class="mw-heading"><h2>Tarih</h2></div>
<p>Neolitik Çağ'dan beri pizzaya benzer yiyecekler yapılmıştır ve ekmeğin üzerine malzeme koymak binlerce yıllık bir gelenektir.[1]</p>
<div class="mw-heading"><h2>Kaynakça</h2></div><p>Bir kaynak listesi burada uzun uzun anlatılır ve yüz karakteri geçer, ancak atlanmalıdır çünkü bölüm adı kaynakçadır.</p>
</div>
"""


class ListAndStepTest(unittest.TestCase):
    def test_ingredient_list_found_and_nav_and_comments_skipped(self):
        lists = extract_lists(RECIPE_HTML)
        labels = [entry["etiket"] for entry in lists]
        self.assertIn("Sosisli Sandviç Tarifi İçin Malzemeler", labels)
        self.assertNotIn("Yorumlar", labels)
        found = pick_list(lists, ("malzeme",), 10)
        self.assertEqual(found["maddeler"][0], "6 adet sosis")

    def test_steps_after_heading(self):
        steps = extract_steps(RECIPE_HTML)
        self.assertEqual(len(steps), 3)
        self.assertTrue(steps[0].startswith("Geniş bir tencerede"))


class SectionTest(unittest.TestCase):
    def test_sections_and_scoring(self):
        sections = extract_sections(TYPES_HTML)
        self.assertEqual([s["baslik"] for s in sections][:3],
                         ["Kompakt Fotoğraf Makineleri", "DSLR Fotoğraf Makineleri",
                          "Aynasız Fotoğraf Makineleri"])
        self.assertTrue(sections[0]["metin"].endswith("seçenektir."))  # yalnız ilk cümle
        anchor = stems("fotoğraf makinesi")
        best = best_sections([("x.com", "https://x.com", sections)], anchor, 5)
        self.assertIsNotNone(best)
        self.assertNotIn("Fiyatları", " ".join(s["baslik"] for s in best[2]))  # ticari başlık elendi
        self.assertGreater(score_sections(sections[:3], anchor), 0.6)

    def test_wiki_sections_skip_references(self):
        sections = parse_wiki_sections(WIKI_HTML)
        self.assertEqual([s["baslik"] for s in sections], ["Tarih"])
        self.assertNotIn("[1]", sections[0]["metin"])


if __name__ == "__main__":
    unittest.main()
