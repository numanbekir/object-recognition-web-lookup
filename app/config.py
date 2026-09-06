# Numan Bekir Özçelik - 06.09.2026
"""Eşikler ve limitler koda dağılmasın diye tek yerde tutulur"""

from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
MODELS_DIR = BASE_DIR / "models"
RECORDS_PATH = BASE_DIR / "records.json"

# Görüş modeli: CLIP ViT-B/32, sıfır atış sınıflandırma
CLIP_MODEL = "ViT-B/32"
OBJECT_NAMES_TR_PATH = DATA_DIR / "object_names_tr.json"  # obje dağarcığı ve Türkçe adlar
THEME_MAP_PATH = DATA_DIR / "theme_map.json"  # tema dağarcığı ve Türkçe anahtar kelimeler
CENTER_CROP_RATIO = 0.7  # ön plandaki objeye odaklanmak için ikinci bakış
MIN_CONFIDENCE = 0.25  # altındaysa tahmin "emin değilim" notuyla verilir
ALTERNATIVES = 2  # düşük güvende gösterilen diğer adaylar
MAX_KEYWORDS = 5
THEME_MIN_RATIO = 0.15  # en iyi temanın bu oranının altındaki temalar kelime vermez
THEME_MIN_SCORE = 0.05  # gürültü seviyesindeki temalar kelime vermez

# Görüntü
MIN_IMAGE_SIDE = 64
MAX_IMAGE_SIDE = 2000
MAX_DOWNLOAD_MB = 20
DOWNLOAD_TIMEOUT = 10
MAX_INPUT_LENGTH = 2000

# Arama ve içerik
SEARCH_REGION = "tr-tr"
SEARCH_RESULT_COUNT = 10
MAX_PAGES = 5
PAGE_TIMEOUT = 6
WIKI_TIMEOUT = 6
MAX_PASSAGES = 3  # Vikipedi tanımına ek olarak gösterilecek web paragrafı
MIN_PASSAGE_CHARS = 150
MAX_PASSAGE_CHARS = 900
JACCARD_THRESHOLD = 0.6

# Bağlam
CONTEXT_WINDOW = 3  # bağlam için hatırlanan son tur sayısı
