# Numan Bekir Özçelik - 04.09.2026
"""YOLO-World ile tespit, birden çok nesne varsa en merkezi/ön plandaki nesne seçilir"""


class Detection:
    def __init__(self, label: str, confidence: float, box: tuple):
        self.label = label
        self.confidence = confidence
        self.box = box


class ObjectDetector:
    def __init__(self):
        self.model = None

    def load(self):
        raise NotImplementedError

    def detect(self, image):
        raise NotImplementedError

    def pick_dominant(self, detections, image_size):
        # en büyük, merkeze en yakın ve en emin kutu kazanır
        raise NotImplementedError
