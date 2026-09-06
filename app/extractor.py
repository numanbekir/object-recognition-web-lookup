# Numan Bekir Özçelik - 06.09.2026
"""Sayfaları indirir, objeyle en alakalı paragrafları seçer.

Cümle cümle kolaj yerine bütün paragraf alınır, böylece metin okunabilir
kalır. Aday paragraflar birkaç sade kuralla elenir, sonra objenin adı ve
anahtar kelimelerden kurulan sorguya TF-IDF kosinüs benzerliğiyle
sıralanır. Kaynak başına bir paragraf, benzer paragraflar teklenir.
"""

import re
from concurrent.futures import ThreadPoolExecutor

import requests

from . import config

TURKISH_CHARS = set("çğıöşü")
WORD = re.compile(r"[a-zçğıöşüâîû]+")
STEM_LENGTH = 5  # Türkçe ekleri hoş görmek için kelimelerin ilk beş harfi kıyaslanır
STOPWORDS = {
    "ve", "veya", "ile", "bir", "bu", "şu", "da", "de", "ki", "mi", "mı", "mu", "mü",
    "için", "gibi", "kadar", "çok", "daha", "en", "ama", "ancak", "ise", "olarak",
    "olan", "her", "ya", "hem", "çünkü", "yani", "sonra", "önce", "göre", "kendi",
    "tüm", "bazı", "diğer", "aynı", "başka", "olur", "vardır",
}
# site kalıntısı olduğu kesin olan birkaç işaret, gerisini alaka sıralaması halleder
NOISE_PATTERNS = ("çerez", "kvkk", "sepet", "giriş yap", "üye ol", "©", "tıkla",
                  "gizlilik politikası", "tüm hakları", "sitemiz", "web sitemiz")


class Passage:
    def __init__(self, text: str, source: str, url: str, score: float = 0.0):
        self.text = text
        self.source = source  # kaynak domain
        self.url = url
        self.score = score


def stems(text: str) -> list:
    return [word[:STEM_LENGTH] for word in WORD.findall(text.lower())
            if len(word) > 2 and word not in STOPWORDS]


class ContentExtractor:
    # --- sayfa indirme ---

    def fetch_pages(self, results: list) -> list:
        """(sonuç, ana metin) çiftleri döndürür, açılamayan sayfa sessizce atlanır."""
        import trafilatura  # import ağır olduğu için fonksiyon içinde

        def fetch(result):
            try:
                response = requests.get(result.url, timeout=config.PAGE_TIMEOUT,
                                        headers={"User-Agent": "Mozilla/5.0"})
                if response.status_code != 200:
                    return None
                # ham bayt verilir, karakter kodlamasını trafilatura tespit eder
                text = trafilatura.extract(response.content, include_comments=False)
                if text:
                    text = re.sub(r"\[\d+\]", "", text)  # dipnot kalıntıları
                return (result, text) if text else None
            except Exception:
                return None

        with ThreadPoolExecutor(max_workers=len(results) or 1) as pool:
            pages = list(pool.map(fetch, results))
        return [page for page in pages if page]

    # --- paragraf seçimi ---

    def select_passages(self, pages: list, object_tr: str, keywords: list,
                        context_words: list = (), limit: int = None) -> list:
        limit = config.MAX_PASSAGES if limit is None else limit
        anchor_stems = stems(object_tr)
        candidates = []
        for result, text in pages:
            for raw in text.split("\n"):
                paragraph = " ".join(raw.split())
                if self._passes_rules(paragraph, anchor_stems):
                    candidates.append(Passage(paragraph, result.domain, result.url))
        if not candidates:
            return []

        query = " ".join([object_tr, *keywords, *context_words])
        for passage, score in zip(candidates, self._similarity(query, candidates)):
            passage.score = score
        return self._pick(sorted(candidates, key=lambda p: -p.score), limit)

    @staticmethod
    def _passes_rules(paragraph: str, anchor_stems: list) -> bool:
        if not config.MIN_PASSAGE_CHARS <= len(paragraph) <= config.MAX_PASSAGE_CHARS:
            return False
        if not paragraph.endswith((".", "!", "?")):  # yarım kalmış satırlar
            return False
        if not paragraph[0].isupper():  # madde işareti, tarih ve başlık artıkları
            return False
        if paragraph.count("?") >= 3:  # soru yığını SEO girişleri bilgi vermez
            return False
        lower = paragraph.lower()
        if not TURKISH_CHARS.intersection(lower):  # bozuk kodlama
            return False
        # Türkçe metin bağlaç ve edatlarını mutlaka kullanır, yabancı dil burada elenir
        if len(STOPWORDS.intersection(WORD.findall(lower))) < 2:
            return False
        if any(noise in lower for noise in NOISE_PATTERNS):
            return False
        # paragraf objeden söz etmeli, çok kelimeli adın bir parçası yeter
        return any(stem in lower for stem in anchor_stems)

    @staticmethod
    def _similarity(query: str, passages: list) -> list:
        """Sorgu ile her paragraf arasındaki TF-IDF kosinüs benzerliği."""
        from sklearn.feature_extraction.text import TfidfVectorizer
        from sklearn.metrics.pairwise import cosine_similarity

        vectorizer = TfidfVectorizer(analyzer=stems)
        matrix = vectorizer.fit_transform([p.text for p in passages])
        query_vector = vectorizer.transform([query])
        return cosine_similarity(query_vector, matrix)[0].tolist()

    @staticmethod
    def _pick(ranked: list, limit: int) -> list:
        """Kaynak başına bir paragraf alır, aynı bilgiyi tekrar edenleri atlar."""
        chosen, used_sources, chosen_stems = [], set(), []
        for passage in ranked:
            if passage.source in used_sources:
                continue
            words = set(stems(passage.text))
            if any(len(words & other) / len(words | other) >= config.JACCARD_THRESHOLD
                   for other in chosen_stems if words | other):
                continue
            chosen.append(passage)
            used_sources.add(passage.source)
            chosen_stems.append(words)
            if len(chosen) >= limit:
                break
        return chosen
