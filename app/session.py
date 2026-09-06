# Numan Bekir Özçelik - 06.09.2026
"""Sohbet bağlamı: son turların objeleri ve anahtar kelimeleri.

Yeni turun kelimeleri önceki bir turla kesişiyorsa iki tur aynı konudadır,
ortak kelime arama sorgusuna eklenir. Kesişim yoksa konu değişmiş
sayılır ve eski tur aramaya karışmaz.
"""

from . import config


class SessionContext:
    def __init__(self, window: int = None):
        self.window = config.CONTEXT_WINDOW if window is None else window
        self.entries = []  # eski -> yeni, {"obje", "kelimeler"}

    def add_turn(self, object_tr: str, keywords: list):
        self.entries.append({"obje": object_tr, "kelimeler": list(keywords)})
        self.entries = self.entries[-self.window:]

    def last_object(self):
        return self.entries[-1]["obje"] if self.entries else None

    def last_keywords(self) -> list:
        return list(self.entries[-1]["kelimeler"]) if self.entries else []

    def shared_context(self, object_tr: str, keywords: list):
        """Kelime kesişimi olan en yeni önceki turu (obje, ortak kelime) olarak döndürür."""
        current = {word.lower() for word in keywords}
        for entry in reversed(self.entries):
            if entry["obje"] == object_tr:
                continue
            shared = [word for word in entry["kelimeler"] if word.lower() in current]
            if shared:
                return entry["obje"], shared[0]
        return None

    def summary_line(self) -> str:
        if not self.entries:
            return ""
        objects = " → ".join(entry["obje"] for entry in self.entries)
        return f"Sohbet: {objects}"
