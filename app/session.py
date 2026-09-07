# Numan Bekir Özçelik - 06.09.2026
"""Sohbet bağlamı. Son turların objeleri ve anahtar kelimeleri tutulur.

Yeni tur önceki bir turla aynı aileye giriyorsa iki tur aynı konudadır.
Varsayılan ailede bu yetmez, ortak anahtar kelime ya da ortak ad kelimesi de
gerekir. Bağ kurulunca önceki objenin adı arama niyetine katılabilir ve
ortak kelime paragraf sıralamasında öncelik verir. Oturumda gösterilen
kaynaklar hatırlanır, aynı obje tekrar geldiğinde yeni kaynaklar aranır.
"""

from . import config


class SessionContext:
    def __init__(self, window: int = None):
        self.window = config.CONTEXT_WINDOW if window is None else window
        self.entries = []  # eski turdan yeniye
        self.shown_urls = set()  # oturumda gösterilen kaynak adresleri
        self.object_counts = {}  # obje kaç kez konuşuldu
        self.turn_count = 0  # pencereden bağımsız gerçek tur sayısı

    def add_turn(self, object_tr: str, keywords: list, family: str = ""):
        self.entries.append({"obje": object_tr, "kelimeler": list(keywords), "aile": family})
        self.entries = self.entries[-self.window:]
        self.object_counts[object_tr] = self.object_counts.get(object_tr, 0) + 1
        self.turn_count += 1

    def remember_shown(self, urls):
        self.shown_urls.update(url for url in urls if url)

    def times_seen(self, object_tr: str) -> int:
        return self.object_counts.get(object_tr, 0)

    def last_object(self):
        return self.entries[-1]["obje"] if self.entries else None

    def last_keywords(self) -> list:
        return list(self.entries[-1]["kelimeler"]) if self.entries else []

    def shared_context(self, object_tr: str, keywords: list, family: str = "",
                       default_family: str = "ürün"):
        """Aynı konudaki en yeni önceki turu obje ve ortak kelime olarak döndürür.

        Ortak kelime yoksa ikinci değer None döner. Aynı aile bağ için yeter,
        varsayılan ailede ortak kelime ya da ortak ad kelimesi de gerekir.
        """
        for entry in reversed(self.entries):
            if entry["obje"] == object_tr:
                continue
            previous = {word.lower() for word in entry["kelimeler"]}
            # mevcut turun kelimeleri skor sırasındadır, ortak olanların en güçlüsü seçilir
            shared = [word for word in keywords if word.lower() in previous]
            common_name = set(object_tr.lower().split()) & set(entry["obje"].lower().split())
            same_family = bool(family) and entry.get("aile") == family
            if shared:
                return entry["obje"], shared[0]
            if common_name:
                return entry["obje"], common_name.pop()
            if same_family and family != default_family:
                return entry["obje"], None
        return None

    def chain(self, family: str) -> list:
        """Son turdan geriye, aynı ailede kalan ardışık objelerin adları, eski ilk."""
        names = []
        for entry in reversed(self.entries):
            if not family or entry.get("aile") != family:
                break
            names.append(entry["obje"])
        return list(reversed(names))
