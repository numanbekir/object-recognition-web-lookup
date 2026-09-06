# Numan Bekir Özçelik - 04.09.2026
"""Eşikler ve limitler koda dağılmasın diye tek yerde tutulur"""

from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
MODELS_DIR = BASE_DIR / "models"
RECORDS_PATH = BASE_DIR / "records.json"

# Tespit, yaygın nesnelerde COCO modeli, gerisinde açık dağarcık
PRIMARY_WEIGHTS = "yolo11n.pt"
DETECTOR_WEIGHTS = "yolov8s-worldv2.pt"
DETECTOR_CUSTOM = MODELS_DIR / "detector-lvis.pt"
VOCABULARY_PATH = DATA_DIR / "vocabulary.txt"
CONFIDENCE_THRESHOLD = 0.20
IOU_DEDUP_THRESHOLD = 0.6
MIN_DOMINANT_CONFIDENCE = 0.30  # altındaysa dürüst "seçemedim" mesajı
PERSON_OVERRIDE_MIN = 0.25  # bu güveni aşan insan-dışı aday baskınlıkta insana tercih edilir
PRIMARY_TRUST_CONFIDENCE = 0.55  # COCO bu güvenin üstündeyse çapraz kontrolsüz kabul
DOMINANT_CONF_GAP = 0.20  # bu kadar daha emin bir aday, büyük kutuya yenilmez
# COCO şemsiye sınıf verdiğinde inceltme sorulur. Tam dağarcıkta skor
# seyrelmesi özgül etiketi bastırdığı için inceltme odaklanmış küçük
# dağarcıkla yapılır. Adaylar names_tr kapsamında olmalı.
UMBRELLA_CLASSES = {"sandwich": ("sandwich", "hamburger", "hot dog")}
# yedi görsellik kıyasta gerçek burger 0.77 üstü, sandviçe hamburger
# önyargısı 0.67 altında kaldı, eşik bu ölçümle temkinli tarafa kondu
UMBRELLA_REFINE_MIN = 0.75
UMBRELLA_IOU = 0.45  # inceltme adayı şemsiye kutuyla bu kadar örtüşmeli

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
SUGGESTION_FILL_THRESHOLD = 3  # baskın nesne bu sayıda kelimeye ulaştıysa öneri istenmez

# Arama ve içerik
SEARCH_REGION = "tr-tr"
SEARCH_RESULT_COUNT = 12
MAX_PAGES = 6
PAGE_TIMEOUT = 5
SENTENCE_CLASSIFIER_PATH = MODELS_DIR / "sentence_classifier.joblib"
CLASSIFIER_FILLER_THRESHOLD = 0.70  # eşik taramasıyla seçildi, eleme isabeti yüzde 88
JACCARD_THRESHOLD = 0.65

# Sunum
MIN_SENTENCES = 3
MAX_SENTENCES = 8
MAX_PER_SOURCE_RUN = 2

# Bağlam, sönümlenen konu profili
CONTEXT_DECAY = 0.5  # her başarılı turda eski ağırlıklar bununla çarpılır
CONTEXT_FLOOR = 0.1  # bu ağırlığın altına düşen kayıt profilden silinir
CONTEXT_QUERY_MIN = 0.5  # yalnız bu ağırlığın üstündeki obje sorguya girebilir
