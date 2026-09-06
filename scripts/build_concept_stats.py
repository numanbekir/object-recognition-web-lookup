# Numan Bekir Özçelik - 06.09.2026
"""Dağarcıktaki her WordNet kavramının kaç nesneyi kapsadığını sayar.

Çıktı data/concept_stats.json: {"vocab_size": N, "breadth": {kavram: sayı}}.
Anahtar kelime puanlaması bu sayıyı ayırt edicilik ölçüsü olarak kullanır
(az nesneyi kapsayan kavram = o nesneye özgü = değerli). Dağarcık her
değiştiğinde build_vocabulary.py'den sonra yeniden çalıştırılmalıdır.
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import config
from app.keywords import KeywordExtractor, MAX_HYPERNYM_DEPTH, STOP_CONCEPTS


def main():
    extractor = KeywordExtractor()
    extractor.load()
    if extractor._wordnet is None:
        print("WordNet yüklenemedi, istatistik üretilemiyor.")
        return 1
    wordnet = extractor._wordnet

    vocabulary = [line.strip() for line in
                  config.VOCABULARY_PATH.read_text(encoding="utf-8").splitlines()
                  if line.strip()]

    breadth = {}
    for name in vocabulary:
        reached = set()
        for synset in wordnet.synsets(name.replace(" ", "_"), pos="n"):
            level, seen = [synset], set()
            for _ in range(MAX_HYPERNYM_DEPTH):
                next_level = []
                for current in level:
                    for parent in current.hypernyms():
                        if parent in seen:
                            continue
                        seen.add(parent)
                        next_level.append(parent)
                        concept = parent.lemmas()[0].name().lower()
                        if concept not in STOP_CONCEPTS:
                            reached.add(concept)
                level = next_level
                if not level:
                    break
        for concept in reached:
            breadth[concept] = breadth.get(concept, 0) + 1

    stats = {"vocab_size": len(vocabulary), "breadth": breadth}
    config.CONCEPT_STATS_PATH.write_text(
        json.dumps(stats, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"{len(breadth)} kavram sayıldı ({len(vocabulary)} nesne) -> {config.CONCEPT_STATS_PATH}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
