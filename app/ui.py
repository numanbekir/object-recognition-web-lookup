# Numan Bekir Özçelik - 04.09.2026
"""Proje kedni terminal arayüzü oluşturuldu,
responsive tasarım """

import re
import time

from rich.markup import escape
from textual import events, work
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.widgets import Static, TextArea

URL_PATTERN = re.compile(r"https?://\S+")
INPUT_MAX_LINES = 3  # input alanı en fazla bu değer kadar satır oluşturur


def linkify(text: str) -> str:
    # url'ler terminal köprüsüne dönüşür (ctrl+tık ile açılır)
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
        # yapıştırma alana varmadan tek merkezden (belirteç/ret denetimi) geçer
        event.stop()
        event.prevent_default()
        self.app.handle_paste_text(event.text)


class ChatApp(App):
    TITLE = "Görüntülü Sohbet"
    BINDINGS = [Binding("ctrl+c", "quit", show=False)]

    CSS = """
    Screen { layout: vertical; }
    #topbox {
        height: auto;
        border: round $primary;
        margin: 1 1 0 1;
        padding: 0 2;
    }
    #title { width: 1fr; }
    #hints { width: auto; color: $text-muted; text-align: right; }
    #log { padding: 1 2; }
    #log Static { margin-bottom: 0; }
    .user {
        border-left: thick $primary;
        background: $primary 12%;
        padding: 0 1;
        margin-top: 1;
    }
    .dim { color: $text-muted; }
    .debug { color: $text-muted; text-style: italic; }
    #inputrow {
        height: auto;
        border-top: solid #555555;
        border-bottom: solid #555555;
        padding: 0 1;
    }
    #inputrow TextArea {
        width: 1fr;
        height: 1;
        border: none;
        padding: 0;
        background: transparent;
    }
    #status { height: 2; margin: 0 2 1 2; }
    #status Static { height: 1; color: $text-muted; }
    #status Static.warn { color: $warning; }
    """

    def __init__(self, loader, detector, keywords, process_turn, classify_input, tools,
                 debug=False):
        super().__init__()
        self.loader = loader
        self.detector = detector
        self.keywords = keywords
        self.process_turn = process_turn
        self.classify_input = classify_input
        self.tools = tools
        self.debug_mode = debug
        self._status_phase = "init"
        self._status_base = ""
        self._embed_timer = None
        self._flash_timer = None
        self._embed_start = 0.0
        self._embed_label = ""
        self._tokenizing = False
        self.attached_source = None  # girdi alanındaki belirtecin gerçek yolu
        self.attached_token = ""

    def compose(self) -> ComposeResult:
        with Horizontal(id="topbox"):
            yield Static("[bold cyan]GÖRÜNTÜLÜ SOHBET[/]\n"
                         "Görselindeki objeyi tanır, web'den bilgi derlerim.", id="title")
            yield Static("Görseli bu pencereye sürükleyip bırakman yeterli.\n"
                         "Çıkış için q yazabilirsin.", id="hints")
        yield VerticalScroll(id="log")
        with Horizontal(id="inputrow"):
            yield SourceInput(id="inbox")
        with Vertical(id="status"):
            yield Static("", id="status1")
            yield Static("", id="status2")

    def on_mount(self):
        self.query_one("#inbox", SourceInput).focus()
        self.set_busy(True)  # tek bilgi kaynağı durum satırıdır
        if self.detector.is_ready_on_disk():
            self.status_line(0, "Model yükleniyor...")
        else:
            self.status_line(0, "Model dosyaları denetleniyor...")
        self.load_model()

    # --- belirteç: kaynak, metnin içinde [Görsel] olarak yaşar ---

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

    # --- durum alanı: input altında 2 satır ---

    def status_line(self, slot: int, text: str):
        self.query_one(f"#status{slot + 1}", Static).update(text)

    def status_reset(self, line1: str = "", line2: str = ""):
        self.status_line(0, line1)
        self.status_line(1, line2)

    def status_flash(self, message: str):
        # 4 saniye uyarı metni görünür
        if self._flash_timer is not None:
            self._flash_timer.stop()
        self.query_one("#status1", Static).add_class("warn")
        self.status_line(0, message)
        self._flash_timer = self.set_timer(4.0, self._end_flash)

    def _end_flash(self):
        self._flash_timer = None
        self.query_one("#status1", Static).remove_class("warn")
        self.status_line(0, self._status_base)

    def _load_progress(self, key, index, total, label, done, size):
        # worker thread'inden gelir; adım sırası plandan geldiği için satırlar sabittir
        if key == "embed":
            self.call_from_thread(self._start_embed_status, f"[{index}/{total}] {label}")
            return
        text = f"[{index}/{total}] {label}"
        if size:
            text += f" · {done / 1e6:.1f}/{size / 1e6:.1f} MB  %{done * 100 // size}"
        elif done:
            text += f" · {done / 1e6:.1f} MB"
        self.call_from_thread(self._set_download_status, index - 1, text)

    def _set_download_status(self, slot: int, text: str):
        if self._status_phase != "download":
            self._status_phase = "download"
            self.status_reset()  # "denetleniyor" satırı görev satırlarına yerini bırakır
        self.status_line(slot, text)

    def _start_embed_status(self, label: str):
        self._status_phase = "embed"
        self._embed_label = label
        self._embed_start = time.monotonic()
        self.status_reset()
        self._tick_embed()
        self._embed_timer = self.set_interval(1.0, self._tick_embed)

    def _tick_embed(self):
        minutes, seconds = divmod(int(time.monotonic() - self._embed_start), 60)
        self.status_line(0, f"{self._embed_label} · geçen süre {minutes}:{seconds:02d}")

    def _finish_status(self):
        if self._embed_timer is not None:
            self._embed_timer.stop()
            self._embed_timer = None
        self._status_phase = "ready"
        self._status_base = f"Model hazır ({self.detector.vocab_size} kavram)."
        self.status_reset(self._status_base)

    # --- ekrana yazma yardımcıları ---

    def add_line(self, text: str, style_class: str = ""):
        line = Static(text)
        if style_class:
            line.add_class(style_class)
        log = self.query_one("#log", VerticalScroll)
        log.mount(line)
        log.scroll_end(animate=False)

    def echo_user(self, kind: str, value: str, raw: str):
        # işlenen her kaynak, giriş yolundan bağımsız girdi belirteciyle aynı rozetle görünür
        if kind == "url":
            self.add_line(f"[bold cyan]›[/] [bold]\\[URL][/] · {linkify(value)}", "user")
        elif kind == "path":
            self.add_line(f"[bold cyan]›[/] [bold]\\[Görsel][/] · {escape(value)}", "user")
        else:
            self.add_line(f"[bold cyan]›[/] {escape(raw.strip())}", "user")

    def emit(self, message: str):
        self.call_from_thread(self.add_line, linkify(message))

    def emit_debug(self, stage: str, message: str):
        if self.debug_mode:
            self.call_from_thread(self.add_line, escape(f"{stage} · {message}"), "debug")

    def set_busy(self, busy: bool, note: str = ""):
        box = self.query_one("#inbox", SourceInput)
        box.disabled = busy
        self.status_line(1, note if busy else "")
        if not busy:
            box.focus()

    # --- iş akışı ---

    @work(thread=True)
    def load_model(self):
        try:
            self.detector.load(progress=self._load_progress)
            self.keywords.load()
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
        # tüm yapıştırma/bırakma yolları bu tek denetimden geçer
        box = self.query_one("#inbox", SourceInput)
        if box.disabled:
            return
        text = raw.replace("\n", " ").strip()
        if not text:
            return
        sources = self.tools.find_sources(text)
        if sources and self.attached_source:
            self.status_flash("Aynı anda tek görsel işleyebiliyorum. "
                              "Önce eldekini gönderir ya da kaldırır mısın?")
            return
        if len(sources) >= 2:
            self.status_flash("Aynı anda tek görsel işleyebiliyorum. Tek bir görsel bırakır mısın?")
            return
        if self.tools.is_single_source(text):
            self.attach_source(sources[0] if sources else text)
            return
        if self.tools.is_unsupported_file(text):
            self.status_flash("Bu dosya türünü desteklemiyorum. JPG ya da PNG gibi bir görsel bırakır mısın?")
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
            remaining = raw.replace(self.attached_token, "").strip()
            if remaining:
                # görsel+mesaj birleşimi arama katmanıyla gelecek; sessiz kayıp olmasın
                self.status_flash("Görselle mesajı birlikte işleme özelliği yakında; "
                                  "şimdilik görseli tek başına gönderir misin?")
                return
            source = self.attached_source
            self._drop_attachment()
            self._clear_input(box)
            kind, value = self.classify_input(source)
            self.echo_user(kind, value, source)
            self.set_busy(True, "işleniyor...")
            self.run_turn(kind, value)
            return

        kind, value = self.classify_input(raw)
        if kind == "empty":
            return
        if kind == "quit":
            self.exit("Görüşmek üzere!")
            return
        if kind == "multi":
            # girdi silinmez ki kullanıcı fazlalığı çıkarabilsin
            self.status_flash("Aynı anda tek görsel işleyebiliyorum. Tek bir görsel ya da URL verir misin?")
            return
        self._clear_input(box)
        self.echo_user(kind, value, raw)
        self.set_busy(True, "işleniyor...")
        self.run_turn(kind, value)

    def _clear_input(self, box: SourceInput):
        self._tokenizing = True
        box.text = ""
        self._tokenizing = False
        self._resize_input()

    @work(thread=True)
    def run_turn(self, kind: str, value: str):
        start = time.perf_counter()
        try:
            self.process_turn(kind, value, self.loader, self.detector, self.keywords,
                              self.emit, self.emit_debug)
        except Exception as error:
            # tek turda oluşan sorun uygulamayı kapatmasın
            self.emit("Beklenmeyen bir sorun oluştu. Tekrar dener misin?")
            self.emit_debug("hata", repr(error))
        finally:
            if kind in ("url", "path"):
                elapsed = time.perf_counter() - start
                self.call_from_thread(self.add_line, f"⏱ {elapsed:.1f} sn", "dim")
            self.call_from_thread(self.set_busy, False)
