# Numan Bekir Özçelik - 04.09.2026
"""Tespit edilen objeden anahtar kelime üretir.

Dört kaynak tek puan ölçeğinde birleşir. Doğrudan tema haritası, WordNet
üst kavramlarından gelen temalar, WordNet parça ve malzeme ilişkisi ve
arama motoru otomatik tamamlaması. Üst kavram puanı yakınlık ile ayırt
edicilik çarpımıdır. İkincil nesnelerin katkısı yarı ağırlıklıdır, tepe
puanın beşte birinin altında kalan kelimeler elenir. Her kelime kaynağını
ve puanını taşır.
"""

import json
import math
import os

import requests

from . import config

# bu kavramlar her nesnenin tepesinde var, tema olarak değer taşımaz
STOP_CONCEPTS = {
    "entity", "physical_entity", "object", "whole", "artifact", "artefact",
    "matter", "substance", "thing", "unit", "organism", "living_thing",
    "causal_agent", "abstraction", "attribute", "instrumentality",
    "instrumentation", "part", "relation", "commodity", "consumer_goods",
}
MAX_HYPERNYM_DEPTH = 6

# anlam seçiminde önce nesne alanları denenir, madde gibi alanlar yedektir,
# insan ve zaman ve eylem anlamları hiç kullanılmaz
SENSE_TIERS = (
    {"noun.artifact", "noun.animal", "noun.food", "noun.plant", "noun.object"},
    {"noun.substance", "noun.body", "noun.communication", "noun.possession"},
)

SUGGEST_URL = "https://duckduckgo.com/ac/"
SUGGEST_NOISE = ("fiyat", "kdv", "nasıl yazılır", "ne demek", "şikayet", "ekşi",
                 "kampanya", "taksit")
SUGGEST_BAD_STARTS = {"ve", "ile", "mi", "mı"}  # bağlaçla başlayan ek kırıktır


class Keyword:
    def __init__(self, word: str, source: str, score: float):
        self.word = word
        self.source = source
        self.score = score


class KeywordExtractor:
    def __init__(self):
        self.theme_map = {}
        self.names_tr = {}
        self.breadth = {}
        self.vocab_size = 1
        self._wordnet = None
        self._suggest_cache = {}

    def load(self):
        self.theme_map = json.loads(config.THEME_MAP_PATH.read_text(encoding="utf-8"))
        self.names_tr = json.loads(config.OBJECT_NAMES_TR_PATH.read_text(encoding="utf-8"))
        if config.CONCEPT_STATS_PATH.exists():
            stats = json.loads(config.CONCEPT_STATS_PATH.read_text(encoding="utf-8"))
            self.breadth = stats["breadth"]
            self.vocab_size = max(stats["vocab_size"], 1)
        # wordnet verisi proje içindeki nltk_data'ya bir kez indirilir
        try:
            import nltk
            nltk_dir = config.BASE_DIR / "nltk_data"
            nltk_dir.mkdir(exist_ok=True)
            os.chmod(nltk_dir, 0o755)  # grup-yazılabilir dizini nltk reddediyor
            if str(nltk_dir) not in nltk.data.path:
                nltk.data.path.insert(0, str(nltk_dir))
            from nltk.corpus import wordnet
            try:
                wordnet.synsets("dog")
            except LookupError:
                nltk.download("wordnet", download_dir=str(nltk_dir), quiet=True)
                wordnet.synsets("dog")
            self._wordnet = wordnet
        except Exception:
            # internetsiz ilk çalıştırmada uygulama düşmez, temalar haritadan gelir
            self._wordnet = None

    @staticmethod
    def _key(label: str) -> str:
        return label.lower().replace(" ", "_")

    def _top_score(self) -> float:
        return math.log(self.vocab_size)

    def _pick_sense(self, label: str):
        """Nesnenin fiziksel-alan öncelikli, tema üreten anlamını seçer."""
        if self._wordnet is None:
            return None
        synsets = self._wordnet.synsets(self._key(label), pos="n")
        fallback = None
        for tier in SENSE_TIERS:
            for synset in synsets:
                if synset.lexname() not in tier:
                    continue
                if fallback is None:
                    fallback = synset
                if any(c in self.theme_map for c in self._concept_depths(synset)):
                    return synset
        return fallback  # tema yoksa bile meronym için en öncelikli anlam

    def _concept_depths(self, synset) -> dict:
        """Anlamın üst kavramlarını en yakın seviyeleriyle döndürür."""
        depths = {}
        level, seen = [synset], set()
        for depth in range(1, MAX_HYPERNYM_DEPTH + 1):
            next_level = []
            for current in level:
                for parent in current.hypernyms():
                    if parent in seen:
                        continue
                    seen.add(parent)
                    next_level.append(parent)
                    concept = parent.lemmas()[0].name().lower()
                    if concept in STOP_CONCEPTS:
                        continue
                    if concept not in depths or depth < depths[concept]:
                        depths[concept] = depth
            level = next_level
            if not level:
                break
        return depths

    def _collect(self, label: str, factor: float) -> list:
        """Bir nesnenin tüm kaynaklardan puanlı kelimelerini toplar."""
        found = []

        def add(word, source, score):
            found.append(Keyword(word, source, score * factor))

        # doğrudan girdi nesneye özel yazıldığı için tavan puan alır
        for word in self.theme_map.get(self._key(label), []):
            add(word, "girdi", self._top_score())

        sense = self._pick_sense(label)
        if sense is not None:
            # üst kavram temaları yakınlık ve ayırt edicilik çarpımıyla puanlanır
            for concept, depth in self._concept_depths(sense).items():
                for word in self.theme_map.get(concept, []):
                    rarity = math.log(self.vocab_size / max(self.breadth.get(concept, 1), 1))
                    add(word, f"kavram:{concept}", (1.0 / depth) * rarity)
            # parça ve malzeme ilişkisi yalnız baskın nesne için
            if factor == 1.0:
                parts = sense.part_meronyms() + sense.substance_meronyms()
                for part in parts[:2]:
                    name = part.lemmas()[0].name().replace(" ", "_").lower()
                    turkish = self.names_tr.get(name.replace("_", " "))
                    if turkish is None or turkish == self.turkish_name(label):
                        continue
                    # çeviri sözlüğü nesne anlamına göre yazıldı, bileşenin anlamı aynı olmalı
                    if self._pick_sense(name.replace("_", " ")) != part:
                        continue
                    add(turkish, "bileşen", 0.9 * self._top_score())
        return found

    def _fetch_suggestions(self, query: str) -> list:
        """Arama motorunun otomatik tamamlamasından niyet ifadeleri döndürür."""
        response = requests.get(SUGGEST_URL, params={"q": query, "kl": "tr-tr"},
                                timeout=config.SUGGESTION_TIMEOUT,
                                headers={"User-Agent": "Mozilla/5.0"})
        response.raise_for_status()
        return [item["phrase"] for item in response.json()]

    def _intent_keywords(self, turkish: str) -> list:
        """Otomatik tamamlamadan nesne adı sonrası gelen ekleri süzer."""
        if turkish in self._suggest_cache:
            phrases = self._suggest_cache[turkish]
        else:
            try:
                phrases = self._fetch_suggestions(turkish)
            except Exception:
                phrases = []  # ağ sorunu kelime katmanını düşürmez
            self._suggest_cache[turkish] = phrases

        found = []
        for phrase in phrases:
            # kelime sınırı şart, bitişik türevler ek değildir
            if not phrase.startswith(turkish + " "):
                continue
            suffix = phrase[len(turkish):].strip()
            if not suffix or len(suffix.split()) > 2 or any(ch.isdigit() for ch in suffix):
                continue
            if suffix.split()[0] in SUGGEST_BAD_STARTS:
                continue
            if any(noise in suffix for noise in SUGGEST_NOISE):
                continue
            # tam ifade doğal ve aranabilir
            phrase_full = f"{turkish} {suffix}"
            if phrase_full not in found:
                found.append(phrase_full)
            if len(found) >= config.MAX_SUGGESTION_KEYWORDS:
                break
        # dolgu rolündedir, diğer kaynaklar doluyken öne geçemez
        return [Keyword(word, "arama önerisi", 0.25 * self._top_score()) for word in found]

    @staticmethod
    def _rank(candidates: list) -> list:
        """Kelime başına en iyi puanı tutar, tepenin beşte biri altını eler."""
        best = {}
        for keyword in candidates:
            current = best.get(keyword.word)
            if current is None or keyword.score > current.score:
                best[keyword.word] = keyword
        if not best:
            return []
        top = max(item.score for item in best.values())
        kept = [item for item in best.values() if item.score >= 0.2 * top]
        kept.sort(key=lambda item: -item.score)
        return kept

    def extract_scored(self, label: str, secondary_labels: list,
                       use_suggestions: bool = True) -> list:
        """Puanlı ve kaynak etiketli anahtar kelime listesi döndürür.

        Kelimeler önce objeyi anlatmalıdır. Sahnedeki yan nesneler ancak
        baskın nesnenin kelimelerinden slot artarsa listeye girer.
        """
        ranked = self._rank(self._collect(label, 1.0))
        # öneriler puan yarışına girmez, kelime kıtlığında temaların arkasına dolgu olur
        if use_suggestions and len(ranked) < config.SUGGESTION_FILL_THRESHOLD:
            seen = {item.word for item in ranked}
            ranked += [item for item in self._intent_keywords(self.turkish_name(label))
                       if item.word not in seen]
        result = ranked[:config.MAX_KEYWORDS]

        if len(result) < config.MAX_KEYWORDS and secondary_labels:
            seen = {item.word for item in result}
            scene = []
            for secondary in secondary_labels:
                scene += self._collect(secondary, 0.5)
            top = result[0].score if result else 0.0
            for item in self._rank(scene):
                if top and item.score < 0.2 * top:
                    break  # sahne dolgusu da tepe puanın %20 eşiğine tabidir
                if item.word in seen:
                    continue
                result.append(item)
                seen.add(item.word)
                if len(result) >= config.MAX_KEYWORDS:
                    break
        return result

    def extract(self, label: str, secondary_labels: list,
                use_suggestions: bool = True) -> list:
        """Türkçe anahtar kelime listesi döndürür."""
        return [item.word for item in
                self.extract_scored(label, secondary_labels, use_suggestions)]

    def turkish_name(self, label: str) -> str:
        return self.names_tr.get(label, label)
