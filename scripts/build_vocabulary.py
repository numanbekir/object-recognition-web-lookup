# Numan Bekir Özçelik - 06.09.2026
"""LVIS v1 kategori adlarından data/vocabulary.txt üretir.

Tam liste kullanılmaz. Ölçümler büyük listede skor seyrelmesi gösterdi,
küçük listeyle aynı nesneler çok daha yüksek güvenle bulunuyor. Bu yüzden
dağarcık, LVIS içinden seçilmiş yaygın nesnelerle sınırlı tutulur. Yeni
nesne eklemek için SELECTED listesine LVIS adını yazıp script yeniden
çalıştırılır, gömülü model kendiliğinden tazelenir.
"""

import ast
import re
from pathlib import Path

import requests

SOURCE_URL = ("https://raw.githubusercontent.com/facebookresearch/"
              "detectron2/main/detectron2/data/datasets/lvis_v1_categories.py")
OUTPUT_PATH = Path(__file__).resolve().parent.parent / "data" / "vocabulary.txt"

# LVIS'te olmayan, elle eklenen nesneler
EXTRA_TERMS = ["hot dog"]

# LVIS içinden seçilen dağarcık. İlk blok COCO köprüsünün hedef adları,
# hibrit çapraz kontrol bu adları açık dağarcıkta arıyor. İkinci blok
# COCO dışı yaygın nesneler.
SELECTED = [
    "person", "bicycle", "car", "motorcycle", "airplane", "bus", "train",
    "truck", "boat", "traffic light", "fireplug", "stop sign",
    "parking meter", "bench", "bird", "cat", "dog", "horse", "sheep", "cow",
    "elephant", "bear", "zebra", "giraffe", "backpack", "umbrella",
    "handbag", "necktie", "suitcase", "frisbee", "ski", "snowboard", "ball",
    "kite", "baseball bat", "baseball glove", "skateboard", "surfboard",
    "tennis racket", "bottle", "wineglass", "cup", "fork", "knife", "spoon",
    "bowl", "banana", "apple", "sandwich", "orange", "broccoli", "carrot",
    "pizza", "doughnut", "cake", "chair", "sofa", "flowerpot", "bed",
    "toilet", "laptop computer", "mouse", "remote control",
    "computer keyboard", "cellular telephone", "microwave oven", "oven",
    "toaster", "sink", "refrigerator", "book", "clock", "vase", "scissors",
    "teddy bear", "hair dryer", "toothbrush", "television set",

    "camera", "coconut", "chocolate bar", "teapot", "kettle", "wallet",
    "guitar", "violin", "piano", "drum", "watch", "sunglasses", "hat",
    "shoe", "boot", "shirt", "dress", "jacket", "coat", "sweater", "jean",
    "scarf", "glove", "belt", "ring", "necklace", "bracelet", "earring",
    "lamp", "candle", "mirror", "pillow", "blanket", "towel", "curtain",
    "ladder", "hammer", "screwdriver", "pen", "pencil", "envelope", "key",
    "coin", "helmet", "strawberry", "grape", "lemon", "watermelon",
    "pineapple", "peach", "pear", "cherry", "tomato", "potato", "onion",
    "cucumber", "mushroom", "egg", "bread", "cookie", "muffin", "cupcake",
    "pretzel", "hamburger", "taco", "burrito", "sushi", "lettuce",
    "pumpkin", "garlic", "avocado", "fig", "date", "almond", "honey",
    "butter", "yogurt", "milk", "edible corn", "mug", "plate", "tray",
    "napkin", "basket", "bucket", "broom", "soap", "shampoo", "perfume",
    "hairbrush", "toothpaste", "thermometer", "bandage", "crutch",
    "wheelchair", "tricycle", "canoe", "binoculars", "compass",
    "flashlight", "lantern", "matchbox", "fireplace", "fan", "heater",
    "radiator", "radio receiver", "speaker", "headset", "earphone",
    "printer", "monitor", "calculator", "stapler", "clipboard", "calendar",
    "map", "globe", "trophy cup", "balloon", "doll", "drumstick",
    "saxophone", "microphone",
]


def clean(name: str) -> str:
    name = name.split()[0]  # boşluk sonrası eşanlamlı yazımlar atılır
    name = re.sub(r"_\(.*\)$", "", name)  # flip-flop_(sandal) -> flip-flop
    return name.replace("_", " ").strip()


def main():
    text = requests.get(SOURCE_URL, timeout=30).text
    start = text.index("[", text.index("LVIS_CATEGORIES"))
    literal = text[start:text.rindex("]") + 1]
    categories = ast.literal_eval(literal)

    lvis = {clean(c["name"]) for c in categories}
    missing = [name for name in SELECTED if name not in lvis]
    if missing:
        print(f"Uyarı, bu adlar LVIS'te yok ve atlandı: {missing}")
    names = sorted(({n for n in SELECTED if n in lvis}) | set(EXTRA_TERMS))
    OUTPUT_PATH.write_text("\n".join(names) + "\n", encoding="utf-8")
    print(f"{len(names)} kavram yazıldı -> {OUTPUT_PATH}")

    # dağarcık değiştiğinde eski gömülü model yeniden üretilsin
    custom_model = OUTPUT_PATH.parent.parent / "models" / "detector-lvis.pt"
    if custom_model.exists():
        custom_model.unlink()
        print("Gömülü model silindi, bir sonraki açılışta yeni dağarcıkla üretilecek.")


if __name__ == "__main__":
    main()
