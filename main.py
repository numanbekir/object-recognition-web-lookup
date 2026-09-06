# Numan Bekir Özçelik - 04.09.2026
"""Ana uygulama"""

import argparse
import re
import shlex
import sys
from pathlib import Path
from urllib.parse import unquote, urlparse

from app import config
from app.detector import ObjectDetector
from app.image_loader import ImageLoader, ImageLoadError
from app.keywords import KeywordExtractor

IMAGE_EXTENSIONS = (".jpg", ".jpeg", ".png", ".webp", ".bmp", ".gif", ".tif", ".tiff", ".svg")
QUIT_WORDS = ("q", "çık", "cik", "exit", "quit")
KNOWN_TLDS = ("com", "net", "org", "io", "co", "dev", "ai", "app", "edu", "gov", "tr", "uk", "de")
DOMAIN_PATTERN = re.compile(r"[a-z0-9-]+(\.[a-z0-9-]+)*\.[a-z]{2,24}", re.IGNORECASE)


def _path_exists(path: Path) -> bool:
    # 255 bayttan uzun ad bileşeni linux'ta OSError fırlatır, dosya yok sayılır
    try:
        return path.exists()
    except (OSError, ValueError):
        return False


def _path_is_file(path: Path) -> bool:
    try:
        return path.is_file()
    except (OSError, ValueError):
        return False


def clean_input(raw: str) -> str:
    text = raw.strip()
    # terminale sürüklenen dosya yolu tırnaklı gelebilir
    if len(text) >= 2 and text[0] == text[-1] and text[0] in ("'", '"'):
        text = text[1:-1].strip()
    return text


def _looks_like_source(token: str) -> bool:
    # yalnız url'ler ve desteklenen dosya türleri kaynak sayılır
    if token.startswith(("http://", "https://", "file://", "www.")):
        return True
    return token.lower().endswith(IMAGE_EXTENSIONS)


def find_sources(text: str) -> list:
    """Girdideki görsel/URL adaylarını listeler (çoklu girdi denetimi için)."""
    try:
        tokens = shlex.split(text)
    except ValueError:
        return []
    return [token for token in tokens if _looks_like_source(token)]


def is_unsupported_file(text: str) -> bool:
    """Sürüklenen dosya var ama görsel değilse girişte hiç kabul edilmez."""
    try:
        tokens = shlex.split(text)
    except ValueError:
        return False
    for token in tokens:
        if _looks_like_source(token):
            continue
        if _path_is_file(Path(token).expanduser()):
            return True
    return False


def is_single_source(text: str) -> bool:
    """Metnin tamamı tek bir kaynak mı (chip'e dönüşmeye uygun mu)?"""
    try:
        tokens = shlex.split(text)
    except ValueError:
        return False
    return len(tokens) == 1 and _looks_like_source(tokens[0])


def normalize_schemeless(text: str):
    """www.x.com veya x.com/yol gibi şemasız adresleri https'e yükseltir."""
    if " " in text:
        return None
    if text.startswith("www.") and "." in text[4:]:
        return "https://" + text
    head = text.split("/", 1)[0]
    if "/" in text and DOMAIN_PATTERN.fullmatch(head):
        return "https://" + text
    if DOMAIN_PATTERN.fullmatch(text) and text.rsplit(".", 1)[1].lower() in KNOWN_TLDS:
        return "https://" + text
    return None


def classify_input(raw: str):
    """(tür, değer) döndürür; tür: empty/quit/too_long/multi/url/bad_scheme/path/missing_file/text"""
    stripped = raw.strip()
    if not stripped:
        return "empty", ""
    if stripped.lower() in QUIT_WORDS:
        return "quit", ""
    if len(stripped) > config.MAX_INPUT_LENGTH:
        return "too_long", ""

    # çoklu denetim tırnak temizliğinden ÖNCE: shlex tırnaklı yolları doğru böler
    if len(find_sources(stripped)) >= 2:
        return "multi", ""

    text = clean_input(raw)

    # sürükle-bırak bazı terminallerde file:// önekiyle gelir
    if text.startswith("file://"):
        text = unquote(urlparse(text).path)

    if "://" in text or text.startswith("data:"):
        scheme = urlparse(text).scheme
        if scheme in ("http", "https"):
            return "url", text
        return "bad_scheme", scheme

    path = Path(text).expanduser()
    if _path_exists(path):
        return "path", str(path)
    if "\\" in text:
        # bazı terminaller sürüklenen yolu ters bölüyle kaçışlar: foto\ 1.jpg
        unescaped = re.sub(r"\\(.)", r"\1", text)
        unescaped_path = Path(unescaped).expanduser()
        if _path_exists(unescaped_path):
            return "path", str(unescaped_path)
    upgraded = normalize_schemeless(text)
    if upgraded:
        return "url", upgraded
    if text.lower().endswith(IMAGE_EXTENSIONS):
        return "missing_file", text
    return "text", text


def process_turn(kind: str, value: str, loader: ImageLoader, detector: ObjectDetector,
                 keywords: KeywordExtractor, emit, emit_debug):
    """Bir kullanıcı turunu işler; çıktıları emit(mesaj) ile arayüze iletir."""
    if kind == "too_long":
        emit("Girdi biraz uzun görünüyor. Daha kısa bir adres ya da mesaj dener misin?")
        return
    if kind == "bad_scheme":
        emit("Yalnızca http/https adreslerini ve yerel dosya yollarını destekliyorum.")
        return
    if kind == "missing_file":
        emit(f"Bu konumda bir dosya bulamadım: {value}. Yolu kontrol eder misin?")
        return
    if kind == "multi":
        emit("Aynı anda tek görsel işleyebiliyorum. Tek bir görsel ya da URL verir misin?")
        return
    if kind == "text":
        emit("Henüz analiz edilmiş bir görsel yok. Önce bir görsel URL'si ya da dosya yolu verir misin?")
        return

    try:
        image = loader.load(value, kind)
    except ImageLoadError as error:
        emit(str(error))
        return
    emit_debug("görüntü", f"{image.width}x{image.height} yüklendi")

    detections = detector.detect(image)
    emit_debug("tespit", ", ".join(
        f"{d.label} {d.confidence:.2f}" for d in detections) or "kutu yok")
    dominant = detector.pick_dominant(detections, image.size)
    if dominant is None:
        emit("Bu görselde belirgin bir obje tespit edemedim. Başka bir görsel dener misin?")
        return

    secondary = [d.label for d in detections if d is not dominant and d.label != dominant.label]
    emit_debug("baskın", f"{dominant.label} ({dominant.confidence:.2f})"
               + (f" · ikincil: {', '.join(secondary)}" if secondary else ""))
    emit(f"Tespit ettiğim obje: {keywords.turkish_name(dominant.label)} "
         f"(güven %{dominant.confidence * 100:.0f}).")

    scored = keywords.extract_scored(dominant.label, secondary)
    emit_debug("kelimeler", ", ".join(
        f"{item.word} [{item.source} {item.score:.1f}]" for item in scored) or "tema bulunamadı")
    if scored:
        emit(f"Anahtar kelimeler: {', '.join(item.word for item in scored)}")


def run_plain(args, loader, detector, keywords):
    # tty olmayan ortam (pipe/test) için sade satır modu
    print("Görüntülü Sohbet")
    if detector.is_ready_on_disk():
        print("Model yükleniyor...")
    else:
        print("Model bulunamadı, tek seferlik indirme ve hazırlık yapılıyor...")
    try:
        detector.load()
        keywords.load()
    except Exception as error:
        print("Modeli hazırlayamadım. İlk çalıştırma için internet bağlantısı gerekiyor, "
              "bağlantını kontrol edip tekrar dener misin?")
        if args.debug:
            print(f"Ayrıntı: {error!r}")
        return
    print(f"Model hazır ({detector.vocab_size} kavram).")

    def emit(message):
        print(message)

    def emit_debug(stage, message):
        if args.debug:
            print(f"{stage} · {message}")

    while True:
        try:
            raw = input("\n> ")
        except (KeyboardInterrupt, EOFError):
            print("\nGörüşmek üzere!")
            return
        kind, value = classify_input(raw)
        if kind == "empty":
            continue
        if kind == "quit":
            print("Görüşmek üzere!")
            return
        try:
            process_turn(kind, value, loader, detector, keywords, emit, emit_debug)
        except KeyboardInterrupt:
            print("İşlemi iptal ettim.")
        except Exception as error:
            # tek turda oluşan sorun uygulamayı kapatmasın
            print("Beklenmeyen bir sorun oluştu. Tekrar dener misin?")
            emit_debug("hata", repr(error))


def run(args):
    loader = ImageLoader()
    detector = ObjectDetector()
    keywords = KeywordExtractor()

    if not (sys.stdin.isatty() and sys.stdout.isatty()):
        run_plain(args, loader, detector, keywords)
        return

    from types import SimpleNamespace

    from app.ui import ChatApp
    tools = SimpleNamespace(is_single_source=is_single_source,
                            find_sources=find_sources,
                            is_unsupported_file=is_unsupported_file)
    app = ChatApp(loader, detector, keywords, process_turn, classify_input, tools,
                  debug=args.debug)
    farewell = app.run()
    print(farewell or "Görüşmek üzere!")


def parse_args():
    parser = argparse.ArgumentParser(description="Görüntülü sohbet uygulaması")
    parser.add_argument("--debug", action="store_true", help="Pipeline kararlarını ayrıntılı göster")
    return parser.parse_args()


if __name__ == "__main__":
    run(parse_args())
