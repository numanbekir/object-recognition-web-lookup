# Numan Bekir Özçelik - 04.09.2026
"""Ana uygulama"""

import argparse
import re
import sys
from pathlib import Path
from urllib.parse import unquote, urlparse

from app import config
from app.detector import ObjectDetector
from app.image_loader import ImageLoader, ImageLoadError

IMAGE_EXTENSIONS = (".jpg", ".jpeg", ".png", ".webp", ".bmp", ".gif", ".tif", ".tiff", ".svg")
QUIT_WORDS = ("q", "çık", "cik", "exit", "quit")


def clean_input(raw: str) -> str:
    text = raw.strip()
    # terminale sürüklenen dosya yolu tırnaklı gelebilir
    if len(text) >= 2 and text[0] == text[-1] and text[0] in ("'", '"'):
        text = text[1:-1].strip()
    return text


def classify_input(raw: str):
    """(tür, değer) döndürür; tür: empty/quit/too_long/url/bad_scheme/path/missing_file/text"""
    text = clean_input(raw)
    if not text:
        return "empty", ""
    if text.lower() in QUIT_WORDS:
        return "quit", ""
    if len(text) > config.MAX_INPUT_LENGTH:
        return "too_long", ""

    # sürükle-bırak bazı terminallerde file:// önekiyle gelir
    if text.startswith("file://"):
        text = unquote(urlparse(text).path)

    if "://" in text or text.startswith("data:"):
        scheme = urlparse(text).scheme
        if scheme in ("http", "https"):
            return "url", text
        return "bad_scheme", scheme

    path = Path(text).expanduser()
    if path.exists():
        return "path", str(path)
    if "\\" in text:
        # bazı terminaller sürüklenen yolu ters bölüyle kaçışlar: foto\ 1.jpg
        unescaped = re.sub(r"\\(.)", r"\1", text)
        unescaped_path = Path(unescaped).expanduser()
        if unescaped_path.exists():
            return "path", str(unescaped_path)
    if text.lower().endswith(IMAGE_EXTENSIONS):
        return "missing_file", text
    return "text", text


def process_turn(kind: str, value: str, loader: ImageLoader, detector: ObjectDetector,
                 emit, emit_debug):
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
    emit(f"Tespit ettiğim obje: {dominant.label} (güven %{dominant.confidence * 100:.0f}).")


def run_plain(args, loader, detector):
    # tty olmayan ortam (pipe/test) için sade satır modu
    print("Görüntülü Sohbet")
    if detector.is_ready_on_disk():
        print("Model yükleniyor...")
    else:
        print("Model bulunamadı, tek seferlik indirme ve hazırlık yapılıyor...")
    try:
        detector.load()
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
            process_turn(kind, value, loader, detector, emit, emit_debug)
        except KeyboardInterrupt:
            print("İşlemi iptal ettim.")
        except Exception as error:
            # tek turda oluşan sorun uygulamayı kapatmasın
            print("Beklenmeyen bir sorun oluştu. Tekrar dener misin?")
            emit_debug("hata", repr(error))


def run(args):
    loader = ImageLoader()
    detector = ObjectDetector()

    if not (sys.stdin.isatty() and sys.stdout.isatty()):
        run_plain(args, loader, detector)
        return

    from app.ui import ChatApp
    app = ChatApp(loader, detector, process_turn, classify_input, debug=args.debug)
    farewell = app.run()
    print(farewell or "Görüşmek üzere!")


def parse_args():
    parser = argparse.ArgumentParser(description="Görüntülü sohbet uygulaması")
    parser.add_argument("--debug", action="store_true", help="Pipeline kararlarını ayrıntılı göster")
    return parser.parse_args()


if __name__ == "__main__":
    run(parse_args())
