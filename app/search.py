# Numan Bekir Özçelik - 06.09.2026
"""Web araması: Vikipedi tanımı ve DuckDuckGo sonuçları.

    sorgu = objenin Türkçe adı [+ bağlam kelimesi] [+ kullanıcı metni]
    Vikipedi her turda tanım paragrafı sağlar, arama sonuçları detay getirir.
"""

import re
from urllib.parse import urlparse

import requests

from . import config

WIKI_API = "https://tr.wikipedia.org/w/api.php"
USER_AGENT = "GoruntuluSohbet/1.0 (ogrenci projesi)"

# içerik sayfası vermeyen alanlar
DOMAIN_BLACKLIST = (
    "wikipedia.org",  # Vikipedi ayrı kanaldan alınır, ikinci kez gelmesin
    "grokipedia.",  # yapay zeka üretimi, çoğu zaman İngilizce
    "pinterest.", "instagram.", "facebook.", "twitter.", "x.com", "tiktok.",
    "youtube.", "youtu.be", "linkedin.", "reddit.",
    "trendyol.", "hepsiburada.", "n11.", "amazon.", "sahibinden.", "letgo.",
)


class SearchResult:
    def __init__(self, title: str, url: str):
        self.title = title
        self.url = url
        self.domain = (urlparse(url).hostname or "").removeprefix("www.")


class WebSearcher:
    @staticmethod
    def build_query(object_tr: str, context_word: str = "", user_text: str = "") -> str:
        """Objenin adı sorgudan hiç çıkmaz, bağlam ve kullanıcı metni eklenir."""
        terms = [object_tr]
        if context_word and context_word.lower() not in object_tr.lower():
            terms.append(context_word)
        if user_text:
            terms.append(user_text)
        return " ".join(terms)

    def search(self, query: str) -> list:
        """Süzülmüş sonuç listesi döndürür, servis hatası yukarı fırlar."""
        from ddgs import DDGS  # import ağır olduğu için fonksiyon içinde

        rows = DDGS().text(query, region=config.SEARCH_REGION,
                           max_results=config.SEARCH_RESULT_COUNT)
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

    def wikipedia(self, object_tr: str):
        """Türkçe Vikipedi'den giriş paragrafını (metin, url) olarak döndürür, yoksa None.

        Önce tam başlık denenir (yönlendirmeler izlenir), bulunamazsa tam
        metin araması yapılır. Anlam ayrımı sayfaları ve objeden söz etmeyen
        sayfalar atlanır.
        """
        base = {"action": "query", "prop": "extracts|info", "exintro": 1, "explaintext": 1,
                "inprop": "url", "redirects": 1, "format": "json"}
        by_title = {**base, "titles": tr_capitalize(object_tr)}
        by_search = {**base, "generator": "search", "gsrsearch": object_tr, "gsrlimit": 3}
        anchor = object_tr.lower()[:5]
        for params in (by_title, by_search):
            for page in self._wiki_pages(params):
                extract = (page.get("extract") or "").strip()
                if not extract or "anlamlara gelebilir" in extract or "anlamına gelebilir" in extract:
                    continue
                first = re.sub(r"\[\d+\]", "", extract.split("\n")[0].strip())  # dipnot kalıntıları
                title = page.get("title", "").lower()
                # arama yedeğinde başlık objeyle başlamalı, "Binlik Demlik" gibi albüm
                # ve eser sayfaları objeden söz etse de tanım vermez
                if len(first) < 40 or anchor not in first.lower() or not title.startswith(anchor):
                    continue
                return first[:config.MAX_PASSAGE_CHARS], page.get("fullurl", "")
        return None

    @staticmethod
    def _wiki_pages(params: dict) -> list:
        try:
            response = requests.get(WIKI_API, params=params, timeout=config.WIKI_TIMEOUT,
                                    headers={"User-Agent": USER_AGENT})
            response.raise_for_status()
            pages = response.json().get("query", {}).get("pages", {})
        except Exception:
            return []
        # arama sırası korunur, eksik sayfalar (negatif id) elenir
        return [page for page in sorted(pages.values(), key=lambda p: p.get("index", 99))
                if "missing" not in page]


def tr_capitalize(text: str) -> str:
    # python'un capitalize'ı türkçe i'yi I yapar, İ olmalı
    if not text:
        return text
    first = "İ" if text[0] == "i" else text[0].upper()
    return first + text[1:]
