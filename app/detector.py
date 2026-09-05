# Numan Bekir Özçelik - 04.09.2026
"""YOLO-World ile tüm nesneler tespit edilir

    görüntü -> YOLO-World -> tüm nesneler tespit edilir
            -> tespit edilen her nesne için skor = kapladığı alan x merkeze yakınlık x güven
            -> en yüksek skorlu kutu ön plandaki objedir, kalanlar ikincil
"""

from . import config


class Detection:
    def __init__(self, label: str, confidence: float, box: tuple):
        self.label = label
        self.confidence = confidence
        self.box = box


class ObjectDetector:
    def __init__(self):
        self.model = None
        self.vocab_size = 0

    def load(self):
        # import ağır olduğu için fonksiyon içinde, uygulama açılışında bir kez çalışır
        from ultralytics import YOLOWorld

        vocabulary = [line.strip() for line in
                      config.VOCABULARY_PATH.read_text(encoding="utf-8").splitlines()
                      if line.strip()]
        self.vocab_size = len(vocabulary)

        if config.DETECTOR_CUSTOM.exists():
            # dağarcık gömülü model varsa CLIP'e gerek kalmadan direkt açılır
            self.model = YOLOWorld(str(config.DETECTOR_CUSTOM))
            return

        self.model = YOLOWorld(config.DETECTOR_WEIGHTS)
        self.model.set_classes(vocabulary)
        config.MODELS_DIR.mkdir(exist_ok=True)
        self.model.save(str(config.DETECTOR_CUSTOM))  # sonraki açılışlar hızlansın

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
