# Numan Bekir Özçelik - 04.09.2026
"""LVIS v1 kategori adlarından data/vocabulary.txt üretir, bir kez çalıştırılır"""

import ast
import re
from pathlib import Path

import requests

SOURCE_URL = ("https://raw.githubusercontent.com/facebookresearch/"
              "detectron2/main/detectron2/data/datasets/lvis_v1_categories.py")
OUTPUT_PATH = Path(__file__).resolve().parent.parent / "data" / "vocabulary.txt"

# LVIS'te olmayan, elle eklenen nesneler (boş tutulur; gerçek bir ihtiyaç
# gözlemlenirse eklenir, ekleme prosedürü için proje notlarına bakılır)
EXTRA_TERMS = []


def clean(name: str) -> str:
    name = name.split()[0]  # boşluk sonrası eşanlamlı yazımlar atılır
    name = re.sub(r"_\(.*\)$", "", name)  # flip-flop_(sandal) -> flip-flop
    return name.replace("_", " ").strip()


def main():
    text = requests.get(SOURCE_URL, timeout=30).text
    start = text.index("[", text.index("LVIS_CATEGORIES"))
    literal = text[start:text.rindex("]") + 1]
    categories = ast.literal_eval(literal)

    names = sorted({clean(c["name"]) for c in categories} | set(EXTRA_TERMS))
    OUTPUT_PATH.write_text("\n".join(names) + "\n", encoding="utf-8")
    print(f"{len(names)} kavram yazıldı -> {OUTPUT_PATH}")

    # dağarcık değiştiğinde eski gömülü model yeniden üretilsin
    custom_model = OUTPUT_PATH.parent.parent / "models" / "detector-lvis.pt"
    if custom_model.exists():
        custom_model.unlink()
        print("Gömülü model silindi, bir sonraki açılışta yeni dağarcıkla üretilecek.")


if __name__ == "__main__":
    main()
