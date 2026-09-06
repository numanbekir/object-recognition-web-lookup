# Numan Bekir Özçelik - 06.09.2026
"""Görüntüden obje adını ve anahtar kelimeleri çıkarır.

Tek model kullanılır. Görüntü ve metin aynı vektör uzayına kodlandığı için
sınıflandırma, önceden belirlenmiş isim listeleriyle kosinüs benzerliği
hesaplanarak sıfır atışla yapılır. Eğitim yoktur, sınıf listesi kod dışında
json dosyalarında durur ve istenildiği gibi büyütülür.

Görüntü kodlayıcıdan çıkan vektör iki listeyle karşılaştırılır. Obje listesi
kimlik sorusuna, tema listesi bağlam sorusuna cevap verir.

Kapalı kümeli detektörler kapsam dışındaki objede sessiz kalır ya da yanlış
sınıfa zorlar. Açık dağarcıklı detektörler büyük listede skor seyrelmesi
yaşar ve konum bilgisi bu görevde gerekmez. Bu model yüz milyonlarca görüntü
ve metin çiftiyle eğitildiğinden binlerce isim arasında ayrım yapabilir ve
aynı öznitelik vektörü hem obje adını hem temaları verir.
"""

import hashlib
import json
from pathlib import Path

import requests

from . import config

CLIP_URL = ("https://openaipublic.azureedge.net/clip/models/"
            "40d365715913c9da98579312b702a82c18be219cc2a73407c4526f58eba950af/ViT-B-32.pt")
# birden çok kalıbın ortalaması tek kalıba göre daha kararlı skor verir
OBJECT_PROMPTS = ("a photo of a {}.", "a close-up photo of a {}.")
THEME_PROMPTS = ("a photo of {}.", "a photo related to {}.")
LOGIT_SCALE = 100.0  # modelin eğitimde öğrendiği sıcaklık değeri


class Prediction:
    def __init__(self, label: str, name_tr: str, confidence: float, alternatives: list):
        self.label = label  # İngilizce dağarcık adı
        self.name_tr = name_tr
        self.confidence = confidence
        self.alternatives = alternatives  # türkçe ad ve güven çiftleri


class Keyword:
    def __init__(self, word: str, theme: str, score: float):
        self.word = word
        self.theme = theme  # kelimeyi getiren tema
        self.score = score


class VisionModel:
    def __init__(self):
        self.names_tr = {}
        self.themes = {}
        self.labels = []
        self.theme_keys = []
        self.vocab_size = 0
        self._model = None
        self._preprocess = None
        self._object_features = None
        self._theme_features = None

    # hazırlık

    @staticmethod
    def _clip_cache_path() -> Path:
        # clip kütüphanesi ağırlığı bu klasörde arar
        return Path.home() / ".cache" / "clip" / "ViT-B-32.pt"

    def _load_vocabularies(self):
        self.names_tr = json.loads(config.OBJECT_NAMES_TR_PATH.read_text(encoding="utf-8"))
        self.themes = json.loads(config.THEME_MAP_PATH.read_text(encoding="utf-8"))
        self.labels = sorted(self.names_tr)
        self.theme_keys = sorted(self.themes)
        self.vocab_size = len(self.labels)

    def _text_cache_path(self) -> Path:
        # dağarcık ya da kalıplar değişirse önbellek kendiliğinden yenilenir
        key = json.dumps([self.labels, self.theme_keys, OBJECT_PROMPTS, THEME_PROMPTS])
        digest = hashlib.sha1(key.encode("utf-8")).hexdigest()[:10]
        return config.MODELS_DIR / f"text_features-{digest}.pt"

    def is_ready_on_disk(self) -> bool:
        if not self.labels:
            self._load_vocabularies()
        return self._clip_cache_path().exists() and self._text_cache_path().exists()

    def load(self, progress=None):
        """Modeli ve dağarcık özniteliklerini hazırlar, ilerlemeyi progress ile bildirir."""
        import clip  # import ağır olduğu için fonksiyon içinde
        import torch

        def report(stage, label, done=None, total=None):
            if progress:
                progress(stage, label, done, total)

        self._load_vocabularies()
        weights = self._clip_cache_path()
        if not weights.exists():
            try:
                self._download(CLIP_URL, weights,
                               lambda done, total: report("download", "Görüş modeli (CLIP) indiriliyor", done, total))
            except Exception:
                pass  # adres değişmişse kütüphanenin kendi indiricisi devralır
        report("load", "Model yükleniyor")
        self._model, self._preprocess = clip.load(config.CLIP_MODEL, device="cpu")
        self._model.eval()

        cache = self._text_cache_path()
        if cache.exists():
            features = torch.load(cache)
        else:
            report("encode", "Dağarcık kodlanıyor (tek seferlik)")
            features = {
                "objects": self._encode_texts(self.labels, OBJECT_PROMPTS),
                "themes": self._encode_texts([k.replace("_", " ") for k in self.theme_keys],
                                             THEME_PROMPTS),
            }
            config.MODELS_DIR.mkdir(exist_ok=True)
            torch.save(features, cache)
        self._object_features = features["objects"]
        self._theme_features = features["themes"]

    @staticmethod
    def _download(url: str, dest: Path, progress):
        dest.parent.mkdir(parents=True, exist_ok=True)
        partial = dest.with_suffix(dest.suffix + ".part")
        with requests.get(url, stream=True, timeout=30) as response:
            response.raise_for_status()
            total = int(response.headers.get("content-length", 0))
            done = 0
            with open(partial, "wb") as file:
                for chunk in response.iter_content(256 * 1024):
                    file.write(chunk)
                    done += len(chunk)
                    progress(done, total)
        partial.replace(dest)  # yarım inen dosya gerçek adıyla kalmaz

    def _encode_texts(self, phrases: list, templates: tuple):
        """Her ifadeyi kalıplarla kodlar, kalıp ortalamasını birim uzunluğa getirir."""
        import clip
        import torch
        features = []
        with torch.no_grad():
            for start in range(0, len(phrases), 256):
                batch = phrases[start:start + 256]
                stacked = []
                for template in templates:
                    tokens = clip.tokenize([template.format(p) for p in batch])
                    encoded = self._model.encode_text(tokens).float()
                    stacked.append(encoded / encoded.norm(dim=-1, keepdim=True))
                mean = torch.stack(stacked).mean(dim=0)
                features.append(mean / mean.norm(dim=-1, keepdim=True))
        return torch.cat(features)

    # çıkarım

    def _encode_image(self, image):
        """Tam görüntü ve merkez kırpımının ortalama özniteliği.

        Merkez kırpım ön plandaki objenin ağırlığını artırır.
        """
        import torch
        width, height = image.size
        ratio = config.CENTER_CROP_RATIO
        left, top = width * (1 - ratio) / 2, height * (1 - ratio) / 2
        center = image.crop((left, top, left + width * ratio, top + height * ratio))
        batch = torch.stack([self._preprocess(image), self._preprocess(center)])
        with torch.no_grad():
            encoded = self._model.encode_image(batch).float()
        encoded = encoded / encoded.norm(dim=-1, keepdim=True)
        mean = encoded.mean(dim=0)
        return mean / mean.norm()

    def analyze(self, image):
        """Görüntü için tahmin ve anahtar kelime listesi döndürür."""
        features = self._encode_image(image)
        object_scores = (LOGIT_SCALE * features @ self._object_features.T).softmax(dim=-1).tolist()
        theme_scores = (LOGIT_SCALE * features @ self._theme_features.T).softmax(dim=-1).tolist()

        ranked = self.rank(object_scores, self.labels, 1 + config.ALTERNATIVES)
        label, confidence = ranked[0]
        name_tr = self.turkish_name(label)
        alternatives = [(self.turkish_name(other), score) for other, score in ranked[1:]]
        prediction = Prediction(label, name_tr, confidence, alternatives)
        keywords = self.keywords_from_themes(theme_scores, self.theme_keys, self.themes,
                                             name_tr, config.MAX_KEYWORDS)
        return prediction, keywords

    @staticmethod
    def rank(scores: list, names: list, top: int) -> list:
        """Skorları büyükten küçüğe ad ve skor çiftleri olarak sıralar."""
        order = sorted(range(len(scores)), key=lambda i: -scores[i])
        return [(names[i], scores[i]) for i in order[:top]]

    @staticmethod
    def keywords_from_themes(scores: list, theme_keys: list, themes: dict,
                             object_tr: str, limit: int) -> list:
        """En güçlü temaların Türkçe kelimelerini, objenin adını tekrar etmeden toplar."""
        ranked = VisionModel.rank(scores, theme_keys, len(theme_keys))
        floor = max(ranked[0][1] * config.THEME_MIN_RATIO, config.THEME_MIN_SCORE) if ranked else 0.0
        strong = [(theme, score) for theme, score in ranked if score >= floor]
        keywords = VisionModel._collect_words(strong, themes, object_tr, limit)
        if len(keywords) < config.MIN_KEYWORDS:
            # eşik çok az tema bıraktıysa sıradaki temalarla asgari sayıya tamamlanır
            keywords = VisionModel._collect_words(ranked[:limit * 3], themes, object_tr,
                                                  max(len(keywords), config.MIN_KEYWORDS))
        return keywords

    @staticmethod
    def _collect_words(ranked: list, themes: dict, object_tr: str, limit: int) -> list:
        object_lower = object_tr.lower()
        keywords, seen = [], set()
        # ilk turda her temadan bir kelime alınır ki liste tek temaya kilitlenmesin,
        # yer kalırsa ikinci turda temaların diğer kelimeleri gelir
        for position in range(max((len(themes.get(t, [])) for t, _ in ranked), default=0)):
            for theme, score in ranked:
                words = themes.get(theme, [])
                if position >= len(words) or len(keywords) >= limit:
                    continue
                lower = words[position].lower()
                # objenin adı zaten biliniyor, anahtar kelime olarak tekrar etmez
                if lower in seen or lower in object_lower or object_lower in lower:
                    continue
                seen.add(lower)
                keywords.append(Keyword(words[position], theme, score))
            if len(keywords) >= limit:
                break
        return keywords

    def turkish_name(self, label: str) -> str:
        return self.names_tr.get(label, label)
