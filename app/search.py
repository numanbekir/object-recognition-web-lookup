# Numan Bekir Özçelik - 04.09.2026
"""Sorguyu kurar ve ddgs ile arar"""


class SearchResult:
    def __init__(self, title: str, url: str):
        self.title = title
        self.url = url


class WebSearcher:
    def build_query(self, object_tr: str, keywords: list, context_terms: list, user_text: str = "") -> str:
        raise NotImplementedError

    def search(self, query: str) -> list:
        # aynı domainden tek sonuç, kalanlar yedek havuzda
        raise NotImplementedError
