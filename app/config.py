# Numan Bekir Özçelik - 04.09.2026
"""Eşikler ve limitler koda dağılmasın diye tek yerde tutulur"""

from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
MODELS_DIR = BASE_DIR / "models"
RECORDS_PATH = BASE_DIR / "records.json"

# Tespit
DETECTOR_WEIGHTS = "yolov8s-worldv2.pt"
DETECTOR_CUSTOM = MODELS_DIR / "detector-lvis.pt"
VOCABULARY_PATH = DATA_DIR / "vocabulary.txt"
CONFIDENCE_THRESHOLD = 0.20
IOU_DEDUP_THRESHOLD = 0.6

# Görüntü
MIN_IMAGE_SIDE = 64
MAX_IMAGE_SIDE = 2000
MAX_DOWNLOAD_MB = 20
DOWNLOAD_TIMEOUT = 10
MAX_INPUT_LENGTH = 2000

# Anahtar kelime
THEME_MAP_PATH = DATA_DIR / "theme_map.json"
OBJECT_NAMES_TR_PATH = DATA_DIR / "object_names_tr.json"
CONCEPT_STATS_PATH = DATA_DIR / "concept_stats.json"
MAX_KEYWORDS = 6
MAX_SUGGESTION_KEYWORDS = 2
SUGGESTION_TIMEOUT = 3

# Arama ve içerik
SEARCH_REGION = "tr-tr"
SEARCH_RESULT_COUNT = 12
MAX_PAGES = 6
PAGE_TIMEOUT = 5
SENTENCE_CLASSIFIER_PATH = MODELS_DIR / "sentence_classifier.joblib"
CLASSIFIER_FILLER_THRESHOLD = 0.80
JACCARD_THRESHOLD = 0.65

# Sunum
MIN_SENTENCES = 3
MAX_SENTENCES = 8
MAX_PER_SOURCE_RUN = 2

# Bağlam
CONTEXT_WINDOW = 3
