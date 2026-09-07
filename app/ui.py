# Numan Bekir Özçelik - 06.09.2026
"""Terminal arayüzü. İş akışını bilmez, yalnız tur işleyicisini çağırır."""

import os
import re
import time
import webbrowser

from rich.markup import escape
from textual import events, work
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Grid, Horizontal, Vertical, VerticalScroll
from textual.widgets import Collapsible, Markdown, Static, TextArea

URL_PATTERN = re.compile(r"https?://\S+")
INPUT_MAX_LINES = 3  # input alanı en fazla bu değer kadar satır oluşturur


def linkify(text: str) -> str:
    # adresler ctrl+click ile açılan terminal köprüsüne dönüşür
    parts, last = [], 0
    for match in URL_PATTERN.finditer(text):
        parts.append(escape(text[last:match.start()]))
        url = match.group()
        parts.append(f"[link='{url}']{escape(url)}[/link]")
        last = match.end()
    parts.append(escape(text[last:]))
    return "".join(parts)


class SourceInput(TextArea):
    def _token_span(self):
        token = getattr(self.app, "attached_token", "")
        if not token:
            return None
        index = self.text.find(token)
        if index < 0:
            return None
        return index, index + len(token)

    async def _on_key(self, event: events.Key):
        if event.key == "enter":
            event.stop()
            event.prevent_default()
            self.app.submit_current()
            return

        # belirteç bölünmez
        span = self._token_span()
        if span:
            start, end = span
            column = self.cursor_location[1]
            if event.key == "backspace" and start < column <= end:
                event.stop()
                event.prevent_default()
                self.app.remove_token()
                return
            if event.key == "delete" and start <= column < end:
                event.stop()
                event.prevent_default()
                self.app.remove_token()
                return
            if event.key == "left" and start < column <= end:
                event.stop()
                event.prevent_default()
                self.cursor_location = (0, start)
                return
            if event.key == "right" and start <= column < end:
                event.stop()
                event.prevent_default()
                self.cursor_location = (0, end)
                return
        await super()._on_key(event)

    def on_mouse_move(self, event: events.MouseMove):
        # belirtecin üzerine gelince baloncukta ilgili dosya veya url tam adresi belirir
        span = self._token_span()
        source = None
        if span:
            start, end = span
            column = event.x + self.scroll_offset.x
            if start <= column < end:
                source = self.app.attached_source
        if self.tooltip != source:
            self.tooltip = source

    def on_leave(self, event: events.Leave):
        self.tooltip = None

    async def _on_paste(self, event: events.Paste):
        # yapıştırma alana varmadan tek merkezden denetlenir
        event.stop()
        event.prevent_default()
        self.app.handle_paste_text(event.text)


class TurnCard(Vertical):
    """Bir turun tüm çıktısını tutan kart. Kademeli dolar, gövde yazılıyormuş gibi akar."""

    DEFAULT_CSS = """
    TurnCard { height: auto; border: round $primary 60%; padding: 0 1; margin: 0 0 1 0; }
    TurnCard #headbox { height: auto; border: round $primary 40%; margin-bottom: 1; }
    TurnCard .hcell { height: 1; padding: 0 1; text-wrap: nowrap; text-overflow: ellipsis;
                      border-right: solid $primary 40%; }
    TurnCard #cell_object { width: 40; }
    TurnCard #cell_keywords { width: 52; }
    TurnCard #cell_intent { width: 1fr; border-right: none; }
    TurnCard .card-context { color: $text-muted; margin-bottom: 1; }
    TurnCard .card-note { color: $warning; }
    TurnCard .card-message { color: $warning; margin-top: 1; }
    TurnCard Markdown { margin: 0; padding: 0; background: transparent; }
    TurnCard MarkdownH3 { margin: 1 0 0 0; padding: 0; background: transparent; color: orange; }
    TurnCard Markdown, TurnCard MarkdownBlock { link-color: dodgerblue; link-style: none; link-background: transparent;
                                               link-color-hover: dodgerblue; link-style-hover: underline; link-background-hover: transparent; }
    TurnCard #sources { link-color: dodgerblue; link-style: none; link-background: transparent;
                        link-color-hover: dodgerblue; link-style-hover: underline; link-background-hover: transparent; }
    TurnCard #progress { height: auto; color: $text-muted; text-style: italic; margin-top: 1; }
    TurnCard #progress_label { width: 1fr; }
    TurnCard #progress_time { width: auto; }
    TurnCard #footer { height: auto; margin-top: 1; border-top: solid $primary 30%; }
    TurnCard #sources { width: 1fr; color: $text-muted; }
    TurnCard #stats { width: auto; color: $text-muted; }
    TurnCard Collapsible { margin-top: 1; padding: 0; border: none; background: transparent; }
    TurnCard .detail { color: $text-muted; }
    """
    WORDS_PER_TICK = 6
    TICK = 0.03

    def __init__(self, debug: bool = False):
        super().__init__()
        self.debug = debug
        self._stats = {}
        self._started = time.monotonic()
        self._progress_timer = None
        self._dots = 0
        self._full = ""  # gövdenin hedef metni
        self._pos = 0  # ekranda yazılmış karakter sayısı
        self._stream_timer = None

    def compose(self) -> ComposeResult:
        with Horizontal(id="headbox"):
            yield Static("", id="cell_object", classes="hcell")
            yield Static("", id="cell_keywords", classes="hcell")
            yield Static("", id="cell_intent", classes="hcell")
        yield Markdown("", id="body")
        with Horizontal(id="progress"):
            yield Static("", id="progress_label")
            yield Static("", id="progress_time")
        with Horizontal(id="footer"):
            yield Static("", id="sources")
            yield Static("", id="stats")
        if self.debug:
            yield Collapsible(title="ayrıntılar", collapsed=True, id="details")

    def on_mount(self):
        self.query_one("#progress").display = False
        self.query_one("#footer").display = False

    def _scroll(self):
        parent = self.parent
        if isinstance(parent, VerticalScroll):
            parent.scroll_end(animate=False)

    @staticmethod
    def _title_case(text: str) -> str:
        return " ".join(("İ" if w[:1] == "i" else w[:1].upper()) + w[1:] for w in text.split())

    def set_head(self, object_tr, confidence, keywords, intent, note="", confident=True, size="",
                 previous=None):
        title = self._title_case(object_tr) if object_tr else ""
        label = "BULUNAN" if confidence is None or confident else "EN YAKIN TAHMİN"
        right = []
        if confidence is not None:
            right.append(f"güven %{confidence * 100:.0f}")
        if size:
            right.append(size)
        detail = " · ".join(right)
        words = " · ".join(self._title_case(k) for k in keywords)
        cells = [
            ("#cell_object", label, f"[b]{escape(title)}[/b]" + (f"  [dim]{escape(detail)}[/]" if detail else ""),
             title + (f"  {detail}" if detail else "")),
            ("#cell_keywords", "ANAHTAR KELİMELER", escape(words), words),
            ("#cell_intent", "ARAŞTIR", self._highlight(intent, previous) if intent else "", intent or ""),
        ]
        for cell_id, name, markup, plain in cells:
            cell = self.query_one(cell_id, Static)
            cell.update(f"[orange]{name}:[/] {markup}" if plain else f"[orange]{name}:[/]")
            cell.tooltip = f"{name.capitalize()}, {plain}" if plain else None  # kırpılsa da tam içerik görünür
        if note:
            self.mount(Static(escape(note), classes="card-note"), after=self.query_one("#headbox"))
        self._scroll()

    @staticmethod
    def _highlight(intent: str, previous) -> str:
        """Niyet cümlesinde önceki turdan gelen kelimeler turuncu gösterilir."""
        marked = {w.lower() for w in (previous or "").split()}
        words = [f"[orange]{escape(w)}[/]" if w.lower() in marked else escape(w) for w in intent.split()]
        return "[i]" + " ".join(words) + "[/i]"

    def add_context(self, previous, family_label, injected):
        text = f"↻ önceki tur [orange]{escape(previous)}[/] ile aynı konu, {escape(family_label)}"
        if injected:
            text += f" · sorguya [orange]{escape(previous)}[/] eklendi"
        self.mount(Static(text, classes="card-context"), after=self.query_one("#headbox"))
        self._scroll()

    # gövde yazılıyormuş gibi akar

    def set_body(self, markdown: str):
        self._full, self._pos = markdown, len(markdown)
        self.query_one("#body", Markdown).update(markdown)
        self._scroll()

    def stream_body(self, markdown: str):
        common = len(os.path.commonprefix([self._full, markdown]))
        self._pos = min(self._pos, common)  # ortak önek zaten yazıldı, yalnız devamı akar
        self._full = markdown
        if self._stream_timer is None:
            self._stream_timer = self.set_interval(self.TICK, self._stream_tick)

    def _stream_tick(self):
        if self._pos >= len(self._full):
            self._stream_timer.stop()
            self._stream_timer = None
            return
        pos = self._pos
        for _ in range(self.WORDS_PER_TICK):
            nxt = self._full.find(" ", pos + 1)
            pos = len(self._full) if nxt < 0 else nxt
        self._pos = pos
        self.query_one("#body", Markdown).update(self._full[:pos])
        self._scroll()

    def set_sources(self, sources: list, urls: dict = None):
        footer = self.query_one("#footer")
        footer.display = True
        urls = urls or {}
        parts = []
        for index, source in enumerate(sources, 1):
            label = escape(source)
            if urls.get(source):
                url = urls[source].replace("'", "%27")
                label = f"[@click=app.open_url('{url}')]{label}[/]"  # tıklayınca tarayıcıda açılır
            parts.append(f"\\[{index}] {label}")
        self.query_one("#sources", Static).update("  ".join(parts))
        self.query_one("#sources", Static).tooltip = "Kaynağı tarayıcıda açmak için tıkla"

    # ilerleme satırı, nokta canlanır ve süre akar

    def set_progress(self, text: str):
        row = self.query_one("#progress")
        if not text:
            row.display = False
            if self._progress_timer is not None:
                self._progress_timer.stop()
                self._progress_timer = None
            return
        row.display = True
        self._progress_text = text
        self._progress_tick()
        if self._progress_timer is None:
            self._progress_timer = self.set_interval(0.3, self._progress_tick)
        self._scroll()

    def _progress_tick(self):
        self._dots = (self._dots + 1) % 4
        dots = "." * (self._dots or 1)
        self.query_one("#progress_label", Static).update(f"{escape(self._progress_text)} {dots}")
        self.query_one("#progress_time", Static).update(f"⏱ {int(time.monotonic() - self._started)} sn")

    def add_message(self, text: str):
        self.mount(Static(linkify(text), classes="card-message"), before=self.query_one("#progress"))
        self._scroll()

    def add_detail(self, stage: str, text: str):
        if not self.debug:
            return
        details = self.query_one("#details", Collapsible)
        # satırlar katlanan içerik kabına girer, yoksa başlığın dışında sürekli görünür kalır
        details.query_one(Collapsible.Contents).mount(
            Static(f"[b]{escape(stage)}[/b]  {escape(text)}", classes="detail"))

    def set_stat(self, key: str, value: str):
        self._stats[key] = value
        self.query_one("#footer").display = True
        stats = self.query_one("#stats", Static)
        parts = []
        if "kayit" in self._stats:
            parts.append(("kaydedildi · " if self.debug else "[green]✓[/] ") + escape(self._stats["kayit"]))
            stats.tooltip = f"Sonuçlar kaydedildi, {self._stats['kayit']}"
        if "sure" in self._stats:
            parts.append("⏱ " + escape(self._stats["sure"]))
        stats.update(" · ".join(parts))

    def finish(self, elapsed: float):
        self.set_progress("")
        self.set_stat("sure", f"{elapsed:.1f} sn")
        self._scroll()


class CardView:
    """Tur işleyicisinin çalışan iş parçacığından karta güvenli erişimi."""

    def __init__(self, app, card: TurnCard):
        self.app = app
        self.card = card

    def head(self, object_tr, confidence, keywords, intent, note="", confident=True, size="",
             previous=None):
        self.app.call_from_thread(self.card.set_head, object_tr, confidence, keywords, intent,
                                  note, confident, size, previous)

    def context_note(self, previous, family_label, injected):
        self.app.call_from_thread(self.card.add_context, previous, family_label, injected)

    def definition(self, markdown):
        self.app.call_from_thread(self.card.stream_body, markdown)

    def body(self, markdown, sources, urls=None):
        self.app.call_from_thread(self.card.stream_body, markdown)
        self.app.call_from_thread(self.card.set_sources, sources, urls)

    def progress(self, text):
        self.app.call_from_thread(self.card.set_progress, text)

    def message(self, text):
        self.app.call_from_thread(self.card.add_message, text)

    def detail(self, stage, text):
        self.app.call_from_thread(self.card.add_detail, stage, text)

    def saved(self, turn_no):
        self.app.call_from_thread(self.card.set_stat, "kayit", f"{turn_no}. tur")

    def context(self, turn_no, object_tr, previous, family_label, chain, repeat):
        self.app.call_from_thread(self.app._set_context, turn_no, object_tr, previous,
                                  family_label, chain, repeat)

    def finish(self, elapsed):
        self.app.call_from_thread(self.card.finish, elapsed)


class ChatApp(App):
    TITLE = "Görüntülü Sohbet"
    BINDINGS = [Binding("ctrl+c", "quit", show=False)]

    CSS = """
    Screen { layout: vertical; }
    #topbox {
        height: auto;
        border: round $primary;
        margin: 1 1 0 1;
        padding: 1 2;
    }
    #title { width: 1fr; }
    #hints { width: auto; color: $text-muted; text-align: right; }
    #log { padding: 1 2; scrollbar-size: 0 0; }
    #log Static { margin-bottom: 0; }
    .user {
        border-left: thick $primary;
        background: $primary 12%;
        padding: 0 1;
        margin-top: 1;
    }
    .dim { color: $text-muted; }
    .debug { color: $text-muted; text-style: italic; }
    .title { text-style: bold; margin-top: 1; }
    .subtitle { text-style: bold; color: $accent; margin-top: 1; }
    #inputrow {
        height: auto;
        border-top: solid #555555;
        border-bottom: solid #555555;
        padding: 0 1;
    }
    #prompt { width: 3; color: $primary; text-style: bold; }
    #inputrow TextArea {
        width: 1fr;
        height: 1;
        border: none;
        padding: 0;
        background: transparent;
    }
    #inputrow TextArea:focus { background: transparent; }
    #inputrow TextArea .text-area--cursor-line { background: transparent; }
    #status { height: 2; margin: 0 2 1 2; }
    #status Static { height: 1; color: $text-muted; }
    """

    def __init__(self, loader, vision, session, storage, process_turn,
                 classify_input, tools, debug=False, storage_note=None):
        super().__init__()
        self.loader = loader
        self.vision = vision
        self.session = session
        self.storage = storage
        self.storage_note = storage_note
        self.process_turn = process_turn
        self.classify_input = classify_input
        self.tools = tools
        self.debug_mode = debug
        self._status_phase = "init"
        self._status_base = ""
        self._embed_timer = None
        self._flash_timer = None
        self._spin_timer = None
        self._spin_text = ""
        self._spin_frame = 0
        self._embed_start = 0.0
        self._embed_label = ""
        self._tokenizing = False
        self.attached_source = None  # girdi alanındaki belirtecin gerçek yolu
        self.attached_token = ""

    def compose(self) -> ComposeResult:
        with Horizontal(id="topbox"):
            yield Static("[bold cyan]▌ GÖRÜNTÜLÜ SOHBET[/]\n\n"
                         "[dim]CLIP ViT-B/32 · LVIS obje adları · tema dağarcığı[/]", id="title")
            yield Static("URL / dosya yolunu doğrudan yapıştırabilir\n"
                         "elle yazabilir ya da görseli bu pencereye sürükleyip\n"
                         "bırakabilirsin. Aynı anda tek görsel analiz edilir.\n"
                         "Objeyi tanır, web'den derlediğim bilgiyi sunarım.\n"
                         "Bir metin yazıp aynı konuda soru sorabilirsin.\n"
                         "Çıkış için: q + enter veya ctrl+c.", id="hints")
        yield VerticalScroll(id="log")
        with Horizontal(id="inputrow"):
            yield Static("▸", id="prompt")
            yield SourceInput(id="inbox")
        with Vertical(id="status"):
            yield Static("", id="status1")
            yield Static("", id="statusctx")

    def on_mount(self):
        if self.storage_note:
            self.add_line(self.storage_note, "dim")
        self.query_one("#inbox", SourceInput).focus()
        self.set_busy(True)  # tek bilgi kaynağı durum satırıdır
        if self.vision.is_ready_on_disk():
            self.spin("Model yükleniyor")
        else:
            self.spin("İlk çalıştırma, model hazırlanıyor")
        self.load_model()

    # belirteç, kaynak metnin içinde yaşar

    def attach_source(self, source: str):
        label = "URL" if source.startswith(("http://", "https://", "www.")) else "Görsel"
        self.attached_source = source
        self.attached_token = f"[{label}]"
        box = self.query_one("#inbox", SourceInput)
        box.insert(self.attached_token)
        box.focus()

    def _drop_attachment(self):
        self.attached_source = None
        self.attached_token = ""

    def remove_token(self):
        box = self.query_one("#inbox", SourceInput)
        index = box.text.find(self.attached_token)
        if index >= 0:
            self._tokenizing = True
            box.text = box.text[:index] + box.text[index + len(self.attached_token):]
            box.cursor_location = (0, index)
            self._tokenizing = False
        self._drop_attachment()
        self._resize_input()

    def on_text_area_selection_changed(self, event: TextArea.SelectionChanged):
        token = self.attached_token
        if not token:
            return
        box = event.text_area
        index = box.text.find(token)
        if index < 0:
            return
        start, end = index, index + len(token)
        column = box.cursor_location[1]
        if start < column < end:
            box.cursor_location = (0, start if column - start <= end - column else end)

    def on_text_area_changed(self, event: TextArea.Changed):
        self._resize_input()
        if self._tokenizing:
            return
        # belirteç metinden silindiyse ek de düşer
        if self.attached_source and self.attached_token not in event.text_area.text:
            self._drop_attachment()
            return
        if self.attached_source:
            return
        # elle yazılan kaynak, boşlukla tamamlanınca belirtece dönüşür
        value = event.text_area.text
        if not value.endswith(" "):
            return
        candidate = value.strip()
        if candidate and self.tools.is_single_source(candidate):
            self._tokenizing = True
            event.text_area.text = ""
            self._tokenizing = False
            self.attach_source(candidate)
            self._resize_input()

    def _resize_input(self):
        # içerik büyüdükçe alan yukarı doğru genişler, sınır aşılırsa içeride scroll olur
        box = self.query_one("#inbox", SourceInput)
        lines = max(1, box.wrapped_document.height)
        box.styles.height = min(lines, INPUT_MAX_LINES)

    # girdi altındaki durum alanı

    SPINNER = ("⏳", "⌛")

    def spin(self, text: str):
        # model hazır olana kadar birinci satırda dönen turuncu kum saati
        self._spin_text = text
        self._spin_tick()
        if self._spin_timer is None:
            self._spin_timer = self.set_interval(0.5, self._spin_tick)

    def _spin_tick(self):
        self._spin_frame = (self._spin_frame + 1) % len(self.SPINNER)
        self.status_line(0, f"[orange]{self.SPINNER[self._spin_frame]}[/] {self._spin_text}")

    def stop_spin(self):
        if self._spin_timer is not None:
            self._spin_timer.stop()
            self._spin_timer = None

    def status_line(self, slot: int, text: str):
        self.query_one(f"#status{slot + 1}", Static).update(text)

    def status_reset(self, line1: str = ""):
        self.status_line(0, line1)

    def status_flash(self, message: str):
        # 4 saniye uyarı görünür, ikon turuncu, vurgular metnin içinde işaretlidir
        if self._flash_timer is not None:
            self._flash_timer.stop()
        self.status_line(0, f"[orange]⚠[/] {message}")
        self._flash_timer = self.set_timer(4.0, self._end_flash)

    def _end_flash(self):
        self._flash_timer = None
        self.status_line(0, self._status_base)

    def _load_progress(self, stage, label, done=None, total=None):
        # çalışan iş parçacığından gelir, indirme ilerlemesi ve kodlama süresi gösterilir
        if stage == "encode":
            self.call_from_thread(self._start_embed_status, label)
            return
        if self._embed_timer is not None:
            self.call_from_thread(self._stop_embed_timer)
        text = label
        if total:
            text += f" · [orange]{done / 1e6:.0f} / {total / 1e6:.0f} MB[/]"
        self.call_from_thread(self.spin, text)

    def _stop_embed_timer(self):
        if self._embed_timer is not None:
            self._embed_timer.stop()
            self._embed_timer = None

    def _start_embed_status(self, label: str):
        self._status_phase = "embed"
        self._embed_label = label
        self._embed_start = time.monotonic()
        self.status_reset()
        self._tick_embed()
        self._embed_timer = self.set_interval(1.0, self._tick_embed)

    def _tick_embed(self):
        minutes, seconds = divmod(int(time.monotonic() - self._embed_start), 60)
        self.spin(f"{self._embed_label} · [orange]{minutes}:{seconds:02d}[/]")

    def _finish_status(self):
        self._stop_embed_timer()
        self._status_phase = "ready"
        self.stop_spin()
        themes = len(getattr(self.vision, "theme_keys", []) or [])
        self._status_base = (f"[green]●[/] Hazır · [orange]{self.vision.vocab_size}[/] obje · "
                             f"[orange]{themes}[/] tema")
        self.query_one("#title", Static).update(
            "[bold cyan]▌ GÖRÜNTÜLÜ SOHBET[/]\n\n"
            f"[dim]CLIP ViT-B/32 · {self.vision.vocab_size} LVIS obje adı · {themes} tema[/]")
        self.status_reset(self._status_base)

    # ekrana yazma yardımcıları

    def add_line(self, text: str, style_class: str = ""):
        line = Static(text)
        if style_class:
            line.add_class(style_class)
        log = self.query_one("#log", VerticalScroll)
        log.mount(line)
        log.scroll_end(animate=False)

    def echo_user(self, kind: str, value: str, raw: str, user_text: str = ""):
        # işlenen her kaynak, giriş yolundan bağımsız girdi belirteciyle aynı rozetle görünür
        tail = f"  [i]{escape(user_text)}[/i]" if user_text else ""
        if kind == "url":
            self.add_line(f"[bold cyan]›[/] [bold]\\[URL][/] · {linkify(value)}{tail}", "user")
        elif kind == "path":
            self.add_line(f"[bold cyan]›[/] [bold]\\[Görsel][/] · {escape(value)}{tail}", "user")
        else:
            self.add_line(f"[bold cyan]›[/] {escape(raw.strip())}", "user")

    def action_open_url(self, url: str):
        webbrowser.open(url)

    def open_card(self) -> TurnCard:
        card = TurnCard(debug=self.debug_mode)
        log = self.query_one("#log", VerticalScroll)
        log.mount(card)
        log.scroll_end(animate=False)
        return card

    def _set_context(self, turn_no, object_tr, previous, family_label, chain, repeat):
        # giriş altındaki kalıcı satır sohbetin özetini gösterir, kart o turu
        n = f"[orange]{turn_no}.[/] tur"
        if previous:
            names = ", ".join(f"[orange]{escape(name)}[/]" for name in chain)
            text = f"↻ {n} · {escape(family_label)} konusu sürüyor · {names}"
        elif repeat:
            text = f"↻ {n} · [orange]{escape(object_tr)}[/] yeniden · yeni kaynaklar"
        elif turn_no == 1:
            text = f"↻ Sohbet başladı · [orange]{escape(object_tr)}[/]"
        else:
            text = f"↻ {n} · konu [orange]{escape(object_tr)}[/] · yeni konu"
        self.query_one("#statusctx", Static).update(text)

    def set_busy(self, busy: bool):
        box = self.query_one("#inbox", SourceInput)
        box.disabled = busy
        if not busy:
            box.focus()

    # iş akışı

    @work(thread=True)
    def load_model(self):
        try:
            self.vision.load(progress=self._load_progress)
        except Exception as error:
            message = ("Modeli hazırlayamadım. İlk çalıştırma için internet bağlantısı "
                       "gerekiyor, bağlantını kontrol edip tekrar dener misin?")
            if self.debug_mode:
                message += f"\nAyrıntı: {error!r}"
            self.call_from_thread(self.exit, message)
            return
        self.call_from_thread(self._finish_status)
        self.call_from_thread(self.set_busy, False)

    def on_click(self, event: events.Click):
        # nereye tıklanırsa tıklansın input alanı aktif olur
        box = self.query_one("#inbox", SourceInput)
        if not box.disabled:
            box.focus()

    def handle_paste_text(self, raw: str):
        # tüm yapıştırma ve bırakma yolları bu tek denetimden geçer
        box = self.query_one("#inbox", SourceInput)
        if box.disabled:
            return
        text = raw.replace("\n", " ").strip()
        if not text:
            return
        sources = self.tools.find_sources(text)
        if sources and self.attached_source:
            self.status_flash("Aynı anda [orange]tek görsel[/] analiz edilir, önce eldekini gönder ya da kaldır")
            return
        if len(sources) >= 2:
            self.status_flash("Birden çok görsel bırakıldı, [orange]tek görsel[/] yeter")
            return
        if self.tools.is_single_source(text):
            self.attach_source(sources[0] if sources else text)
            return
        if self.tools.is_unsupported_file(text):
            self.status_flash("Bu dosya bir görsel değil, [orange]JPG[/] ya da [orange]PNG[/] bekleniyor")
            return
        box.insert(text)
        box.focus()

    def on_paste(self, event: events.Paste):
        # odak input dışındayken gelen yapıştırmalar da aynı denetime gider
        event.stop()
        self.handle_paste_text(event.text)

    def submit_current(self):
        box = self.query_one("#inbox", SourceInput)
        raw = box.text

        if self.attached_source and self.attached_token in raw:
            # görselle birlikte yazılan metin o turun sorusu olur
            user_text = raw.replace(self.attached_token, "").strip()
            source = self.attached_source
            self._drop_attachment()
            self._clear_input(box)
            kind, value = self.classify_input(source)
            self.echo_user(kind, value, source, user_text)
            self.set_busy(True)
            self.run_turn(kind, value, user_text)
            return

        source, user_text = self.tools.split_source_text(raw)
        kind, value = self.classify_input(source or raw)
        if not source:
            user_text = ""
        if kind == "empty":
            return
        if kind == "quit":
            self.exit("Görüşmek üzere!")
            return
        if kind == "multi":
            # girdi silinmez ki kullanıcı fazlalığı çıkarabilsin
            self.status_flash("Metinde iki kaynak var, [orange]tek görsel[/] ya da adres yeter")
            return
        self._clear_input(box)
        self.echo_user(kind, value, raw, user_text)
        self.set_busy(True)
        self.run_turn(kind, value, user_text)

    def _clear_input(self, box: SourceInput):
        self._tokenizing = True
        box.text = ""
        self._tokenizing = False
        self._resize_input()

    @work(thread=True)
    def run_turn(self, kind: str, value: str, user_text: str = ""):
        start = time.perf_counter()
        view = CardView(self, self.call_from_thread(self.open_card))
        try:
            self.process_turn(kind, value, self.loader, self.vision, self.session,
                              self.storage, view, user_text=user_text)
        except Exception as error:
            # tek turda oluşan sorun uygulamayı kapatmasın
            view.message("Beklenmeyen bir sorun oluştu. Tekrar dener misin?")
            view.detail("hata", repr(error))
        finally:
            view.finish(time.perf_counter() - start)
            self.call_from_thread(self.set_busy, False)
