# Numan Bekir Özçelik - 06.09.2026
"""Ana uygulama: girdi ayrıştırma ve tur akışı.

    girdi ─► görüntü yükle ─► CLIP: obje + anahtar kelimeler ─► kaydet
          ─► Vikipedi tanımı + web araması ─► alakalı paragraflar ─► göster ─► kaydet
"""

import argparse
import re
import shlex
import sys
from datetime import datetime
from pathlib import Path
from urllib.parse import unquote, urlparse

from app import config
from app.extractor import ContentExtractor
from app.image_loader import ImageLoader, ImageLoadError
from app.search import WebSearcher
from app.session import SessionContext
from app.storage import Storage
from app.vision import VisionModel

def tr_capitalize(text: str) -> str:
    # python'un capitalize'ı türkçe i'yi I yapar, İ olmalı
    if not text:
        return text
    first = "İ" if text[0] == "i" else text[0].upper()
    return first + text[1:]

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
    """Tür ve değer ikilisi döndürür, dokuz girdi türü vardır."""
    stripped = raw.strip()
    if not stripped:
        return "empty", ""
    if stripped.lower() in QUIT_WORDS:
        return "quit", ""
    if len(stripped) > config.MAX_INPUT_LENGTH:
        return "too_long", ""

    # çoklu denetim tırnak temizliğinden önce gelir, shlex tırnaklı yolları doğru böler
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
        # bazı terminaller sürüklenen yoldaki boşlukları ters bölüyle kaçışlar
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




# --- tur akışı ---

def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _new_record(storage: Storage, kind: str, value: str) -> dict:
    return {"zaman": _now(), "tur_no": storage.next_turn_no(),
            "girdi": {"tip": kind, "deger": value}}


def _save_record(storage: Storage, record: dict, status: str, emit):
    # kayıt hatası akışı kesmez
    record["durum"] = status
    if storage.append(record):
        emit(f"✓ Kayıt: records.json · {record['tur_no']}. tur", "dim")
    else:
        emit("Kaydı dosyaya yazamadım, sohbete devam ediyorum.", "dim")


def _gather_text(object_tr: str, query: str, keywords: list, context_words: list,
                 emit_debug, with_wikipedia: bool = True) -> tuple:
    """Vikipedi tanımı ve web paragraflarını toplar, (paragraflar, iz) döndürür.

    Her paragraf {"metin", "kaynak", "url"} sözlüğüdür. Arama servisi
    düşerse Vikipedi tek başına yeter, ikisi de boşsa liste boş döner.
    """
    searcher = WebSearcher()
    extractor = ContentExtractor()
    passages, trace = [], {"sorgu": query}

    if with_wikipedia:
        wiki = searcher.wikipedia(object_tr)
        trace["vikipedi"] = bool(wiki)
        emit_debug("vikipedi", "tanım bulundu" if wiki else "sayfa yok")
        if wiki:
            passages.append({"metin": wiki[0], "kaynak": "tr.wikipedia.org", "url": wiki[1]})

    try:
        results = searcher.search(query)
    except Exception as error:
        results = []
        trace["arama_hatasi"] = repr(error)
        emit_debug("arama hatası", repr(error))
    emit_debug("arama", f"{len(results)} aday: " + ", ".join(r.domain for r in results))
    pages = extractor.fetch_pages(results[:config.MAX_PAGES])
    emit_debug("indirme", f"{len(pages)}/{min(len(results), config.MAX_PAGES)} sayfa açıldı")
    for passage in extractor.select_passages(pages, object_tr, keywords, context_words):
        emit_debug("paragraf", f"{passage.source} · benzerlik {passage.score:.2f}")
        passages.append({"metin": passage.text, "kaynak": passage.source, "url": passage.url})
    trace.update({"aday": len(results), "sayfa": len(pages), "paragraf": len(passages)})
    return passages, trace


def _show_text(object_tr: str, passages: list, record: dict, emit):
    emit(tr_capitalize(object_tr), "title")
    for passage in passages:
        emit(passage["metin"])
        emit(f"— {passage['kaynak']}", "dim")
    record["metin"] = "\n\n".join(p["metin"] for p in passages)
    record["paragraflar"] = passages
    record["kaynaklar"] = list(dict.fromkeys(p["kaynak"] for p in passages))


def _refine_turn(value: str, session: SessionContext, storage: Storage, emit, emit_debug):
    """Düz metin girdisi son obje bağlamında yeni bir arama yapar."""
    anchor = session.last_object()
    record = _new_record(storage, "text", value)
    record["obje"] = {"ad_tr": anchor}
    query = WebSearcher.build_query(anchor, user_text=value)
    emit_debug("sorgu", query)
    passages, trace = _gather_text(anchor, query, session.last_keywords() + value.split(),
                                   [], emit_debug, with_wikipedia=False)
    record["arama_izi"] = trace
    if not passages:
        emit(f"{tr_capitalize(anchor)} hakkında bununla ilgili bir metin bulamadım. "
             "Farklı bir ifadeyle dener misin?")
        _save_record(storage, record, "metin_yok", emit)
        return
    _show_text(anchor, passages, record, emit)
    _save_record(storage, record, "tamam", emit)


def process_turn(kind: str, value: str, loader: ImageLoader, vision: VisionModel,
                 session: SessionContext, storage: Storage, emit, emit_debug, emit_context):
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
        if session.last_object() is None:
            emit("Henüz analiz edilmiş bir görsel yok. Önce bir görsel URL'si ya da dosya yolu verir misin?")
            return
        _refine_turn(value, session, storage, emit, emit_debug)
        return

    # 1. görüntü
    record = _new_record(storage, kind, value)
    try:
        image = loader.load(value, kind)
    except ImageLoadError as error:
        emit(str(error))
        _save_record(storage, record, "yukleme_hatasi", emit)
        return
    emit_debug("görüntü", f"{image.width}x{image.height} yüklendi")

    # 2. obje ve anahtar kelimeler
    prediction, keywords = vision.analyze(image)
    object_tr = prediction.name_tr
    emit_debug("adaylar", f"{object_tr} {prediction.confidence:.2f}; " + "; ".join(
        f"{name} {score:.2f}" for name, score in prediction.alternatives))
    if prediction.confidence >= config.MIN_CONFIDENCE:
        emit(f"Tespit ettiğim obje: {object_tr} (güven %{prediction.confidence * 100:.0f}).")
    else:
        # düşük güvende kesin konuşulmaz ama akış durmaz, alternatifler de söylenir
        others = ", ".join(name for name, _ in prediction.alternatives)
        emit(f"Tam emin olamadım, en yakın tahminim {object_tr} "
             f"(güven %{prediction.confidence * 100:.0f}); diğer adaylar: {others}.")
    words = [item.word for item in keywords]
    emit_debug("temalar", ", ".join(f"{k.word} [{k.theme} {k.score:.2f}]" for k in keywords))
    if words:
        emit(f"Anahtar kelimeler: {', '.join(words)}")
    record["obje"] = {"ad_tr": object_tr, "etiket": prediction.label,
                      "guven": round(prediction.confidence, 2)}
    record["anahtar_kelimeler"] = words

    # 3. bağlam: önceki turla ortak kelime varsa sorguya girer
    shared = session.shared_context(object_tr, words)
    context_words = []
    if shared:
        previous, common = shared
        context_words = [common]
        emit_debug("bağlam", f"{previous} ile ortak kelime: {common}")
        record["baglam"] = {"onceki_obje": previous, "ortak_kelime": common}
    else:
        record["baglam"] = None
    query = WebSearcher.build_query(object_tr, context_words[0] if context_words else "")
    emit_debug("sorgu", query)

    # 4. web metni
    passages, trace = _gather_text(object_tr, query, words, context_words, emit_debug)
    record["arama_izi"] = trace
    if not passages:
        emit(f"{tr_capitalize(object_tr)} hakkında şu anda bir metin derleyemedim. "
             "Bağlantını kontrol edip tekrar dener misin?")
        _save_record(storage, record, "metin_yok", emit)
        return
    _show_text(object_tr, passages, record, emit)
    _save_record(storage, record, "tamam", emit)

    # 5. bağlam güncellenir
    session.add_turn(object_tr, words)
    emit_context(session.summary_line())


# --- arayüzler ---

def run_plain(args, loader, vision, session, storage, storage_note):
    # tty olmayan ortam için sade satır modu
    print("Görüntülü Sohbet")
    if storage_note:
        print(storage_note)
    print("Model yükleniyor..." if vision.is_ready_on_disk()
          else "Model hazırlanıyor, ilk çalıştırmada indirme ve kodlama yapılır...")
    try:
        vision.load()
    except Exception as error:
        print("Modeli hazırlayamadım. İlk çalıştırma için internet bağlantısı gerekiyor, "
              "bağlantını kontrol edip tekrar dener misin?")
        if args.debug:
            print(f"Ayrıntı: {error!r}")
        return
    print(f"Model hazır ({vision.vocab_size} kavram).")

    def emit(message, style=""):
        print(message)

    def emit_debug(stage, message):
        if args.debug:
            print(f"{stage} · {message}")

    def emit_context(line):
        print(f"↻ {line}")

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
            process_turn(kind, value, loader, vision, session, storage,
                         emit, emit_debug, emit_context)
        except KeyboardInterrupt:
            print("İşlemi iptal ettim.")
        except Exception as error:
            # tek turda oluşan sorun uygulamayı kapatmasın
            print("Beklenmeyen bir sorun oluştu. Tekrar dener misin?")
            emit_debug("hata", repr(error))


def run(args):
    loader = ImageLoader()
    vision = VisionModel()
    session = SessionContext()
    storage = Storage(config.RECORDS_PATH)
    storage_note = storage.load()

    if args.plain or not (sys.stdin.isatty() and sys.stdout.isatty()):
        run_plain(args, loader, vision, session, storage, storage_note)
        return

    from types import SimpleNamespace

    from app.ui import ChatApp
    tools = SimpleNamespace(is_single_source=is_single_source,
                            find_sources=find_sources,
                            is_unsupported_file=is_unsupported_file)
    app = ChatApp(loader, vision, session, storage, process_turn,
                  classify_input, tools, debug=args.debug, storage_note=storage_note)
    farewell = app.run()
    print(farewell or "Görüşmek üzere!")


def parse_args():
    parser = argparse.ArgumentParser(description="Görüntülü sohbet uygulaması")
    parser.add_argument("--debug", action="store_true", help="Pipeline kararlarını ayrıntılı göster")
    parser.add_argument("--plain", action="store_true", help="Terminal arayüzü yerine düz satır modu")
    return parser.parse_args()


if __name__ == "__main__":
    run(parse_args())
