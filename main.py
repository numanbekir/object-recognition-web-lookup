# Numan Bekir Özçelik - 06.09.2026
"""Ana uygulama. Girdiyi ayrıştırır ve bir turun tüm adımlarını yürütür."""

import argparse
from concurrent.futures import ThreadPoolExecutor
from itertools import zip_longest
import re
import shlex
import sys
from datetime import datetime
from pathlib import Path
from urllib.parse import unquote, urlparse

from app import config
from app.blocks import BlockPlanner, InfoBlock
from app.extractor import ContentExtractor, stems
from app.image_loader import ImageLoader, ImageLoadError
from app.intent import IntentBuilder
from app.search import WebSearcher
from app.session import SessionContext
from app import render, structure
from app.storage import Storage
from app.vision import VisionModel

def tr_capitalize(text: str) -> str:
    # capitalize türkçe i harfini I yapar, İ olması gerekir
    if not text:
        return text
    first = "İ" if text[0] == "i" else text[0].upper()
    return first + text[1:]

IMAGE_EXTENSIONS = (".jpg", ".jpeg", ".png", ".webp", ".bmp", ".gif", ".tif", ".tiff", ".svg")
QUIT_WORDS = ("q", "çık", "cik", "exit", "quit")
KNOWN_TLDS = ("com", "net", "org", "io", "co", "dev", "ai", "app", "edu", "gov", "tr", "uk", "de")
DOMAIN_PATTERN = re.compile(r"[a-z0-9-]+(\.[a-z0-9-]+)*\.[a-z]{2,24}", re.IGNORECASE)


def _path_exists(path: Path) -> bool:
    # çok uzun ad bileşeni linuxta hata fırlatır, dosya yok sayılır
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
    # yalnız adresler ve desteklenen dosya türleri kaynak sayılır
    if token.startswith(("http://", "https://", "file://", "www.")):
        return True
    return token.lower().endswith(IMAGE_EXTENSIONS)


def find_sources(text: str) -> list:
    """Girdideki görsel ve adres adaylarını listeler."""
    try:
        tokens = shlex.split(text)
    except ValueError:
        return []
    return [token for token in tokens if _looks_like_source(token)]


def is_unsupported_file(text: str) -> bool:
    """Sürüklenen dosya var ama görsel değilse girişte kabul edilmez."""
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
    """Metnin tamamı tek bir kaynak mı diye bakar."""
    try:
        tokens = shlex.split(text)
    except ValueError:
        return False
    return len(tokens) == 1 and _looks_like_source(tokens[0])


def normalize_schemeless(text: str):
    """Şemasız adresleri https ile tamamlar."""
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
    """Girdinin türünü ve değerini döndürür."""
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

    # sürükle bırak bazı terminallerde file önekiyle gelir
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




# tur akışı

def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _new_record(storage: Storage, kind: str, value: str) -> dict:
    return {"zaman": _now(), "tur_no": storage.next_turn_no(),
            "girdi": {"tip": kind, "deger": value}}


def _gather_blocks(object_tr: str, blocks: list, keywords: list, context_words: list,
                   view, session: SessionContext = None) -> tuple:
    """Blok sorgularını atar, sayfaları tek havuzda indirir ve her bloğu doldurur.
    Doldurma sırası vikipedi bölümü, sayfa yapısı ve düz paragraftır. Hiçbir
    kaynaktan dolmayan blok listeye girmez. Oturumda gösterilmiş sayfalar
    atlanır, yeni sayfa kalmazsa önceki kaynaklara dönülür.
    """
    emit_debug = view.detail
    searcher = WebSearcher()
    extractor = ContentExtractor()
    trace = {"sorgular": [block.query for block in blocks]}
    shown = session.shown_urls if session else set()
    anchor_stems = stems(object_tr)

    # vikipedi tanımı ve bölümleri
    definition, wiki_sections, wiki_url = None, [], ""
    if blocks and blocks[0].title == "Tanım":
        wiki = searcher.wikipedia(object_tr)
        trace["vikipedi"] = bool(wiki)
        if wiki:
            wiki_url = wiki[1]
            if wiki_url in shown:
                trace["vikipedi"] = "önceki turda gösterildi"
                emit_debug("vikipedi", "tanım önceki turda gösterildi, atlandı")
            else:
                definition = {"metin": wiki[0], "kaynak": "tr.wikipedia.org", "url": wiki_url}
                view.definition(render.definition_markdown(definition, linked=True))  # aramayı beklemeden gösterilir
            if any(block.section_hints for block in blocks):
                title = unquote(wiki_url.rsplit("/wiki/", 1)[-1]).replace("_", " ")
                wiki_sections = searcher.wikipedia_sections(title)
        emit_debug("vikipedi", ("tanım bulundu" if wiki else "sayfa yok")
                   + (f", {len(wiki_sections)} bölüm" if wiki_sections else ""))

    def run_search(text):
        try:
            return searcher.search(text)
        except Exception as error:
            trace.setdefault("arama_hatasi", []).append(f"{text}: {error!r}")
            emit_debug("arama hatası", f"{text}: {error!r}")
            return []

    # blok sorguları birlikte atılır, sonuçlar sırayla harmanlanır ki her blok pay alsın
    view.progress("web'de aranıyor")
    with ThreadPoolExecutor(max_workers=config.SEARCH_WORKERS) as pool:
        result_lists = list(pool.map(run_search, [block.query for block in blocks]))
    for block, results in zip(blocks, result_lists):
        emit_debug("arama", f"{block.title}: {len(results)} aday: "
                   + ", ".join(f"{r.domain} [{r.priority():+d}]" for r in results[:6]))
    merged, seen, origin = [], set(), {}  # sayfa hangi blok sorgularından geldi
    for row in zip_longest(*result_lists):
        for index, result in enumerate(row):
            if result is None:
                continue
            origin.setdefault(result.url, set()).add(index)
            if result.url not in seen:
                seen.add(result.url)
                merged.append(result)

    fresh = [r for r in merged if r.url not in shown]
    view.progress(f"{min(len(fresh), config.MAX_PAGES)} sayfa okunuyor")
    pages = extractor.fetch_pages(fresh[:config.MAX_PAGES])
    emit_debug("indirme", f"{len(pages)}/{min(len(fresh), config.MAX_PAGES)} yeni sayfa açıldı")
    if not pages and shown and len(fresh) < len(merged):
        # yeni kaynak kalmadıysa boş dönmek yerine önceki kaynaklar yeniden kullanılır
        emit_debug("hafıza", "yeni kaynak yok, önceki kaynaklara dönüldü")
        trace["tekrar_kaynak"] = True
        pages = extractor.fetch_pages([r for r in merged if r.url in shown][:config.MAX_PAGES])

    view.progress("bloklar hazırlanıyor")
    output, used_texts = [], set()
    for index, block in enumerate(blocks):
        entry = {"baslik": block.title, "sorgu": block.query, "paragraflar": [], "yapi": None}
        note = ""
        if block.title == "Tanım":
            if definition:
                entry["paragraflar"].append(definition)
            elif wiki_url:
                emit_debug("blok", "Tanım: önceki turda gösterildi, atlandı")
                continue  # tanım zaten verildi, yerine satış metni koymak anlamsız

        own = [page for page in pages if index in origin.get(page[0].url, ())]

        # yapılı bloklarda önce sayfa yapısı, yalnız bloğun kendi sorgusunun sayfalarından
        if block.fmt != "paragraf":
            structure_found = _extract_structure(block, own, extractor, anchor_stems)
            if structure_found:
                entry["yapi"] = structure_found
                note = f"yapı ({block.fmt}) {structure_found['kaynak']}"

        # vikipedinin ilgili bölümü
        if not entry["paragraflar"] and not entry["yapi"] and block.section_hints:
            for section in wiki_sections:
                url = f"{wiki_url}#{section['baslik'].replace(' ', '_')}"
                if url in shown or section["metin"] in used_texts:
                    continue
                if any(hint in section["baslik"].lower() for hint in block.section_hints):
                    entry["paragraflar"].append({"metin": section["metin"],
                                                 "kaynak": "tr.wikipedia.org", "url": url})
                    used_texts.add(section["metin"])
                    note = f"vikipedi bölümü '{section['baslik']}'"
                    break

        # düz paragraf
        remaining = block.limit - len(entry["paragraflar"])
        if remaining > 0 and not entry["yapi"]:
            if block.required_hints:
                options = dict(keywords=list(block.hints), hint_stems=stems(" ".join(block.hints)),
                               min_hint_hits=config.BLOCK_MIN_HINT_HITS,
                               min_score=config.BLOCK_MIN_SIMILARITY, exclude_texts=used_texts,
                               limit=remaining)
                selected = extractor.select_passages(own, object_tr, **options)
                note = "kendi sayfalarından" if selected else ""
                if not selected:
                    options["min_score"] = config.BLOCK_POOL_MIN_SIMILARITY
                    selected = extractor.select_passages(pages, object_tr, **options)
                    note = "havuzdan" if selected else "eşik altı, gösterilmedi"
            else:
                selected = extractor.select_passages(
                    pages, object_tr, block.hints + list(keywords), context_words,
                    limit=remaining, exclude_texts=used_texts)
            for passage in selected:
                used_texts.add(passage.text)
                entry["paragraflar"].append({"metin": passage.text, "kaynak": passage.source,
                                             "url": passage.url})
                note += f" · {passage.source} {passage.score:.2f}"
        emit_debug("blok", f"{block.title}: {len(entry['paragraflar'])} paragraf"
                   + (", yapı" if entry["yapi"] else "") + (f" · {note}" if note else ""))
        if entry["paragraflar"] or entry["yapi"]:
            output.append(entry)
    trace.update({"aday": len(merged), "sayfa": len(pages), "blok": len(output)})
    return output, trace


def _extract_structure(block, pages: list, extractor: ContentExtractor, anchor_stems: list):
    """Sayfa yapısından bloğun biçimine uygun içeriği çıkarır. Sayfa başlığı objeyi anmalıdır."""
    relevant = [(result, extractor.html.get(result.url)) for result, _ in pages
                if extractor.html.get(result.url)
                and any(stem in result.title.lower() for stem in anchor_stems)]
    if block.fmt == "tarif":
        # ikisini de veren sayfa tercih edilir, yoksa malzeme ve adımlar ayrı sayfalardan birleşir
        parsed = [(result, structure.pick_list(structure.extract_lists(html), ("malzeme",), 10),
                   structure.extract_steps(html)[:8]) for result, html in relevant]
        complete = next(((r, i, s) for r, i, s in parsed if i and s), None)
        if complete:
            result, found, steps = complete
            return {"tip": "tarif", "malzemeler": found["maddeler"], "adimlar": steps,
                    "kaynak": result.domain, "url": result.url}
        with_items = next(((r, i) for r, i, _ in parsed if i), None)
        with_steps = next(((r, s) for r, _, s in parsed if s), None)
        if with_items or with_steps:
            main = with_items[0] if with_items else with_steps[0]
            shape = {"tip": "tarif", "malzemeler": with_items[1]["maddeler"] if with_items else [],
                     "adimlar": with_steps[1] if with_steps else [],
                     "kaynak": main.domain, "url": main.url}
            if with_items and with_steps and with_steps[0] is not with_items[0]:
                shape["adim_kaynak"] = with_steps[0].domain
                shape["adim_url"] = with_steps[0].url
            return shape
    elif block.fmt == "basliklar":
        candidates = [(result.domain, result.url, structure.extract_sections(html))
                      for result, html in relevant]
        best = structure.best_sections(candidates, anchor_stems, 5)
        if best:
            source, url, sections = best
            return {"tip": "basliklar", "ogeler": sections, "kaynak": source, "url": url}
    elif block.fmt == "madde":
        hints = tuple(stem for stem in stems(" ".join(block.hints)))
        for result, html in relevant:
            found = structure.pick_list(structure.extract_lists(html), hints, 8)
            if found:
                return {"tip": "madde", "etiket": found["etiket"], "maddeler": found["maddeler"],
                        "kaynak": result.domain, "url": result.url}
    return None


def _present(object_tr: str, blocks: list, record: dict, view, session: SessionContext):
    """Blokları markdown olarak görünüme verir, kayda yazar ve kaynakları hafızaya alır."""
    text, sources = render.blocks_markdown(blocks)
    view.body(render.blocks_markdown(blocks, for_screen=True)[0], sources, render.source_urls(blocks))
    record["bloklar"] = blocks
    record["metin"] = text
    record["kaynaklar"] = sources
    urls = [p["url"] for block in blocks for p in block["paragraflar"]]
    urls += [block["yapi"]["url"] for block in blocks if block["yapi"]]
    urls += [block["yapi"]["adim_url"] for block in blocks
             if block["yapi"] and block["yapi"].get("adim_url")]
    session.remember_shown(urls)


def _save(storage: Storage, record: dict, status: str, view):
    # kayıt hatası akışı kesmez
    record["durum"] = status
    if storage.append(record):
        view.saved(record["tur_no"])
    else:
        view.message("Kaydı dosyaya yazamadım, sohbete devam ediyorum.")


def _refine_turn(value: str, session: SessionContext, storage: Storage, view):
    """Düz metin girdisi son obje bağlamında yeni bir arama yapar."""
    anchor = session.last_object()
    record = _new_record(storage, "text", value)
    record["obje"] = {"ad_tr": anchor}
    query = WebSearcher.build_query(anchor, user_text=value)
    view.head(anchor, None, [], query, note=f"soru · {value}")
    view.detail("sorgu", query)
    blocks = [InfoBlock("Cevap", query, value.split(), limit=config.MAX_PASSAGES)]
    found, trace = _gather_blocks(anchor, blocks, session.last_keywords() + value.split(),
                                  [], view, session=session)
    record["arama_izi"] = trace
    if not found:
        view.message(f"{tr_capitalize(anchor)} hakkında bununla ilgili bir metin bulamadım. "
                     "Farklı bir ifadeyle dener misin?")
        _save(storage, record, "metin_yok", view)
        return
    _present(anchor, found, record, view, session)
    _save(storage, record, "tamam", view)


def process_turn(kind: str, value: str, loader: ImageLoader, vision: VisionModel,
                 session: SessionContext, storage: Storage, view,
                 intent: IntentBuilder = None, planner: BlockPlanner = None):
    """Bir kullanıcı turunu işler ve sonuçları görünüm nesnesine kademeli olarak verir.

    Görünüm nesnesi head, definition, body, progress, message, detail, saved ve
    context çağrılarını alır. Terminal arayüzü bunları bir kart üzerinde,
    düz mod satır satır gösterir.
    """
    if kind == "too_long":
        view.message("Girdi biraz uzun görünüyor. Daha kısa bir adres ya da mesaj dener misin?")
        return
    if kind == "bad_scheme":
        view.message("Yalnızca http ve https adreslerini ve yerel dosya yollarını destekliyorum.")
        return
    if kind == "missing_file":
        view.message(f"Bu konumda bir dosya bulamadım, {value}. Yolu kontrol eder misin?")
        return
    if kind == "multi":
        view.message("Aynı anda tek görsel işleyebiliyorum. Tek bir görsel ya da adres verir misin?")
        return
    intent = intent or IntentBuilder()
    planner = planner or BlockPlanner()
    if kind == "text":
        if session.last_object() is None:
            view.message("Henüz analiz edilmiş bir görsel yok. Önce bir görsel adresi ya da dosya yolu verir misin?")
            return
        _refine_turn(value, session, storage, view)
        return

    # görüntü
    record = _new_record(storage, kind, value)
    view.progress("görüntü yükleniyor")
    try:
        image = loader.load(value, kind)
    except ImageLoadError as error:
        view.message(str(error))
        _save(storage, record, "yukleme_hatasi", view)
        return
    view.detail("görüntü", f"{image.width}x{image.height} yüklendi")

    # obje ve anahtar kelimeler
    view.progress("obje tanınıyor")
    prediction, keywords = vision.analyze(image)
    object_tr = prediction.name_tr
    view.detail("adaylar", "; ".join(f"{vision.turkish_name(l)} {s:.2f}" for l, s in prediction.candidates))
    if prediction.reconciled_from:
        view.detail("uzlaşma", f"{prediction.reconciled_from} yerine temalarla uyumlu aday, {object_tr}")
        record["uzlasma"] = {"onceki_obje": prediction.reconciled_from}
    confident = prediction.confidence >= config.MIN_CONFIDENCE
    words = [item.word for item in keywords]
    view.detail("temalar", ", ".join(f"{k.word} [{k.theme} {k.score:.2f}]" for k in keywords))
    record["obje"] = {"ad_tr": object_tr, "etiket": prediction.label,
                      "guven": round(prediction.confidence, 2)}
    record["anahtar_kelimeler"] = words

    # bağlam, önceki turla ortak kelime varsa o tur aynı konudadır
    shared = session.shared_context(object_tr, words)
    context_words, previous = [], None
    if shared:
        previous, common = shared
        context_words = [common]
        view.detail("bağlam", f"{previous} ile ortak kelime, {common}")
        record["baglam"] = {"onceki_obje": previous, "ortak_kelime": common}
    else:
        record["baglam"] = None

    # arama niyeti, objeden emin değilsek kelimeler sorguya girmez
    if confident:
        query = intent.build(object_tr, words, previous)
    else:
        query = object_tr
        view.detail("niyet", "düşük güven, kelimeler sorguya alınmadı")
    record["arama_niyeti"] = query
    notes = []
    if not confident:
        notes.append("Tam emin olamadım, diğer adaylar " + ", ".join(n for n, _ in prediction.alternatives))
    if session.times_seen(object_tr):
        notes.append("Bu obje hakkında daha önce konuştuk, bu kez farklı kaynaklardan devam ediyorum.")
    view.head(object_tr, prediction.confidence, words, query, note=" · ".join(notes),
              confident=confident, size=f"{image.width}x{image.height}")

    # bilgi blokları
    blocks = planner.plan(object_tr, words, query, confident=confident)
    view.detail("bloklar", f"aile {planner.family(words)}, " + ", ".join(b.title for b in blocks))
    found, trace = _gather_blocks(object_tr, blocks, words, context_words, view, session=session)
    record["arama_izi"] = trace
    if trace.get("tekrar_kaynak"):
        view.message("Yeni bir kaynak bulamadım, daha önce gösterdiğim bilgileri hatırlatıyorum.")
    if not found:
        view.message(f"{tr_capitalize(object_tr)} hakkında şu anda bir metin derleyemedim. "
                     "Bağlantını kontrol edip tekrar dener misin?")
        _save(storage, record, "metin_yok", view)
        return
    _present(object_tr, found, record, view, session)
    _save(storage, record, "tamam", view)

    # bağlam güncellenir
    session.add_turn(object_tr, words)
    view.context(session.summary_line())


# arayüzler

class PlainView:
    """Düz mod görünümü, her bildirimi satır olarak basar."""

    def __init__(self, debug: bool):
        self.debug = debug
        self.console = None

    def _print_markdown(self, text: str):
        from rich.console import Console
        from rich.markdown import Markdown
        self.console = self.console or Console()
        self.console.print(Markdown(text))

    def head(self, object_tr, confidence, keywords, intent, note="", confident=True, size=""):
        if confidence is None:
            print(f"\n{tr_capitalize(object_tr)}")
        elif confident:
            print(f"\n{tr_capitalize(object_tr)}  güven %{confidence * 100:.0f}")
        else:
            print(f"\nEmin değilim, en yakın tahmin {object_tr}  güven %{confidence * 100:.0f}")
        if keywords:
            print("anahtar kelimeler · " + ", ".join(keywords))
        print(f"araştırılan konu · {intent}")
        if note:
            print(note)

    def definition(self, markdown):
        pass  # düz modda tanım gövdeyle birlikte basılır

    def body(self, markdown, sources, urls=None):
        print()
        self._print_markdown(markdown)
        print("kaynaklar · " + render.sources_line(sources))

    def progress(self, text):
        if self.debug:
            print(f"… {text}")

    def message(self, text):
        print(text)

    def detail(self, stage, text):
        if self.debug:
            print(f"{stage} · {text}")

    def saved(self, turn_no):
        print(f"kaydedildi · {turn_no}. tur")

    def context(self, line):
        print(f"↻ {line}")


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
            print(f"Ayrıntı, {error!r}")
        return
    print(f"Model hazır, {vision.vocab_size} kavram.")
    view = PlainView(args.debug)

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
            process_turn(kind, value, loader, vision, session, storage, view)
        except KeyboardInterrupt:
            print("İşlemi iptal ettim.")
        except Exception as error:
            # tek turda oluşan sorun uygulamayı kapatmasın
            print("Beklenmeyen bir sorun oluştu. Tekrar dener misin?")
            view.detail("hata", repr(error))


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
