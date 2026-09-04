# Numan Bekir Özçelik - 04.09.2026
"""Tespit edilen objeden anahtar kelime üretir. WordNet ile üst kavramlar, tema haritası + görseldeki ana nesne dışındaki diğer nesneler"""


class KeywordExtractor:
    def __init__(self):
        self.theme_map = {}
        self.names_tr = {}

    def load(self):
        raise NotImplementedError

    def extract(self, label: str, secondary_labels: list) -> list:
        """Türkçe anahtar kelime listesi döndürür."""
        raise NotImplementedError

    def turkish_name(self, label: str) -> str:
        raise NotImplementedError
