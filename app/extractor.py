# Numan Bekir Özçelik - 04.09.2026
"""Sayfaları indirir, işe yarar cümleleri ayıklar.

Kural filtresi, eğitilmiş sınıflandırıcı ve alaka skoru üç ayrı katmandır.
Kalan cümleler kaynaklar arası tekilleştirmeden geçer.
"""

import re
from concurrent.futures import ThreadPoolExecutor

import requests

from . import config

SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+|(?<=[?!])(?=[A-ZÇĞİÖŞÜ])")
MIN_SENTENCE_CHARS = 60
MAX_SENTENCE_CHARS = 400

# pazarlama, navigasyon ve site kalıpları
CTA_PATTERNS = (
    "tıkla", "satın al", "sepet", "üye ol", "abone", "kayıt ol", "giriş yap",
    "çerez", "gizlilik", "kvkk", "indirim", "kampanya", "ücretsiz kargo",
    "hemen al", "sipariş", "stok", "fiyat", " tl", "keşfet", "takip et",
    "paylaş", "yorum yap", "devamını oku", "tüm hakları", "©", "e-posta",
    "bülten", "reklam", "iletişim", "hakkımızda", "web sitemiz", "sitemizde",
    "satılık", "satılan", "satış", "mağaza", "garanti",
    "firma", "kurumsal", "sektör",
    " ilan", ".com", ".net", "www.",
)
# birinci şahıs veya okuyucuya seslenen kalıplar ve ekler
PERSONAL_PATTERNS = (
    "ben ", "benim", "bizim", "bize", "biz ", "sizin", "size ", "sizi ", "sizler",
    "düşünüyorum", "bence", "kanımca",
    "sınız", "siniz", "sunuz", "sünüz", "sanız", "seniz",
    "ınız", "iniz", "unuz", "ünüz",
)
# emir kipiyle biten tarif adımları
IMPERATIVE_ENDINGS = re.compile(
    r"\b\w+(ın|in|un|ün|ınız|iniz|unuz|ünüz|alım|elim)\.$")
# gövdeye yapışan büyük harfli başlık dizisi
TITLE_GLUE = re.compile(
    r"(?:[A-ZÇĞİÖŞÜ][a-zçğıöşü]+\s+){3}[A-ZÇĞİÖŞÜ][a-zçğıöşü]+")
# önceki cümleye yaslanan başlangıçlar tek başına kopuk kalır
DEPENDENT_STARTS = (
    "bu ", "bunlar", "bunun", "buna", "böylece", "ayrıca", "ancak", "ama ",
    "fakat", "yani", "çünkü", "oysa", "üstelik", "o yüzden", "bu yüzden",
    "hatta", "örneğin", "ise ", "de ", "da ",
)

STOPWORDS = {
    "ve", "veya", "ile", "bir", "bu", "şu", "o", "da", "de", "ki", "mi", "mı",
    "mu", "mü", "için", "gibi", "kadar", "çok", "daha", "en", "ama", "fakat",
    "ancak", "ise", "olarak", "olan", "her", "hiç", "ya", "hem", "çünkü",
    "yani", "sonra", "önce", "göre", "kendi", "tüm", "bütün", "bazı", "diğer",
    "aynı", "başka", "olur", "olabilir", "vardır", "yoktur", "ya da",
}


class Sentence:
    def __init__(self, text: str, source: str, score: float = 0.0,
                 context_hits: int = 0):
        self.text = text
        self.source = source  # dipnot ve kayıt için domain
        self.score = score
        self.context_hits = context_hits  # sohbet bağlamına değen kök sayısı


class ContentExtractor:
    def __init__(self):
        self._classifier = None
        self._classifier_checked = False

    # --- sayfa indirme ---

    def fetch_pages(self, results: list) -> list:
        """Açılan sayfaların ana metnini döndürür, açılamayan sessizce atlanır."""
        import trafilatura  # import ağır olduğu için fonksiyon içinde

        def fetch(result):
            try:
                response = requests.get(result.url, timeout=config.PAGE_TIMEOUT,
                                        headers={"User-Agent": "Mozilla/5.0"})
                if response.status_code != 200:
                    return None
                text = trafilatura.extract(response.text)
                if text:
                    # wikipedia dipnot ve düzenleme kalıntıları temizlenir
                    text = re.sub(r"\[[^\]]{0,40}\]", "", text)
                return (result, text) if text else None
            except Exception:
                return None

        with ThreadPoolExecutor(max_workers=len(results) or 1) as pool:
            pages = list(pool.map(fetch, results))
        return [page for page in pages if page]

    # --- cümle seçimi ---

    def select_sentences(self, pages: list, object_tr: str, keywords: list,
                         context_words: list = ()) -> list:
        anchor = object_tr.lower()
        # ek toleransı için kök benzeri karşılaştırma yapılır
        keyword_stems = [word.lower()[:5] for word in keywords if len(word) >= 4]
        # bağlam eşiği aşamaz, yalnız kapıyı geçen cümleler arasında öncelik verir
        context_stems = [word.lower()[:5] for word in context_words if len(word) >= 4]

        selected = []
        for result, text in pages:
            for raw in SENTENCE_SPLIT.split(text):
                sentence = " ".join(raw.split())
                if not self._passes_rules(sentence):
                    continue
                lower = sentence.lower()
                score = self._relevance(lower, anchor, keyword_stems)
                if score <= 0:
                    continue
                if not self._classifier_approves(sentence):
                    continue
                hits = sum(1 for stem in context_stems if stem in lower)
                selected.append(Sentence(sentence, result.domain, score, hits))
        return self._deduplicate(selected)

    def _passes_rules(self, sentence: str) -> bool:
        if not MIN_SENTENCE_CHARS <= len(sentence) <= MAX_SENTENCE_CHARS:
            return False
        if not sentence.endswith("."):  # soru, ünlem ve yarım satırlar elenir
            return False
        if not sentence[0].isupper():
            return False
        if ":" in sentence or "|" in sentence:  # başlık ve menü kalıntıları
            return False
        if IMPERATIVE_ENDINGS.search(sentence):
            return False
        if TITLE_GLUE.search(sentence):
            return False
        lower = sentence.lower()
        if any(pattern in lower for pattern in CTA_PATTERNS):
            return False
        if any(pattern in lower for pattern in PERSONAL_PATTERNS):
            return False
        if any(lower.startswith(start) for start in DEPENDENT_STARTS):
            return False
        return True

    def _relevance(self, lower: str, anchor: str, keyword_stems: list) -> float:
        """Obje adı zorunludur, kelimeler destekler.

        Çapasız cümle kelime kökleriyle içeri giremez. Destek ifadesi
        alakasız bir kavramın sayfasını getirdiğinde o sayfanın cümleleri
        bu kapıda ölür.
        """
        # çok kelimeli adın her parçası ayrı aranır
        anchor_parts = [part[:5] for part in anchor.split() if len(part) >= 3]
        if anchor_parts and not all(part in lower for part in anchor_parts):
            return 0.0
        score = 2.0 if anchor_parts else 0.0
        score += sum(0.5 for stem in keyword_stems if stem in lower)
        return score if score >= 1.0 else 0.0

    def _classifier_approves(self, sentence: str) -> bool:
        # eğitilmiş sınıflandırıcı varsa dolgu cümlelerini eler
        # dolgu kararı yalnız yüksek güvenle verilir
        if not self._classifier_checked:
            self._classifier_checked = True
            if config.SENTENCE_CLASSIFIER_PATH.exists():
                try:
                    import joblib
                    self._classifier = joblib.load(config.SENTENCE_CLASSIFIER_PATH)
                except Exception:
                    self._classifier = None
        if self._classifier is None:
            return True
        try:
            filler_probability = self._classifier.predict_proba([sentence])[0][0]
            return filler_probability < config.CLASSIFIER_FILLER_THRESHOLD
        except Exception:
            return True

    # --- kaynaklar arası tekilleştirme ---

    @staticmethod
    def _content_words(text: str) -> set:
        words = re.findall(r"[a-zçğıöşü]+", text.lower())
        return {word for word in words if len(word) > 2 and word not in STOPWORDS}

    def _deduplicate(self, sentences: list) -> list:
        # kopya içerik yaygın olduğu için aynı bilgi ikinci kez sunulmaz
        kept = []
        kept_words = []
        for sentence in sorted(sentences, key=lambda s: -s.score):
            words = self._content_words(sentence.text)
            if not words:
                continue
            duplicate = False
            for other in kept_words:
                union = len(words | other)
                if union and len(words & other) / union >= config.JACCARD_THRESHOLD:
                    duplicate = True
                    break
            if not duplicate:
                kept.append(sentence)
                kept_words.append(words)
        return kept
