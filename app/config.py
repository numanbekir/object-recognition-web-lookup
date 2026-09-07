# Numan Bekir Özçelik - 06.09.2026
"""Eşikler ve limitler koda dağılmasın diye tek yerde tutulur"""

from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
MODELS_DIR = BASE_DIR / "models"
RECORDS_PATH = BASE_DIR / "records.json"
LOG_PATH = BASE_DIR / "app.log"  # kütüphane uyarıları ekran yerine buraya yazılır

# görüş modeli, sıfır atış sınıflandırma
CLIP_MODEL = "ViT-B/32"
OBJECT_NAMES_TR_PATH = DATA_DIR / "object_names_tr.json"  # obje dağarcığı ve Türkçe adlar
THEME_MAP_PATH = DATA_DIR / "theme_map.json"  # tema dağarcığı ve Türkçe anahtar kelimeler
WORD_ROLES_PATH = DATA_DIR / "word_roles.json"  # anahtar kelime rolleri, sorgu kurulumunda kullanılır
INFO_BLOCKS_PATH = DATA_DIR / "info_blocks.json"  # obje ailesine göre bilgi blokları
CENTER_CROP_RATIO = 0.7  # ön plandaki objeye odaklanmak için ikinci bakış
PROBE_PATH = MODELS_DIR / "probe.pt"  # kendi eğittiğimiz sınıflandırıcı, yoksa yalnız sıfır atış
PROBE_MIN_CONFIDENCE = 0.5  # sınıflandırıcının cevabı sıfır atış adayları arasındaysa bu güven yeter
PROBE_SOLO_CONFIDENCE = 0.8  # adaylar arasında değilse tek başına bu kadar emin olmalı
MIN_CONFIDENCE = 0.25  # altındaysa tahmin emin değilim notuyla verilir
ALTERNATIVES = 2  # düşük güvende gösterilen diğer adaylar
RECONCILE_MAX_CONFIDENCE = 0.5  # obje güveni bunun altındaysa temalarla uzlaşma kuralı çalışır
MAX_KEYWORDS = 5
MIN_KEYWORDS = 3  # eşik altında kalsa da en güçlü temalardan bu sayıya tamamlanır
THEME_MIN_RATIO = 0.15  # en iyi temanın bu oranının altındaki temalar kelime vermez
THEME_MIN_SCORE = 0.05  # gürültü seviyesindeki temalar kelime vermez

# görüntü
MIN_IMAGE_SIDE = 64
MAX_IMAGE_SIDE = 2000
MAX_DOWNLOAD_MB = 20
DOWNLOAD_TIMEOUT = 10
MAX_INPUT_LENGTH = 2000

# arama ve içerik
SEARCH_REGION = "tr-tr"
SEARCH_RESULT_COUNT = 10
MAX_PAGES = 8  # tüm blok sorgularının sonuçları tek havuzda indirilir
PAGE_TIMEOUT = 6
WIKI_TIMEOUT = 6
WIKI_MIN_CHARS = 250  # giriş bu uzunluğa ulaşana kadar sonraki paragraflar eklenir
MAX_PASSAGES = 3  # metin turlarında gösterilecek web paragrafı
BLOCK_MIN_SIMILARITY = 0.15  # kendi sayfalarından gelen blok paragrafı açı sorgusuna en az bu kadar benzemeli
BLOCK_POOL_MIN_SIMILARITY = 0.20  # havuzdan doldurulan blok sorgu eşleşmesi taşımadığı için daha sıkı
BLOCK_MIN_HINT_HITS = 2  # ve en az bu kadar farklı açı kökü içermeli
SEARCH_WORKERS = 2  # blok sorguları bu kadar paralel atılır
MIN_PASSAGE_CHARS = 150
MAX_PASSAGE_CHARS = 900
JACCARD_THRESHOLD = 0.6
MIN_SIMILARITY = 0.05  # sorguyla bu kadar bile örtüşmeyen paragraf gösterilmez

# bağlam
CONTEXT_WINDOW = 3  # bağlam için hatırlanan son tur sayısı
