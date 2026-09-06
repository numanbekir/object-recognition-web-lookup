# Numan Bekir Özçelik - 04.09.2026
"""Seçilen cümleleri tek metne dizer.

Sıra tanım, genel bilgi ve detay olarak kurulur. Metin tanım cümlelerinin
kelime çekirdeğine bağlanır, çekirdekle örtüşmeyen cümleler elenir.
Kaynak izlenebilirliği dipnot satırı ve cümle-kaynak eşlemesiyle sağlanır.
"""

from . import config
from .extractor import ContentExtractor

DEFINITION_ENDINGS = ("dır.", "dir.", "dur.", "dür.", "tır.", "tir.", "tur.", "tür.")


class TextComposer:
    def __init__(self):
        self.last_has_definition = False  # metin tanımla mı açılıyor

    def compose(self, sentences: list, object_tr: str, aliases: list = ()) -> tuple:
        """Final metni, kaynak listesini ve cümle-kaynak eşlemesini döndürür.

        aliases objenin sorgudaki eş adlarıdır, tanım çoğu zaman bu adla kurulur.
        """
        self.last_has_definition = False
        if not sentences:
            return "", [], []

        subject_terms = [part.lower()[:5] for part in object_tr.split() if len(part) >= 3]
        subject_terms += [alias.lower()[:5] for alias in aliases if len(alias) >= 3]

        definitions, rest = [], []
        for sentence in sentences:
            lower = sentence.text.lower()
            about_subject = any(term in lower for term in subject_terms)
            if about_subject and sentence.text.endswith(DEFINITION_ENDINGS):
                definitions.append(sentence)
            else:
                rest.append(sentence)

        ordered = self._order(definitions, self._coherent(definitions, rest))
        if len(ordered) < config.MIN_SENTENCES:
            # tema çekirdeği daraltamadıysa eski geniş seçime düşülür
            ordered = self._order(definitions, rest)
        if len(ordered) < config.MIN_SENTENCES:
            return "", [], []

        self.last_has_definition = bool(definitions) and ordered[0] in definitions
        text = " ".join(sentence.text for sentence in ordered)
        sources = []
        for sentence in ordered:
            if sentence.source not in sources:
                sources.append(sentence.source)
        mapping = [{"cümle": s.text, "kaynak": s.source} for s in ordered]
        return text, sources, mapping

    @staticmethod
    def _stems(text: str) -> set:
        # ek toleransı için ilk beş harf karşılaştırılır
        return {word[:5] for word in ContentExtractor._content_words(text)}

    @classmethod
    def _coherent(cls, definitions: list, rest: list) -> list:
        """Tanım çekirdeğiyle en az iki kök paylaşan cümleler."""
        theme = set()
        for sentence in definitions:
            theme |= cls._stems(sentence.text)
        if not theme:
            return rest
        return [sentence for sentence in rest
                if len(cls._stems(sentence.text) & theme) >= 2]

    @staticmethod
    def _order(definitions: list, rest: list) -> list:
        """Önce tanım, sonra genel, sonra sayılı detay dizilir."""
        general = [s for s in rest if not any(ch.isdigit() for ch in s.text)]
        detail = [s for s in rest if any(ch.isdigit() for ch in s.text)]
        # bağlama değen cümleler grup içinde öne gelir, sıralama kararlı
        # olduğu için bağlam yokken arama sırası aynen korunur
        general.sort(key=lambda s: -s.context_hits)
        detail.sort(key=lambda s: -s.context_hits)
        ordered, run_source, run_length = [], None, 0
        for sentence in definitions + general + detail:
            if len(ordered) >= config.MAX_SENTENCES:
                break
            if sentence.source == run_source:
                if run_length >= config.MAX_PER_SOURCE_RUN:
                    continue
                run_length += 1
            else:
                run_source, run_length = sentence.source, 1
            ordered.append(sentence)
        return ordered
