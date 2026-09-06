# Numan Bekir Özçelik - 04.09.2026
"""Dağarcık -> anahtar kelime hattının kapalı devre olduğunu doğrular.

Her dağarcık ismi için üç şeyi kontrol eder:
    1. WordNet'te isim karşılığı var mı?
    2. Tema üretiyor mu (WordNet zinciri ya da theme_map'teki doğrudan girdi)?
    3. object_names_tr.json'da Türkçe adı var mı?
Dağarcık değiştiğinde çalıştırılır; eksik kalan isimler haritalara elle eklenir.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import config
from app.keywords import KeywordExtractor


def main():
    extractor = KeywordExtractor()
    extractor.load()
    if extractor._wordnet is None:
        print("WordNet yüklenemedi, kontrol yapılamıyor.")
        return 1

    vocabulary = [line.strip() for line in
                  config.VOCABULARY_PATH.read_text(encoding="utf-8").splitlines()
                  if line.strip()]

    stale_stats = extractor.vocab_size != len(vocabulary)
    if stale_stats:
        print(f"UYARI: concept_stats.json bayat ({extractor.vocab_size} nesneyle "
              f"üretilmiş, dağarcık {len(vocabulary)}) - build_concept_stats.py çalıştırılmalı.")

    no_wordnet, no_theme, no_turkish = [], [], []
    for name in vocabulary:
        if not extractor._wordnet.synsets(name.replace(" ", "_"), pos="n"):
            no_wordnet.append(name)
        if not extractor.extract(name, [], use_suggestions=False):
            no_theme.append(name)
        if name not in extractor.names_tr:
            no_turkish.append(name)

    print(f"Dağarcık: {len(vocabulary)} isim")
    print(f"WordNet karşılığı olmayan: {len(no_wordnet)} (tema doğrudan girdiden gelmeli)")
    for name in no_wordnet:
        print(f"  - {name}")
    print(f"Tema üretmeyen: {len(no_theme)} (theme_map'e eklenmeli)")
    for name in no_theme:
        print(f"  - {name}")
    print(f"Türkçe adı olmayan: {len(no_turkish)} (object_names_tr.json'a eklenmeli)")
    for name in no_turkish:
        print(f"  - {name}")

    return 0 if not (no_theme or no_turkish or stale_stats) else 1


if __name__ == "__main__":
    sys.exit(main())
