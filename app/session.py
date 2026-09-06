# Numan Bekir Özçelik - 06.09.2026
"""Sohbet bağlamını sönümlenen bir konu profili olarak tutar.

Sabit pencere yok. Her başarılı turda eski ağırlıklar çarpılarak azalır,
yeni tur tam ağırlıkla girer, tabanın altına düşen kayıt silinir. Yerleşik
konu birikir, tek seferlik sapma söner. Bağlama yalnız başarılı turlar
girer ve kullanım kesişim kanıtına bağlıdır. Arayüz ham profili değil
damıtılmış özeti gösterir.
"""

from . import config


def _stems(words) -> set:
    # ek toleransı için ilk beş harf karşılaştırılır
    return {word.lower()[:5] for word in words if len(word) >= 3}


class SessionContext:
    def __init__(self, decay: float = None, floor: float = None):
        self.decay = config.CONTEXT_DECAY if decay is None else decay
        self.floor = config.CONTEXT_FLOOR if floor is None else floor
        self.entries = []  # eski -> yeni

    def add_turn(self, object_tr: str, keywords: list):
        for entry in self.entries:
            entry["agirlik"] *= self.decay
        # aynı obje tazelenir, sönen kayıtlar budanır
        self.entries = [entry for entry in self.entries
                        if entry["obje"] != object_tr and entry["agirlik"] >= self.floor]
        self.entries.append({"obje": object_tr, "kelimeler": list(keywords),
                             "agirlik": 1.0})

    def last_object(self):
        return self.entries[-1]["obje"] if self.entries else None

    def last_keywords(self) -> list:
        return list(self.entries[-1]["kelimeler"]) if self.entries else []

    def related_entries(self, current_object: str, current_keywords: list) -> list:
        """Mevcut turla kelime kesişimi olan kayıtlar, ağırlık sırasıyla."""
        current = _stems(current_keywords)
        related = [entry for entry in self.entries
                   if entry["obje"] != current_object
                   and current & _stems(entry["kelimeler"])]
        return sorted(related, key=lambda entry: -entry["agirlik"])

    @staticmethod
    def is_sibling(name_a: str, name_b: str) -> bool:
        """Kök paylaşan adları aynı isim ailesinden sayar.

        Kardeş isim sorguda bir şey ayrıştırmaz ve aramayı eski objeye çeker.
        Bu yüzden sorguya girmez, bağlam yalnız cümle seçiminde bonus verir.
        """
        return bool(_stems(name_a.split()) & _stems(name_b.split()))

    def topic(self):
        """En az iki objenin desteklediği en ağır kökü döndürür.

        Etiket uydurulmaz. Kökün profildeki en kısa yüzey biçimi seçilir,
        obje adları etiket olamaz.
        """
        support = {}
        for entry in self.entries:
            stem_words = {}
            for word in entry["kelimeler"]:
                if len(word) >= 3:
                    stem_words.setdefault(word.lower()[:5], set()).add(word)
            for stem, words in stem_words.items():
                info = support.setdefault(
                    stem, {"agirlik": 0.0, "objeler": set(), "kelimeler": set()})
                info["agirlik"] += entry["agirlik"]
                info["objeler"].add(entry["obje"])
                info["kelimeler"] |= words
        name_stems = _stems(" ".join(e["obje"] for e in self.entries).split())
        candidates = [(stem, info) for stem, info in support.items()
                      if len(info["objeler"]) >= 2 and stem not in name_stems]
        if not candidates:
            return None
        stem, info = max(candidates, key=lambda item: item[1]["agirlik"])
        return min(info["kelimeler"], key=len), info["agirlik"]

    def summary_line(self) -> str:
        # durum satırı iç durumu değil damıtılmış özeti gösterir
        if not self.entries:
            return ""
        parts = []
        top = self.topic()
        if top is not None:
            parts.append(f"Konu: {top[0]}")
        parts.append(f"Son nesne: {self.entries[-1]['obje']}")
        return " · ".join(parts)

    def debug_line(self) -> str:
        weights = ", ".join(f"{entry['obje']} {entry['agirlik']:.2f}"
                            for entry in reversed(self.entries))
        top = self.topic()
        return weights + (f" · konu: {top[0]} ({top[1]:.2f})" if top else "")
