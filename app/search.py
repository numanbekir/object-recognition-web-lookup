# Numan Bekir Özçelik - 06.09.2026
"""Web araması. Vikipedi tanımı ve arama motoru sonuçları.

Vikipedi her turda tanım paragrafı sağlar, arama sonuçları ayrıntı getirir.
"""

import re
import time
from urllib.parse import urlparse

import requests

from . import config

WIKI_API = "https://tr.wikipedia.org/w/api.php"
USER_AGENT = "GoruntuluSohbet/1.0 (ogrenci projesi)"

# sonuç başlığındaki ipuçları, bilgi sayfaları öne ve satış sayfaları arkaya alınır
INFORMATIVE_HINTS = ("nedir", "tarihçe", "tarihi", "nasıl", "özellik", "hakkında",
                     "türleri", "çeşitleri", "fayda", "tarif", "rehber", "bilgi")
COMMERCIAL_HINTS = ("fiyat", "modelleri", "satın al", "indirim", "kampanya", "ucuz",
                    "sipariş", "en iyi", "en ucuz", "mağaza", "outlet", "stok")

# içerik sayfası vermeyen alanlar
DOMAIN_BLACKLIST = (
    "wikipedia.org",  # Vikipedi ayrı kanaldan alınır, ikinci kez gelmesin
    "bing.com", "google.", "yahoo.com", "duckduckgo.com",  # arama motoru yönlendirme adresleri
    "grokipedia.",  #çoğu zaman İngilizce
    "pinterest.", "instagram.", "facebook.", "twitter.", "x.com", "tiktok.",
    "youtube.", "youtu.be", "linkedin.", "reddit.", "translate.google.",
    "trendyol.", "hepsiburada.", "n11.", "amazon.", "sahibinden.", "letgo.",
    # sözlük ve çeviri siteleri kelimeyi anlatmaz
    "nedirnedemek.", "anlami-nedir.", "seslisozluk.", "tureng.", "bab.la",
    "thefreedictionary.", "wiktionary.", "eksisozluk.", "turkcenedemek.", "sozluk.",
)


class SearchResult:
    def __init__(self, title: str, url: str):
        self.title = title
        self.url = url
        self.domain = (urlparse(url).hostname or "").removeprefix("www.")

    def priority(self) -> int:
        """Başlıktaki ipuçlarından sayfanın bilgi mi satış mı olduğu kestirilir"""
        lower = self.title.lower()
        score = sum(1 for hint in INFORMATIVE_HINTS if hint in lower)
        score -= sum(1 for hint in COMMERCIAL_HINTS if hint in lower)
        return score


class WebSearcher:
    @staticmethod
    def build_query(object_tr: str, context_word: str = "", user_text: str = "") -> str:
        """Objenin adı sorgudan hiç çıkmaz, bağlam ve kullanıcı metni eklenir"""
        terms = [object_tr]
        if context_word and context_word.lower() not in object_tr.lower():
            terms.append(context_word)
        if user_text:
            terms.append(user_text)
        return " ".join(terms)

    def search(self, query: str) -> list:
        """Süzülmüş sonuç listesi döndürür, servis hatası yukarı fırlar."""
        from ddgs import DDGS  # import ağır olduğu için fonksiyon içinde

        rows = None
        for attempt in (1, 2):  # servis art arda sorguda geçici hata verebiliyor
            try:
                rows = DDGS().text(query, region=config.SEARCH_REGION,
                                   max_results=config.SEARCH_RESULT_COUNT)
                break
            except Exception:
                if attempt == 2:
                    raise
                time.sleep(2)
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
        # kararlı sıralama, eşit öncelikte arama motorunun sırası korunur
        return sorted(results, key=lambda r: -r.priority())

    def wikipedia(self, object_tr: str):
        """Türkçe Vikipedi giriş paragrafını metin ve adres olarak döndürür, yoksa none

        Önce tam başlık denenir, bulunamazsa tam metin araması yapılır. Anlam
        ayrımı sayfaları ve objeden söz etmeyen sayfalar atlanır.
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
                paragraphs = [re.sub(r"\[\d+\]", "", p).strip()  # dipnot kalıntıları
                              for p in extract.split("\n") if p.strip()]
                first = paragraphs[0] if paragraphs else ""
                title = page.get("title", "").lower()
                # arama yedeğinde başlık objeyle başlamalı, albüm ve eser
                # sayfaları objeden söz etse de tanım vermez
                if len(first) < 40 or anchor not in first.lower() or not title.startswith(anchor):
                    continue
                # tek cümlelik giriş tanım sayılmaz, giriş bölümü sınıra kadar sürdürülür
                text = first
                for paragraph in paragraphs[1:]:
                    if len(text) >= config.WIKI_MIN_CHARS:
                        break
                    if len(text) + len(paragraph) + 1 <= config.MAX_PASSAGE_CHARS:
                        text += " " + paragraph
                return text[:config.MAX_PASSAGE_CHARS], page.get("fullurl", "")
        return None

    def wikipedia_sections(self, title: str) -> list:
        """Sayfanın bölümlerini başlık ve metin sözlükleri olarak tek istekle döndürür.

        Bölüm metni ilk paragraftır. Kaynakça ve galeri gibi bölümler atlanır.
        Tarihçe, türleri ve özellikler gibi bölümler bilgi bloklarını besler.
        """
        if not title:
            return []
        try:
            response = requests.get(WIKI_API, params={"action": "parse", "page": title,
                                                      "prop": "text", "format": "json",
                                                      "redirects": 1},
                                    timeout=config.WIKI_TIMEOUT, headers={"User-Agent": USER_AGENT})
            response.raise_for_status()
            html = response.json()["parse"]["text"]["*"]
        except Exception:
            return []
        return parse_wiki_sections(html)

    @staticmethod
    def _wiki_pages(params: dict) -> list:
        try:
            response = requests.get(WIKI_API, params=params, timeout=config.WIKI_TIMEOUT,
                                    headers={"User-Agent": USER_AGENT})
            response.raise_for_status()
            pages = response.json().get("query", {}).get("pages", {})
        except Exception:
            return []
        # arama sırası korunur, eksik sayfalar elenir
        return [page for page in sorted(pages.values(), key=lambda p: p.get("index", 99))
                if "missing" not in page]


WIKI_SKIP_SECTIONS = ("kaynakça", "ayrıca bakınız", "dış bağlantılar", "galeri", "dipnot",
                      "notlar", "kaynaklar", "bibliyografya", "konuyla ilgili")


def parse_wiki_sections(html: str) -> list:
    """Vikipedi sayfa html içeriğinden başlık ve ilk paragraf çiftlerini çıkarır."""
    import lxml.html
    try:
        document = lxml.html.fromstring(html)
    except Exception:
        return []
    sections = []
    for heading in document.iter("h2", "h3"):
        title = " ".join(heading.text_content().split()).split("[")[0].strip()
        if not title or any(skip in title.lower() for skip in WIKI_SKIP_SECTIONS):
            continue
        node, paragraph, hops = heading.getparent() if heading.getparent().tag == "div" else heading, "", 0
        sibling = node.getnext()
        while sibling is not None and hops < 8 and not paragraph:
            if sibling.tag in ("h2", "h3") or (sibling.tag == "div" and sibling.find("h2") is not None):
                break
            if sibling.tag == "p":
                text = re.sub(r"\[\d+\]", "", " ".join(sibling.text_content().split()))
                if len(text) >= 100:
                    paragraph = text[:config.MAX_PASSAGE_CHARS]
            sibling = sibling.getnext()
            hops += 1
        if paragraph:
            sections.append({"baslik": title, "metin": paragraph})
    return sections


def tr_capitalize(text: str) -> str:
    # capitalize türkçe i harfini I yapar, İ olması gerekir
    if not text:
        return text
    first = "İ" if text[0] == "i" else text[0].upper()
    return first + text[1:]
