# Numan Bekir Özçelik - 06.09.2026
"""Sayfaları indirir ve objeyle en alakalı paragrafları seçer.

Cümle kolajı yerine bütün paragraf alınır, böylece metin okunabilir kalır.
Aday paragraflar birkaç sade kuralla elenir, sonra obje adı ve anahtar
kelimelerden kurulan sorguya tf-idf kosinüs benzerliğiyle sıralanır. Terim
sıklığı, ters belge sıklığı ve kosinüs hesabı hazır kütüphane olmadan burada
yazılmıştır. Kaynak başına bir paragraf alınır, benzer paragraflar teklenir.
"""

import math
import re
from collections import Counter
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
                  "gizlilik politikası", "tüm hakları", "sitemiz", "web sitemiz",
                  # birinci şahıs blog anlatısı bilgi değil deneyimdir
                  "yollardayım", "kullanıyorum", "eminim", "bence", "benim ", "ben de")
# tarif ve soru-cevap sitelerinin bilgi taşımayan kalıp cümleleri kırpılır
TAIL_PATTERNS = re.compile(
    r"\s*(Peki[;,]?\s[^.!?]*[.!?]|İşte[^.!?]*\.{2,}|Afiyet olsun!?|Hadi [^.!?]*[.!?])\s*$")
LEAD_PATTERNS = re.compile(r"^(C|Cevap|Soru|S|Sonuç|Özetle|Not)\s*:\s*")


class Passage:
    def __init__(self, text: str, source: str, url: str, score: float = 0.0):
        self.text = text
        self.source = source  # kaynak domain
        self.url = url
        self.score = score


def stems(text: str) -> list:
    return [word[:STEM_LENGTH] for word in WORD.findall(text.lower())
            if len(word) > 2 and word not in STOPWORDS]


def anchor_terms(object_tr: str) -> list:
    """Paragrafın objeden söz etmesi için aranacak ifadeler.

    Çok kelimeli adda her kök ayrı aranır. Adda iki harfli kelime varsa kökler
    tek başına ayırt edici olmadığından bitişik ifade aranır.
    """
    words = WORD.findall(object_tr.lower())
    if any(len(word) <= 2 for word in words):
        return [" ".join(word[:STEM_LENGTH] for word in words)]
    return [word[:STEM_LENGTH] for word in words]


def cosine(a: dict, b: dict) -> float:
    """İki seyrek vektörün kosinüs benzerliği, boş vektörde sıfır."""
    dot = sum(weight * b.get(token, 0.0) for token, weight in a.items())
    norm_a = math.sqrt(sum(w * w for w in a.values()))
    norm_b = math.sqrt(sum(w * w for w in b.values()))
    return dot / (norm_a * norm_b) if norm_a and norm_b else 0.0


class ContentExtractor:
    def __init__(self):
        self.html = {}  # ham html, yapı çıkarımı için

    # sayfa indirme

    def fetch_pages(self, results: list) -> list:
        """Sonuç ve ana metin çiftleri döndürür, açılamayan sayfa sessizce atlanır."""
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
                    self.html[result.url] = response.text
                return (result, text) if text else None
            except Exception:
                return None

        with ThreadPoolExecutor(max_workers=len(results) or 1) as pool:
            pages = list(pool.map(fetch, results))
        return [page for page in pages if page]

    # paragraf seçimi

    def select_passages(self, pages: list, object_tr: str, keywords: list,
                        context_words: list = (), limit: int = None,
                        exclude_urls: set = frozenset(), hint_stems: list = (),
                        min_hint_hits: int = 0, min_score: float = None,
                        exclude_texts: set = frozenset()) -> list:
        """Bloklar için ipucu kökleri verilir. Paragraf en az istenen sayıda farklı açı
        kökü içermeli ve sorguya en az alt eşik kadar benzemeli, aksi halde blok boş kalır
        """
        limit = config.MAX_PASSAGES if limit is None else limit
        min_score = config.MIN_SIMILARITY if min_score is None else min_score
        anchor = anchor_terms(object_tr)
        candidates = []
        for result, text in pages:
            if result.url in exclude_urls:  # oturumda gösterilmiş sayfa tekrar gelmez
                continue
            for raw in text.split("\n"):
                paragraph = self.clean(" ".join(raw.split()))
                if paragraph in exclude_texts or not self._passes_rules(paragraph, anchor):
                    continue
                lower = paragraph.lower()
                hits = len({stem for stem in hint_stems if stem in lower})
                if hits < min_hint_hits:
                    continue
                candidates.append(Passage(paragraph, result.domain, result.url))
        if not candidates:
            return []

        query = " ".join([object_tr, *keywords, *context_words])
        for passage, score in zip(candidates, self._similarity(query, candidates)):
            passage.score = score
        return self._pick(sorted(candidates, key=lambda p: -p.score), limit, min_score)

    @staticmethod
    def clean(paragraph: str) -> str:
        """Baştaki soru-cevap öneki ve sondaki kalıp cümleler atılır"""
        paragraph = LEAD_PATTERNS.sub("", paragraph)
        previous = None
        while previous != paragraph:  # art arda birkaç kalıp olabilir
            previous, paragraph = paragraph, TAIL_PATTERNS.sub("", paragraph)
        return paragraph.strip()

    @staticmethod
    def _passes_rules(paragraph: str, anchor: list) -> bool:
        if not config.MIN_PASSAGE_CHARS <= len(paragraph) <= config.MAX_PASSAGE_CHARS:
            return False
        if not paragraph.endswith(".") or paragraph.endswith(".."):  # yarım ve kesik satırlar
            return False
        if not paragraph[0].isupper():  # madde işareti, tarih ve başlık artıkları
            return False
        if paragraph.count("?") >= 3:  # soru yığını girişleri bilgi vermez
            return False
        lower = paragraph.lower()
        if not TURKISH_CHARS.intersection(lower):  # bozuk kodlama
            return False
        # Türkçe metin bağlaç ve edatlarını mutlaka kullanır, yabancı dil burada elenir
        if len(STOPWORDS.intersection(WORD.findall(lower))) < 2:
            return False
        if any(noise in lower for noise in NOISE_PATTERNS):
            return False
        # paragraf objeden söz etmeli, her kök ayrı ya da bitişik ifade
        return all(term in lower for term in anchor)

    @staticmethod
    def _similarity(query: str, passages: list) -> list:
        """Sorgu ile her paragraf arasındaki tf-idf kosinüs benzerliği
        Nadir kökler benzerliğe daha çok katkı verir, böylece her paragrafta geçen
        genel kelimeler sıralamayı belirlemez.
        """
        documents = [stems(p.text) for p in passages]
        document_frequency = Counter()
        for tokens in documents:
            document_frequency.update(set(tokens))
        total = len(documents)

        def idf(token):
            return math.log((total + 1) / (document_frequency[token] + 1)) + 1

        def vector(tokens):
            counts = Counter(tokens)
            length = len(tokens) or 1
            return {token: (count / length) * idf(token) for token, count in counts.items()}

        query_vector = vector(stems(query))
        return [cosine(query_vector, vector(tokens)) for tokens in documents]

    @staticmethod
    def _pick(ranked: list, limit: int, min_score: float) -> list:
        """Kaynak başına bir paragraf alır, aynı bilgiyi tekrar edenleri atlar."""
        chosen, used_sources, chosen_stems = [], set(), []
        for passage in ranked:
            if passage.score < min_score:
                break  # liste sıralı, gerisi daha da alakasız
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
