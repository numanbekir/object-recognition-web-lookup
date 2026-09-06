# Numan Bekir Özçelik - 04.09.2026
"""Sorguyu kurar ve ddgs ile arar.

    sorgu = objenin türkçe adı + destek kelimesi + bağlam + kullanıcı metni
    sonuçlar süzülür, domain başına tek sayfa alınır
"""

from urllib.parse import urlparse

from . import config

# içerik sayfası vermeyen alanlar
DOMAIN_BLACKLIST = (
    "pinterest.", "instagram.", "facebook.", "twitter.", "x.com", "tiktok.",
    "youtube.", "youtu.be", "linkedin.", "reddit.", "pbs.twimg",
    "trendyol.", "hepsiburada.", "n11.", "amazon.", "teknosa.", "mediamarkt.",
    "vatanbilgisayar.", "gittigidiyor.", "akakce.", "cimri.", "epey.",
    "sahibinden.", "letgo.", "dolap.", "ciceksepeti.",
)


class SearchResult:
    def __init__(self, title: str, url: str):
        self.title = title
        self.url = url
        self.domain = (urlparse(url).hostname or "").removeprefix("www.")


class WebSearcher:
    def support_term(self, object_tr: str, keywords: list) -> str:
        """Sorguya eşlik edecek tek destek kelimesini seçer, çapayı içerenler atlanır."""
        for word in keywords:
            if object_tr in word or word in object_tr:
                continue
            return word
        return ""

    def build_query(self, object_tr: str, keywords: list,
                    context_terms: list = (), user_text: str = "") -> str:
        """Objenin adı sorgudan hiç çıkmaz."""
        # her ek kelime aramayı kendi alanına çeker, tek destek yeterli
        terms = [object_tr]
        for word in keywords:
            if object_tr in word or any(word in term for term in terms):
                continue
            terms.append(word)
            if len(terms) >= 2:
                break
        for term in context_terms:
            if term not in terms:
                terms.append(term)
        if user_text:
            terms.append(user_text)
        return " ".join(terms)

    def search(self, query: str) -> list:
        """Süzülmüş sonuç listesi döndürür."""
        from ddgs import DDGS  # import ağır olduğu için fonksiyon içinde

        rows = None
        for attempt in (1, 2):  # geçici hataya ikinci deneme
            try:
                rows = DDGS().text(query, region=config.SEARCH_REGION,
                                   max_results=config.SEARCH_RESULT_COUNT)
                break
            except Exception:
                if attempt == 2:
                    raise

        results, seen_domains = [], set()
        for row in rows or []:
            url = row.get("href") or ""
            result = SearchResult(row.get("title") or "", url)
            if not url or not result.domain:
                continue
            if url.lower().split("?")[0].endswith(".pdf"):
                continue
            if any(bad in result.domain for bad in DOMAIN_BLACKLIST):
                continue
            if result.domain in seen_domains:  # domain başına bir sayfa
                continue
            seen_domains.add(result.domain)
            results.append(result)
        return results
