# Numan Bekir Özçelik - 04.09.2026
"""YOLO-World ile tüm nesneler tespit edilir

    görüntü -> YOLO-World -> tüm nesneler tespit edilir
            -> tespit edilen her nesne için skor = kapladığı alan x merkeze yakınlık x güven
            -> en yüksek skorlu kutu ön plandaki objedir, kalanlar ikincil
"""

from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import requests

from . import config

WEIGHTS_URL = ("https://github.com/ultralytics/assets/releases/download/"
               "v8.3.0/yolov8s-worldv2.pt")
CLIP_URL = ("https://openaipublic.azureedge.net/clip/models/"
            "40d365715913c9da98579312b702a82c18be219cc2a73407c4526f58eba950af/ViT-B-32.pt")


class Detection:
    def __init__(self, label: str, confidence: float, box: tuple):
        self.label = label
        self.confidence = confidence
        self.box = box


class ObjectDetector:
    def __init__(self):
        self.model = None
        self.vocab_size = 0

    def is_ready_on_disk(self) -> bool:
        return config.DETECTOR_CUSTOM.exists()

    def load(self, progress=None):
        # import ağır olduğu için fonksiyon içinde, uygulama açılışında bir kez çalışır
        from ultralytics import YOLOWorld

        vocabulary = [line.strip() for line in
                      config.VOCABULARY_PATH.read_text(encoding="utf-8").splitlines()
                      if line.strip()]
        self.vocab_size = len(vocabulary)

        if config.DETECTOR_CUSTOM.exists():
            # dağarcık gömülü model varsa indirme ve CLIP gerekmez
            self.model = YOLOWorld(str(config.DETECTOR_CUSTOM))
            return

        # eksik adımlar baştan planlanır
        jobs = []
        if not self._weights_path().exists():
            jobs.append(("weights", "Tespit modeli indiriliyor",
                         WEIGHTS_URL, config.MODELS_DIR / config.DETECTOR_WEIGHTS))
        clip_cache = self._clip_cache_path()
        if not clip_cache.exists():
            jobs.append(("clip", "Sözlük kodlayıcı (CLIP) indiriliyor", CLIP_URL, clip_cache))

        step_keys = [job[0] for job in jobs] + ["embed"]
        total = len(step_keys)
        order = {key: index + 1 for index, key in enumerate(step_keys)}

        def report(key, label, done, size):
            if progress:
                progress(key, order[key], total, label, done, size)

        if jobs:
            # satırlar indirme başlamadan plan sırasıyla yerleşsin
            for key, label, _url, _dest in jobs:
                report(key, label, 0, 0)
            # iki dosya da eksikse aynı anda indirilir
            try:
                with ThreadPoolExecutor(max_workers=2) as pool:
                    futures = [pool.submit(self._download, key, label, url, dest, report)
                               for key, label, url, dest in jobs]
                    for future in futures:
                        future.result()
            except Exception:
                # adresler değişmiş olabilir; kütüphanelerin kendi indiricileri devralsın
                pass

        report("embed", "Dağarcık modele gömülüyor (tek seferlik)", None, None)
        weights = self._weights_path()
        # dosya hala yoksa ultralytics adı tanıyıp kendisi indirir
        self.model = YOLOWorld(str(weights) if weights.exists() else config.DETECTOR_WEIGHTS)
        self.model.set_classes(vocabulary)
        config.MODELS_DIR.mkdir(exist_ok=True)
        self.model.save(str(config.DETECTOR_CUSTOM))  # sonraki açılışlar hızlansın

    def _weights_path(self) -> Path:
        preferred = config.MODELS_DIR / config.DETECTOR_WEIGHTS
        if preferred.exists():
            return preferred
        legacy = Path(config.DETECTOR_WEIGHTS)
        return legacy if legacy.exists() else preferred

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
        results = self.model.predict(image, conf=config.CONFIDENCE_THRESHOLD, verbose=False)
        result = results[0]
        detections = []
        for box in result.boxes:
            label = result.names[int(box.cls)]
            detections.append(Detection(label, float(box.conf), tuple(box.xyxy[0].tolist())))
        return detections

    def pick_dominant(self, detections: list, image_size: tuple):
        # en büyük, merkeze en yakın ve en emin kutu kazanır
        width, height = image_size
        best, best_score = None, 0.0
        for detection in detections:
            x1, y1, x2, y2 = detection.box
            area = (x2 - x1) * (y2 - y1) / (width * height)
            center_x = (x1 + x2) / 2 / width
            center_y = (y1 + y2) / 2 / height
            distance = ((center_x - 0.5) ** 2 + (center_y - 0.5) ** 2) ** 0.5
            centrality = 1.0 - min(distance / 0.707, 1.0)
            score = area * centrality * detection.confidence
            if score > best_score:
                best, best_score = detection, score
        return best
