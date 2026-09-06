# Numan Bekir Özçelik - 04.09.2026
"""nesne tespiti için iki model

    görüntü -> YOLO11n, 80 yaygın COCO sınıfı
                 baskın kutu yeterince eminse -> sonuç
                 şemsiye sınıf odaklanmış dağarcıkla inceltilir
               değilse -> YOLO-World ve LVIS dağarcığı, açık kapsam
    baskın obje skoru = sqrt(alan) x merkeze yakınlık x güven^2
"""

from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import requests

from . import config

PRIMARY_URL = ("https://github.com/ultralytics/assets/releases/download/"
               "v8.3.0/yolo11n.pt")
WEIGHTS_URL = ("https://github.com/ultralytics/assets/releases/download/"
               "v8.3.0/yolov8s-worldv2.pt")
CLIP_URL = ("https://openaipublic.azureedge.net/clip/models/"
            "40d365715913c9da98579312b702a82c18be219cc2a73407c4526f58eba950af/ViT-B-32.pt")

# farklı yazılan COCO sınıf adlarının dağarcıktaki karşılıkları
COCO_TO_VOCAB = {
    "fire hydrant": "fireplug",
    "tie": "necktie",
    "skis": "ski",
    "sports ball": "ball",
    "wine glass": "wineglass",
    "donut": "doughnut",
    "couch": "sofa",
    "potted plant": "flowerpot",
    "tv": "television set",
    "laptop": "laptop computer",
    "remote": "remote control",
    "keyboard": "computer keyboard",
    "cell phone": "cellular telephone",
    "microwave": "microwave oven",
    "hair drier": "hair dryer",
    "mouse": "computer mouse",  # COCO'nun mouse'u aygıttır
}


class Detection:
    def __init__(self, label: str, confidence: float, box: tuple):
        self.label = label
        self.confidence = confidence
        self.box = box


class ObjectDetector:
    def __init__(self):
        self.primary = None  # yaygın nesnelerin COCO modeli
        self.model = None  # açık dağarcık modeli
        self.vocab_size = 0
        self.last_engine = ""
        self.last_uncertain = False
        self._refiners = {}  # şemsiye sınıf başına odaklanmış model, tembel kurulur
        self._clip = None  # hakem model, ilk ihtiyaçta kurulur

    def is_ready_on_disk(self) -> bool:
        return (config.DETECTOR_CUSTOM.exists()
                and (config.MODELS_DIR / config.PRIMARY_WEIGHTS).exists())

    def load(self, progress=None):
        # import ağır olduğu için fonksiyon içinde, uygulama açılışında bir kez çalışır
        from ultralytics import YOLO, YOLOWorld

        vocabulary = [line.strip() for line in
                      config.VOCABULARY_PATH.read_text(encoding="utf-8").splitlines()
                      if line.strip()]
        self.vocab_size = len(vocabulary)

        # eksik adımlar baştan planlanır
        primary_path = config.MODELS_DIR / config.PRIMARY_WEIGHTS
        weights = config.MODELS_DIR / config.DETECTOR_WEIGHTS
        need_embed = not config.DETECTOR_CUSTOM.exists()
        jobs = []
        if not primary_path.exists():
            jobs.append(("primary", "Hızlı tespit modeli indiriliyor", PRIMARY_URL, primary_path))
        if need_embed:
            if not weights.exists():
                jobs.append(("weights", "Tespit modeli indiriliyor", WEIGHTS_URL, weights))
            clip_cache = self._clip_cache_path()
            if not clip_cache.exists():
                jobs.append(("clip", "Sözlük kodlayıcı (CLIP) indiriliyor", CLIP_URL, clip_cache))

        step_keys = [job[0] for job in jobs] + (["embed"] if need_embed else [])
        total = len(step_keys)
        order = {key: index + 1 for index, key in enumerate(step_keys)}

        def report(key, label, done, size):
            if progress:
                progress(key, order[key], total, label, done, size)

        if jobs:
            # satırlar indirme başlamadan plan sırasıyla yerleşsin
            for key, label, _url, _dest in jobs:
                report(key, label, 0, 0)
            # eksik dosyalar aynı anda indirilir
            try:
                with ThreadPoolExecutor(max_workers=3) as pool:
                    futures = [pool.submit(self._download, key, label, url, dest, report)
                               for key, label, url, dest in jobs]
                    for future in futures:
                        future.result()
            except Exception:
                # adresler değişmiş olabilir, kütüphanelerin kendi indiricileri devralsın
                pass

        # dosya hala yoksa ultralytics adı tanıyıp kendisi indirir
        self.primary = YOLO(str(primary_path) if primary_path.exists()
                            else config.PRIMARY_WEIGHTS)
        if need_embed:
            report("embed", "Dağarcık modele gömülüyor (tek seferlik)", None, None)
            self.model = YOLOWorld(str(weights) if weights.exists() else config.DETECTOR_WEIGHTS)
            self.model.set_classes(vocabulary)
            config.MODELS_DIR.mkdir(exist_ok=True)
            self.model.save(str(config.DETECTOR_CUSTOM))  # sonraki açılışlar hızlansın
        else:
            self.model = YOLOWorld(str(config.DETECTOR_CUSTOM))

    def _clip_cache_path(self) -> Path:
        # CLIP kendi weights_dir ayarının altında aramaktadır
        try:
            from ultralytics.utils import WEIGHTS_DIR
            return Path(WEIGHTS_DIR) / "clip" / "ViT-B-32.pt"
        except Exception:
            return Path.home() / ".cache" / "clip" / "ViT-B-32.pt"

    def _download(self, key, label, url, dest: Path, progress):
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
                    if progress:
                        progress(key, label, done, total)
        partial.replace(dest)  # yarım inen dosya gerçek adıyla kalmaması için

    def detect(self, image) -> list:
        """Hibrit akış, kararsızlıkta last_uncertain işaretlenir.

        COCO güven eşiğini aşıyorsa doğrudan kabul edilir. Orta bölgede açık
        dağarcığa da sorulur. Aynı etiketi o da görüyorsa COCO onaylanır,
        görmüyorsa ve güçlü bir alternatifi de yoksa cevap uydurmak yerine
        kararsızlık işaretlenir.
        """
        self.last_uncertain = False
        primary = self._predict(self.primary, image, COCO_TO_VOCAB)
        dominant = self.pick_dominant(primary, image.size)
        has_object = (dominant is not None and dominant.label != "person"
                      and dominant.confidence >= config.PERSON_OVERRIDE_MIN)

        if has_object and dominant.confidence >= config.PRIMARY_TRUST_CONFIDENCE:
            if dominant.label in config.UMBRELLA_CLASSES:
                # odaklanmış dağarcık aynı kutuda daha özgül bir etiket
                # veriyorsa o kazanır
                focused = self._predict(self._refiner(dominant.label), image,
                                        None, dedup=False)
                refined = self._pick_refinement(dominant, focused)
                if refined is not None:
                    dominant.label = refined.label
                    dominant.confidence = refined.confidence
                    self.last_engine = "coco+inceltme"
                    return primary
            self.last_engine = "coco"
            return primary

        # coco yeterince emin değil, hakem model tam görüntüye bakar.
        # insan cevabı hakemden kabul edilmez, insan kuralı coco'da çözülür
        try:
            label, prob = self._clip_verdict(image)
        except Exception:
            label, prob = "", 0.0
        if prob >= config.CLIP_TRUST and label != "person":
            self.last_engine = "clip hakemliği"
            width, height = image.size
            return [Detection(label, prob, (0.0, 0.0, float(width), float(height)))]

        world = self._predict(self.model, image, None)
        if not has_object:
            self.last_engine = "açık dağarcık"
            return world

        if any(d.label == dominant.label and d.confidence >= config.PERSON_OVERRIDE_MIN
               for d in world):
            self.last_engine = "coco+dünya onayı"
            return primary
        world_dominant = self.pick_dominant(world, image.size)
        if world_dominant is not None \
                and world_dominant.confidence >= config.PRIMARY_TRUST_CONFIDENCE:
            self.last_engine = "açık dağarcık"
            return world
        # iki model orta güvenle farklı şeyler söylüyorsa tahmine güvenilmez
        self.last_engine = "uyuşmazlık"
        self.last_uncertain = True
        return primary

    def _clip_verdict(self, image):
        """Tam görüntüyü dağarcık üzerinde sınıflandırır, ad ve olasılık döner.

        Tespit modeli bazı nesnelere kör kalıyor, ölçümde keman yüksek
        güvenle makas sanılırken CLIP aynı görüntüye tam güven verdi.
        COCO'nun emin olamadığı her durumda hakem olarak buraya sorulur.
        """
        import clip
        import torch
        if self._clip is None:
            vocabulary = [line.strip() for line in
                          config.VOCABULARY_PATH.read_text(encoding="utf-8").splitlines()
                          if line.strip()]
            model, preprocess = clip.load("ViT-B/32", device="cpu")
            tokens = clip.tokenize([f"a photo of a {name}" for name in vocabulary])
            with torch.no_grad():
                features = model.encode_text(tokens)
                features /= features.norm(dim=-1, keepdim=True)
            self._clip = (model, preprocess, features, vocabulary)
        model, preprocess, text_features, vocabulary = self._clip
        tensor = preprocess(image).unsqueeze(0)
        with torch.no_grad():
            image_features = model.encode_image(tensor)
            image_features /= image_features.norm(dim=-1, keepdim=True)
            probs = (100 * image_features @ text_features.T).softmax(dim=-1)[0]
        best = int(probs.argmax())
        return vocabulary[best], float(probs[best])

    def _refiner(self, umbrella: str):
        """Şemsiye sınıfın küçük dağarcıklı modelini ilk kullanımda kurar.

        Tam dağarcıkta özgül etiket skor seyrelmesine yenik düşüyor. Birkaç
        isimlik odaklanmış liste bu rekabeti ortadan kaldırıyor.
        """
        if umbrella not in self._refiners:
            from ultralytics import YOLOWorld
            weights = config.MODELS_DIR / config.DETECTOR_WEIGHTS
            refiner = YOLOWorld(str(weights) if weights.exists()
                                else config.DETECTOR_WEIGHTS)
            refiner.set_classes(list(config.UMBRELLA_CLASSES[umbrella]))
            self._refiners[umbrella] = refiner
        return self._refiners[umbrella]

    def _pick_refinement(self, dominant, world_detections: list):
        """Şemsiye kutuyla örtüşen en emin ve daha özgül etiketi seçer."""
        candidates = [d for d in world_detections
                      if d.label != "person"
                      and self._iou(d.box, dominant.box) >= config.UMBRELLA_IOU]
        if not candidates:
            return None
        top = max(candidates, key=lambda d: d.confidence)
        # açık dağarcık da şemsiye etiketi öne koyuyorsa inceltme yapılmaz
        if top.label == dominant.label or top.confidence < config.UMBRELLA_REFINE_MIN:
            return None
        return top

    def _predict(self, model, image, label_map, dedup: bool = True) -> list:
        result = model.predict(image, conf=config.CONFIDENCE_THRESHOLD, verbose=False)[0]
        detections = []
        for box in result.boxes:
            label = result.names[int(box.cls)]
            if label_map:
                label = label_map.get(label, label)
            detections.append(Detection(label, float(box.conf), tuple(box.xyxy[0].tolist())))
        # inceltme ham listeye bakar, tekilleştirme eş kutudaki özgül etiketi silebilir
        return self._deduplicate(detections) if dedup else detections

    @staticmethod
    def _iou(a: tuple, b: tuple) -> float:
        x1, y1 = max(a[0], b[0]), max(a[1], b[1])
        x2, y2 = min(a[2], b[2]), min(a[3], b[3])
        intersection = max(0.0, x2 - x1) * max(0.0, y2 - y1)
        if intersection == 0.0:
            return 0.0
        area_a = (a[2] - a[0]) * (a[3] - a[1])
        area_b = (b[2] - b[0]) * (b[3] - b[1])
        return intersection / (area_a + area_b - intersection)

    def _deduplicate(self, detections: list) -> list:
        # aynı bölgeye düşen eş anlamlı etiketler teklenir
        detections = sorted(detections, key=lambda d: -d.confidence)
        kept = []
        for detection in detections:
            if all(self._iou(detection.box, other.box) < config.IOU_DEDUP_THRESHOLD
                   for other in kept):
                kept.append(detection)
        return kept

    def pick_dominant(self, detections: list, image_size: tuple):
        # büyük ama emin olunmayan kutu küçük ama emin kutuyu ezememeli
        width, height = image_size
        best, best_score = None, 0.0
        best_object, best_object_score = None, 0.0  # insan dışındaki en iyi aday
        for detection in detections:
            x1, y1, x2, y2 = detection.box
            area = (x2 - x1) * (y2 - y1) / (width * height)
            center_x = (x1 + x2) / 2 / width
            center_y = (y1 + y2) / 2 / height
            distance = ((center_x - 0.5) ** 2 + (center_y - 0.5) ** 2) ** 0.5
            centrality = 1.0 - min(distance / 0.707, 1.0)
            score = (area ** 0.5) * centrality * (detection.confidence ** 2)
            if score > best_score:
                best, best_score = detection, score
            if detection.label != "person" and score > best_object_score:
                best_object, best_object_score = detection, score
        if (best is not None and best.label == "person" and best_object is not None
                and best_object.confidence >= config.PERSON_OVERRIDE_MIN):
            best = best_object
        #belirgin biçimde daha emin küçük aday kazanır
        if best is not None:
            for detection in detections:
                if detection.label == "person":
                    continue
                if detection.confidence >= best.confidence + config.DOMINANT_CONF_GAP:
                    best = detection
        return best
