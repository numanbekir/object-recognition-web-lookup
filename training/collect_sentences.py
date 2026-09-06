# Numan Bekir Özçelik - 06.09.2026
"""Sınıflandırıcı eğitimi için web'ten cümle toplar.

Uygulamanın kendi arama ve çıkarma katmanlarını kullanır ki toplanan
cümleler sahada görülecek dağılımın aynısı olsun. Kural süzgecini ve
alaka kapısını geçen cümleler kaynağıyla birlikte data klasörüne yazılır.
Tekilleştirme etiketlemeden önce burada yapılır. Arama servisini yormamak
için sorgular arasında bekler, kısıtlı oturumda çalıştırılmamalı.
"""

import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import config  # noqa: E402
from app.extractor import ContentExtractor  # noqa: E402
from app.keywords import KeywordExtractor  # noqa: E402
from app.search import WebSearcher  # noqa: E402

OUTPUT = Path(__file__).parent / "data" / "raw_sentences.jsonl"
SEARCH_PAUSE = 4  # saniye, art arda sorgu servisi kısıtlatıyor
MAX_PER_OBJECT = 120  # tek obje veri setini domine etmesin

# çeşitlilik bilinçli, senaryo nesneleri ve alakasız alanlar birlikte
OBJECTS = (
    "sandwich", "hot dog", "hamburger", "pizza", "banana",
    "bus", "car", "bicycle", "dog", "cat",
    "computer keyboard", "computer mouse", "cellular telephone",
    "laptop computer", "television set",
    "backpack", "clock", "book", "chair", "vase",
)


def collect_for_object(label, keywords, searcher, extractor):
    turkish = keywords.turkish_name(label)
    scored = keywords.extract_scored(label, use_suggestions=False)
    words = [item.word for item in scored]
    query_words = [item.word for item in scored if item.source != "bileşen"]
    category = searcher.support_term(turkish, query_words)
    queries = [f"{turkish} {category} nedir" if category else f"{turkish} nedir",
               searcher.build_query(turkish, query_words)]

    pages = []
    for query in queries:
        try:
            results = searcher.search(query)
        except Exception as error:
            print(f"  arama hatası ({query}): {error!r}")
            continue
        pages += extractor.fetch_pages(results[:config.MAX_PAGES])
        time.sleep(SEARCH_PAUSE)

    sentences = extractor.select_sentences(pages, turkish, words)
    rows = [{"cumle": s.text, "obje": turkish, "domain": s.source, "sorgu": queries[0]}
            for s in sentences[:MAX_PER_OBJECT]]
    print(f"  {turkish}: {len(pages)} sayfa -> {len(rows)} cümle")
    return rows


def main():
    if OUTPUT.exists():
        print(f"{OUTPUT} zaten var, üzerine yazmamak için çıkılıyor. "
              "Yeniden toplamak için dosyayı taşı.")
        return
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)

    keywords = KeywordExtractor()
    keywords.load()
    searcher = WebSearcher()
    extractor = ContentExtractor()

    rows, seen = [], set()
    for index, label in enumerate(OBJECTS, 1):
        print(f"[{index}/{len(OBJECTS)}] {label}")
        for row in collect_for_object(label, keywords, searcher, extractor):
            if row["cumle"] in seen:  # nesneler arası birebir kopya
                continue
            seen.add(row["cumle"])
            rows.append(row)

    with open(OUTPUT, "w", encoding="utf-8") as file:
        for row in rows:
            file.write(json.dumps(row, ensure_ascii=False) + "\n")
    print(f"\nToplam {len(rows)} cümle -> {OUTPUT}")
    print("Sıradaki adım etiketleme, training/label_tool.py")


if __name__ == "__main__":
    main()
