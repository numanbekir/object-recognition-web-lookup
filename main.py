# Numan Bekir Özçelik - 04.09.2026
"""Ana uygulama"""

import argparse
from pathlib import Path
from urllib.parse import unquote, urlparse

from app import config
from app.detector import ObjectDetector
from app.image_loader import ImageLoader, ImageLoadError
from app.ui import ConsoleUI

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
    if text.lower().endswith(IMAGE_EXTENSIONS):
        return "missing_file", text
    return "text", text


def handle_turn(kind: str, value: str, ui: ConsoleUI, loader: ImageLoader,
                detector: ObjectDetector):
    if kind == "too_long":
        ui.info("Girdi biraz uzun görünüyor. Daha kısa bir adres ya da mesaj dener misin?")
        return
    if kind == "bad_scheme":
        ui.info("Yalnızca http/https adreslerini ve yerel dosya yollarını destekliyorum.")
        return
    if kind == "missing_file":
        ui.info(f"Bu konumda bir dosya bulamadım: {value}. Yolu kontrol eder misin?")
        return
    if kind == "text":
        ui.info("Henüz analiz edilmiş bir görsel yok. Önce bir görsel URL'si ya da dosya yolu verir misin?")
        return

    try:
        image = loader.load(value, kind)
    except ImageLoadError as error:
        ui.info(str(error))
        return
    ui.debug_line("görüntü", f"{image.width}x{image.height} yüklendi")

    detections = detector.detect(image)
    ui.debug_line("tespit", ", ".join(
        f"{d.label} {d.confidence:.2f}" for d in detections) or "kutu yok")
    dominant = detector.pick_dominant(detections, image.size)
    if dominant is None:
        ui.info("Bu görselde belirgin bir obje tespit edemedim. Başka bir görsel dener misin?")
        return

    secondary = [d.label for d in detections if d is not dominant and d.label != dominant.label]
    ui.debug_line("baskın", f"{dominant.label} ({dominant.confidence:.2f})"
                  + (f" · ikincil: {', '.join(secondary)}" if secondary else ""))
    ui.info(f"Tespit ettiğim obje: {dominant.label} (güven %{dominant.confidence * 100:.0f}).")


def run(args):
    ui = ConsoleUI(debug=args.debug)
    loader = ImageLoader()
    ui.welcome()

    detector = ObjectDetector()
    ui.info("Model hazırlanıyor, ilk çalıştırmada model dosyaları indirilir...")
    try:
        detector.load()
    except KeyboardInterrupt:
        print()
        ui.info("Kurulum yarıda kaldı. Tekrar başlattığında kaldığı yerden devam ederim.")
        return
    except Exception as error:
        # ilk çalıştırmada internet yoksa model inemez
        ui.info("Modeli hazırlayamadım. İlk çalıştırma için internet bağlantısı gerekiyor, "
                "bağlantını kontrol edip tekrar dener misin?")
        ui.debug_line("hata", repr(error))
        return
    ui.info(f"Model hazır ({detector.vocab_size} kavram).")

    while True:
        try:
            raw = ui.prompt()
        except (KeyboardInterrupt, EOFError):
            print()
            ui.info("Görüşmek üzere!")
            return

        kind, value = classify_input(raw)
        if kind == "empty":
            continue
        if kind == "quit":
            ui.info("Görüşmek üzere!")
            return

        try:
            handle_turn(kind, value, ui, loader, detector)
        except KeyboardInterrupt:
            ui.info("İşlemi iptal ettim.")
        except Exception as error:
            # tek turda oluşan sorun uygulamayı kapatmasın
            ui.info("Beklenmeyen bir sorun oluştu. Tekrar dener misin?")
            ui.debug_line("hata", repr(error))


def parse_args():
    parser = argparse.ArgumentParser(description="Görüntülü sohbet uygulaması")
    parser.add_argument("--debug", action="store_true", help="Pipeline kararlarını ayrıntılı göster")
    return parser.parse_args()


if __name__ == "__main__":
    run(parse_args())
