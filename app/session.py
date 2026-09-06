# Numan Bekir Özçelik - 06.09.2026
"""Sohbet bağlamı. Son turların objeleri ve anahtar kelimeleri tutulur.

Yeni turun kelimeleri önceki bir turla kesişiyorsa iki tur aynı konudadır
ve ortak kelime arama sorgusuna eklenir. Kesişim yoksa konu değişmiş
sayılır. Oturumda gösterilen kaynaklar hatırlanır, aynı obje tekrar
geldiğinde yeni kaynaklar aranır.
"""

from . import config


class SessionContext:
    def __init__(self, window: int = None):
        self.window = config.CONTEXT_WINDOW if window is None else window
        self.entries = []  # eski turdan yeniye
        self.shown_urls = set()  # oturumda gösterilen kaynak adresleri
        self.object_counts = {}  # obje kaç kez konuşuldu

    def add_turn(self, object_tr: str, keywords: list):
        self.entries.append({"obje": object_tr, "kelimeler": list(keywords)})
        self.entries = self.entries[-self.window:]
        self.object_counts[object_tr] = self.object_counts.get(object_tr, 0) + 1

    def remember_shown(self, urls):
        self.shown_urls.update(url for url in urls if url)

    def times_seen(self, object_tr: str) -> int:
        return self.object_counts.get(object_tr, 0)

    def last_object(self):
        return self.entries[-1]["obje"] if self.entries else None

    def last_keywords(self) -> list:
        return list(self.entries[-1]["kelimeler"]) if self.entries else []

    def shared_context(self, object_tr: str, keywords: list):
        """Kelime kesişimi olan en yeni önceki turu obje ve ortak kelime olarak döndürür."""
        for entry in reversed(self.entries):
            if entry["obje"] == object_tr:
                continue
            previous = {word.lower() for word in entry["kelimeler"]}
            # mevcut turun kelimeleri skor sırasındadır, ortak olanların en güçlüsü seçilir
            shared = [word for word in keywords if word.lower() in previous]
            if shared:
                return entry["obje"], shared[0]
            # ad paylaşan objeler de aynı konudadır
            common = set(object_tr.lower().split()) & set(entry["obje"].lower().split())
            if common:
                return entry["obje"], common.pop()
        return None

    def summary_line(self) -> str:
        if not self.entries:
            return ""
        objects = " → ".join(entry["obje"] for entry in self.entries)
        return f"Sohbet: {objects}"
