# Numan Bekir Özçelik - 04.09.2026
"""Ana uygulama"""

import argparse
import re
import shlex
import sys
import time
from datetime import datetime
from pathlib import Path
from urllib.parse import unquote, urlparse

from app import config
from app.composer import TextComposer
from app.detector import ObjectDetector
from app.extractor import ContentExtractor
from app.image_loader import ImageLoader, ImageLoadError
from app.keywords import KeywordExtractor
from app.search import WebSearcher
from app.session import SessionContext
from app.storage import Storage


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


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _new_record(storage: Storage, kind: str, value: str) -> dict:
    return {"zaman": _now(), "tur_no": storage.next_turn_no(),
            "girdi": {"tip": kind, "deger": value}}


def _save_record(storage: Storage, record: dict, status: str, emit):
    # kanıt satırı varsayılanda görünür, kayıt hatası akışı kesmez
    record["durum"] = status
    if storage.append(record):
        emit(f"✓ Kayıt: records.json · {record['tur_no']}. tur", "dim")
    else:
        emit("Kaydı dosyaya yazamadım, sohbete devam ediyorum.", "dim")


def _compose_from_web(query: str, fallback_query: str, anchor: str, words: list,
                      aliases: list, emit_debug, context_words: list = ()) -> tuple:
    """Arama, indirme, süzgeç ve derleme adımlarını tek yerden yürütür.

    Metin boş ya da tanımsız kalırsa ek sorgu denenir. Arama servisine
    ulaşılamazsa ilk aramanın hatası yukarı fırlar. İz sözlüğü kayda girer,
    turun neden böyle sonuçlandığı dosyadan okunabilir.
    """
    searcher = WebSearcher()
    results = searcher.search(query)
    emit_debug("arama", f"{len(results)} aday: " + ", ".join(r.domain for r in results))
    trace = {"aday": len(results)}

    extractor = ContentExtractor()
    pages = extractor.fetch_pages(results[:config.MAX_PAGES])
    emit_debug("indirme", f"{len(pages)}/{min(len(results), config.MAX_PAGES)} sayfa açıldı")
    sentences = extractor.select_sentences(pages, anchor, words, context_words)
    emit_debug("süzgeç", f"{len(sentences)} cümle üç katmanı geçti"
               + (f", sınıflandırıcı {extractor.last_classifier_drops} eledi"
                  if extractor.last_classifier_drops else ""))

    composer = TextComposer()
    text, sources, mapping = composer.compose(sentences, anchor, aliases)

    if fallback_query and (not text or not composer.last_has_definition):
        # metin boş ya da tanımsız kaldıysa ikinci sorguyla genişletilir,
        # aynı adres atlanır ama aynı sitenin farklı sayfası gelebilir
        emit_debug("ek sorgu", fallback_query)
        trace["ek_sorgu"] = fallback_query
        try:
            seen = {result.url for result in results}
            extra = [r for r in searcher.search(fallback_query) if r.url not in seen]
            if not extra:
                time.sleep(2)  # art arda sorguda arama servisi kısabiliyor
                extra = [r for r in searcher.search(fallback_query) if r.url not in seen]
        except Exception:
            extra = []
        emit_debug("ek arama", f"{len(extra)} yeni aday: "
                   + ", ".join(r.domain for r in extra))
        trace["ek_aday"] = len(extra)
        if extra:
            pages += extractor.fetch_pages(extra[:config.MAX_PAGES])
            sentences = extractor.select_sentences(pages, anchor, words, context_words)
            emit_debug("süzgeç", f"yedekle birlikte {len(sentences)} cümle")
            merged, merged_sources, merged_mapping = composer.compose(sentences, anchor, aliases)
            if merged:
                text, sources, mapping = merged, merged_sources, merged_mapping
    trace["sayfa"] = len(pages)
    trace["cumle"] = len(sentences)
    return text, sources, mapping, trace


def _refine_turn(value: str, session: SessionContext, storage: Storage, emit, emit_debug):
    """Düz metin girdisini son objenin çapasıyla rafine aramaya çevirir."""
    anchor = session.last_object()
    record = _new_record(storage, "text", value)
    record["obje"] = {"ad_tr": anchor}

    searcher = WebSearcher()
    query = searcher.build_query(anchor, [], user_text=value)
    record["sorgu"] = query
    emit_debug("sorgu", query)
    # alaka süzgeci önceki kelimeleri ve kullanıcının kelimelerini birlikte tanır
    words = session.last_keywords() + value.split()
    try:
        text, sources, mapping, trace = _compose_from_web(query, "", anchor, words,
                                                          [], emit_debug)
        record["arama_izi"] = trace
    except Exception as error:
        emit_debug("arama hatası", repr(error))
        emit("Şu anda web aramasına ulaşamıyorum. Bağlantını kontrol edip "
             "biraz sonra tekrar dener misin?")
        _save_record(storage, record, "arama_hatasi", emit)
        return
    if not text:
        emit(f"{tr_capitalize(anchor)} hakkında bununla ilgili bir metin "
             "derleyemedim. Farklı bir ifadeyle dener misin?")
        _save_record(storage, record, "metin_yok", emit)
        return
    emit(tr_capitalize(anchor), "title")
    emit(text)
    emit("Kaynaklar: " + ", ".join(sources), "dim")
    record["metin"] = text
    record["cumle_kaynaklari"] = [{"cumle": m["cümle"], "kaynak": m["kaynak"]} for m in mapping]
    record["kaynaklar"] = sources
    _save_record(storage, record, "tamam", emit)


def process_turn(kind: str, value: str, loader: ImageLoader, detector: ObjectDetector,
                 keywords: KeywordExtractor, session: SessionContext, storage: Storage,
                 emit, emit_debug, emit_context):
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

    record = _new_record(storage, kind, value)
    try:
        image = loader.load(value, kind)
    except ImageLoadError as error:
        emit(str(error))
        _save_record(storage, record, "yukleme_hatasi", emit)
        return
    emit_debug("görüntü", f"{image.width}x{image.height} yüklendi")

    detections = detector.detect(image)
    emit_debug("tespit", f"[{detector.last_engine}] " + (", ".join(
        f"{d.label} {d.confidence:.2f}" for d in detections) or "kutu yok"))
    dominant = detector.pick_dominant(detections, image.size)
    if dominant is None:
        emit("Bu görselde belirgin bir obje tespit edemedim. Başka bir görsel dener misin?")
        _save_record(storage, record, "obje_yok", emit)
        return
    if dominant.confidence < config.MIN_DOMINANT_CONFIDENCE or detector.last_uncertain:
        # düşük güven ya da model uyuşmazlığında emin cevap yerine dürüst mesaj
        emit_debug("düşük güven", f"{dominant.label} ({dominant.confidence:.2f})")
        emit("Görseldeki nesneden yeterince emin olamadım. Nesnenin daha net "
             "göründüğü bir görsel dener misin?")
        record["obje"] = {"ad_tr": keywords.turkish_name(dominant.label),
                          "etiket": dominant.label,
                          "guven": round(dominant.confidence, 2)}
        _save_record(storage, record, "dusuk_guven", emit)
        return

    secondary = [d.label for d in detections if d is not dominant and d.label != dominant.label]
    emit_debug("baskın", f"{dominant.label} ({dominant.confidence:.2f})"
               + (f" · ikincil: {', '.join(secondary)}" if secondary else ""))
    turkish = keywords.turkish_name(dominant.label)
    emit(f"Tespit ettiğim obje: {turkish} (güven %{dominant.confidence * 100:.0f}).")
    record["obje"] = {"ad_tr": turkish, "etiket": dominant.label,
                      "guven": round(dominant.confidence, 2)}

    scored = keywords.extract_scored(dominant.label, secondary)
    emit_debug("kelimeler", ", ".join(
        f"{item.word} [{item.source} {item.score:.1f}]" for item in scored) or "tema bulunamadı")
    if scored:
        emit(f"Anahtar kelimeler: {', '.join(item.word for item in scored)}")
    words = [item.word for item in scored]
    record["anahtar_kelimeler"] = words

    # bağlam kıyası yalnız baskın nesnenin kelimeleriyle yapılır, ikincil
    # sahne kelimeleri iki alakasız görseli akraba gösterebiliyor
    dominant_words = [item.word for item in keywords.extract_scored(dominant.label, [])]
    related = session.related_entries(turkish, dominant_words)
    context, context_words = [], []
    if related:
        # bağlam iki katmanda yaşar. cümle seçiminde yumuşak bonus, detay
        # sorgusunda yalnız taze ve ayrıştırıcı obje. kardeş isim aramayı
        # eski objeye çektiği için sorguya girmez
        context_words = [word for entry in related for word in entry["kelimeler"]]
        inject = next((entry for entry in related
                       if entry["agirlik"] >= config.CONTEXT_QUERY_MIN
                       and not session.is_sibling(entry["obje"], turkish)), None)
        if inject is not None:
            context = [inject["obje"]]
            emit_debug("bağlam", f"detay sorgusuna eklendi: {inject['obje']}; "
                       "cümle seçiminde bonus aktif")
        else:
            emit_debug("bağlam", "cümle seçiminde bonus aktif; sorguya uygun aday yok")
    elif session.entries:
        emit_debug("bağlam", "önceki turlarla kesişim yok, kullanılmadı")
    record["baglam"] = ({"obje": related[0]["obje"], "sorguda": bool(context),
                         "secimde": True} if related else None)

    # ansiklopedik nedir sorgusu önce gelir, metin zayıf kalırsa detay
    # sorgusu denenir. bileşen kelimesi ekranda kalır ama sorguya girmez,
    # aramayı saptırıyor
    query_words = [item.word for item in scored if item.source != "bileşen"]
    searcher = WebSearcher()
    category = searcher.support_term(turkish, query_words)
    query = f"{turkish} {category} nedir" if category else f"{turkish} nedir"
    detail_query = searcher.build_query(turkish, query_words, context_terms=context)
    record["sorgu"] = query
    emit_debug("sorgu", query)

    aliases = category.split() if category else []
    try:
        text, sources, mapping, trace = _compose_from_web(query, detail_query, turkish,
                                                          words, aliases, emit_debug,
                                                          context_words)
        record["arama_izi"] = trace
    except Exception as error:
        emit_debug("arama hatası", repr(error))
        emit("Şu anda web aramasına ulaşamıyorum. Bağlantını kontrol edip "
             "biraz sonra tekrar dener misin?")
        _save_record(storage, record, "arama_hatasi", emit)
        return

    if not text:
        emit(f"{tr_capitalize(turkish)} hakkında işine yarayacak bir metin "
             "derleyemedim. Farklı bir görselle ya da ifadeyle dener misin?")
        _save_record(storage, record, "metin_yok", emit)
        return
    emit(tr_capitalize(turkish), "title")
    emit(text)
    emit("Kaynaklar: " + ", ".join(sources), "dim")
    record["metin"] = text
    record["cumle_kaynaklari"] = [{"cumle": m["cümle"], "kaynak": m["kaynak"]} for m in mapping]
    record["kaynaklar"] = sources
    _save_record(storage, record, "tamam", emit)

    # başarılı tur profile girer, başarısız turlar profili etkilemez
    session.add_turn(turkish, dominant_words)
    emit_context(session.summary_line())
    emit_debug("bağlam profili", session.debug_line())


def run_plain(args, loader, detector, keywords, session, storage, storage_note):
    # tty olmayan ortam için sade satır modu
    print("Görüntülü Sohbet")
    if storage_note:
        print(storage_note)
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
            process_turn(kind, value, loader, detector, keywords, session, storage,
                         emit, emit_debug, emit_context)
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
    session = SessionContext()
    storage = Storage(config.RECORDS_PATH)
    storage_note = storage.load()

    if not (sys.stdin.isatty() and sys.stdout.isatty()):
        run_plain(args, loader, detector, keywords, session, storage, storage_note)
        return

    from types import SimpleNamespace

    from app.ui import ChatApp
    tools = SimpleNamespace(is_single_source=is_single_source,
                            find_sources=find_sources,
                            is_unsupported_file=is_unsupported_file)
    app = ChatApp(loader, detector, keywords, session, storage, process_turn,
                  classify_input, tools, debug=args.debug, storage_note=storage_note)
    farewell = app.run()
    print(farewell or "Görüşmek üzere!")


def parse_args():
    parser = argparse.ArgumentParser(description="Görüntülü sohbet uygulaması")
    parser.add_argument("--debug", action="store_true", help="Pipeline kararlarını ayrıntılı göster")
    return parser.parse_args()


if __name__ == "__main__":
    run(parse_args())
