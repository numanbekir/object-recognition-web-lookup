# Numan Bekir Özçelik - 06.09.2026
"""Obje, anahtar kelimeler ve bağlamdan Türkçe arama niyeti üretir.

Kural tabanlı doğal dil üretimidir. Anahtar kelimeler rolüne göre cümleye
girer. Nitelik ve malzeme başa sıfat olarak, bileşen -lı ekiyle, kullanım
ve bağlacıyla listelenerek girer. Aile ve alan kelimeleri sorguya girmez
çünkü obje adı o bilgiyi zaten taşır. Ekler ünlü uyumu ve ünsüz
yumuşamasıyla üretilir.
"""

import json

from . import config

BACK_VOWELS = set("aıou")
FRONT_VOWELS = set("eiöü")
ROUNDED = set("oöuü")
VOWELS = BACK_VOWELS | FRONT_VOWELS
SOFTENING = {"k": "ğ", "p": "b", "t": "d", "ç": "c"}  # ünsüz yumuşaması
POSSESSIVE_ENDINGS = ("sı", "si", "su", "sü", "ı", "i", "u", "ü")
MAX_PER_ROLE = 2
OPPOSITES = (("kadın", "erkek"), ("yaz", "kış"))  # birlikte gelirse ikisi de anlamsızdır
FOOD_FAMILIES = {"yemek", "fast food", "atıştırmalık", "aperatif yemek", "yemek tarifi",
                 "hamurlu yemek", "sokak lezzeti", "ev yemeği", "tarif", "tatlı", "fırın ürünü",
                 "et ürünü", "süt ürünü", "sebze", "meyve", "içecek", "şekerleme", "deniz ürünü"}


def last_vowel(word: str) -> str:
    for char in reversed(word.lower()):
        if char in VOWELS:
            return char
    return "a"


def harmony(word: str, family: str) -> str:
    """Ünlü uyumuna göre ekin biçimini seçer."""
    vowel = last_vowel(word)
    back = vowel in BACK_VOWELS
    if family == "lar":
        return "lar" if back else "ler"
    narrow = ("u" if back else "ü") if vowel in ROUNDED else ("ı" if back else "i")
    return "l" + narrow if family == "lı" else narrow


def soften(word: str) -> str:
    # son ünsüz yumuşar, tek heceli istisnalar bu görevde nadir
    return word[:-1] + SOFTENING[word[-1]] if word[-1] in SOFTENING else word


def possessive(word: str) -> str:
    """Belirtisiz tamlama için iyelik eki ekler."""
    if word[-1] in VOWELS:
        return word + "s" + harmony(word, "ı")
    return soften(word) + harmony(word, "ı")


def split_possessive(word: str):
    """Kelimeyi kök ve iyelik eki olarak ayırır, ek yoksa ikinci parça boş döner."""
    for ending in POSSESSIVE_ENDINGS:
        if word.endswith(ending) and len(word) - len(ending) >= 2:
            return word[:-len(ending)], ending
    return word, ""


def plural(name: str) -> str:
    """Tamlamalarda çoğul eki kökle iyelik arasına girer."""
    words = name.split()
    head = words[-1]
    if len(words) > 1:
        root, ending = split_possessive(head)
        if ending:
            plural_root = root + harmony(root, "lar")
            return " ".join(words[:-1] + [plural_root + harmony(plural_root, "ı")])
    return " ".join(words[:-1] + [head + harmony(head, "lar")])


def plural_possessive(word: str) -> str:
    """Tamlama çoğulu üretir. Ek ünsüzle başladığı için yumuşama olmaz"""
    stem = word + harmony(word, "lar")
    return stem + harmony(stem, "ı")


def merge_names(current: str, previous: str):
    """Son kelimesi ortak iki adı tek tamlamada birleştirir, ortak değilse none döner."""
    a, b = current.split(), previous.split()
    if len(a) > 1 and len(b) > 1 and a[-1] == b[-1] and a[:-1] != b[:-1]:
        return " ".join(a[:-1]) + " ve " + " ".join(b[:-1]) + " " + a[-1]
    return None


def join_list(words: list) -> str:
    return " ve ".join(words) if len(words) <= 2 else ", ".join(words[:-1]) + " ve " + words[-1]


class IntentBuilder:
    def __init__(self):
        self.roles = json.loads(config.WORD_ROLES_PATH.read_text(encoding="utf-8"))

    def is_food(self, keywords: list) -> bool:
        return any(word in FOOD_FAMILIES for word in keywords)

    def build(self, object_tr: str, keywords: list, previous_object: str = None) -> str:
        """Arama niyeti cümlesi döndürür. Sorguya girecek kelime yoksa obje adı döner.

        Kelimeler skor sırasında gelir, her rolden en fazla iki kelime alınır.
        Önceki obje bağlamdan gelir. Adlar son kelimeyi paylaşıyorsa birleşir.
        Önceki adı zaten içeren obje olduğu gibi kalır
        """
        food = self.is_food(keywords)
        subject = object_tr
        if previous_object:
            subject = merge_names(object_tr, previous_object) or object_tr

        lowered = {word.lower() for word in keywords}
        excluded = {word for pair in OPPOSITES if set(pair) <= lowered for word in pair}
        by_role = {}
        for word in keywords:
            role = self.roles.get(word, "aile")
            if word.lower() in subject.lower() or word.lower() in excluded:
                continue
            if len(by_role.get(role, [])) >= MAX_PER_ROLE:
                continue
            by_role.setdefault(role, []).append(word)

        parts = by_role.get("nitelik", []) + by_role.get("malzeme", [])
        if by_role.get("bileşen"):
            parts.append(join_list([w + harmony(w, "lı") for w in by_role["bileşen"]]))
        uses = by_role.get("kullanım", [])
        if uses and " " not in subject:
            # tek kelimeli objede kullanım kelimesi tamlama kurar
            phrase = join_list(uses) + " " + (possessive(subject) if food else plural_possessive(subject))
            return " ".join(parts + [phrase] + (["tarifleri"] if food else []))
        if uses:
            parts.append(join_list(uses))
        if not parts:
            return object_tr
        if food:
            return " ".join(parts + [subject, "tarifleri"])
        return " ".join(parts + [plural(subject)])
