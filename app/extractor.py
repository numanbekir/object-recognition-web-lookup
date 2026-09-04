# Numan Bekir Özçelik - 04.09.2026
"""Sayfaları indirir, işe yarar cümleleri ayıklar. Duplicate ve pazarlama cümleleri burada ayrıştırılır"""


class Sentence:
    def __init__(self, text: str, source: str, score: float = 0.0):
        self.text = text
        self.source = source
        self.score = score


class ContentExtractor:
    def fetch_pages(self, results: list) -> dict:
        # url -> ana metin; açılamayan sayfa sessizce atlanır
        raise NotImplementedError

    def select_sentences(self, pages: dict, object_tr: str, keywords: list) -> list:
        raise NotImplementedError
