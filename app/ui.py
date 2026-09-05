# Numan Bekir Özçelik - 04.09.2026
"""Proje kedni terminal arayüzü oluşturuldu, 
responsive tasarım """

import time

from rich.markup import escape
from textual import events, work
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.widgets import Input, Static


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
    #inbox { border: round $primary; margin: 0 1 0 1; }
    #status { height: 2; margin: 0 2 1 2; }
    #status Static { height: 1; color: $text-muted; }
    """

    def __init__(self, loader, detector, process_turn, classify_input, debug=False):
        super().__init__()
        self.loader = loader
        self.detector = detector
        self.process_turn = process_turn
        self.classify_input = classify_input
        self.debug_mode = debug
        self._status_phase = "init"
        self._embed_timer = None
        self._embed_start = 0.0
        self._embed_label = ""

    def compose(self) -> ComposeResult:
        with Horizontal(id="topbox"):
            yield Static("[bold cyan]GÖRÜNTÜLÜ SOHBET[/]\n"
                         "Görselindeki objeyi tanır, web'den bilgi derlerim.", id="title")
            yield Static("Görseli bu pencereye sürükleyip bırakman yeterli.\n"
                         "Çıkış için q yazabilirsin.", id="hints")
        yield VerticalScroll(id="log")
        yield Input(placeholder="Görsel adresi (URL / dosya yolu) ya da mesaj...", id="inbox")
        with Vertical(id="status"):
            yield Static("", id="status1")
            yield Static("", id="status2")

    def on_mount(self):
        self.query_one("#inbox", Input).focus()
        self.set_busy(True, "model hazırlanıyor...")
        if self.detector.is_ready_on_disk():
            self.status_line(0, "Model yükleniyor...")
        else:
            self.status_line(0, "Model dosyaları denetleniyor...")
        self.load_model()

    # --- durum alanı: input altında 2 satır ---

    def status_line(self, slot: int, text: str):
        self.query_one(f"#status{slot + 1}", Static).update(text)

    def status_reset(self, line1: str = "", line2: str = ""):
        self.status_line(0, line1)
        self.status_line(1, line2)

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
        self.status_reset(f"Model hazır ({self.detector.vocab_size} kavram).")

    # --- ekrana yazma yardımcıları ---

    def add_line(self, text: str, style_class: str = ""):
        line = Static(text)
        if style_class:
            line.add_class(style_class)
        log = self.query_one("#log", VerticalScroll)
        log.mount(line)
        log.scroll_end(animate=False)

    def emit(self, message: str):
        self.call_from_thread(self.add_line, escape(message))

    def emit_debug(self, stage: str, message: str):
        if self.debug_mode:
            self.call_from_thread(self.add_line, escape(f"{stage} · {message}"), "debug")

    def set_busy(self, busy: bool, note: str = ""):
        box = self.query_one("#inbox", Input)
        box.disabled = busy
        box.placeholder = note if busy else "Görsel adresi (URL / dosya yolu) ya da mesaj..."
        if not busy:
            box.focus()

    # --- iş akışı ---

    @work(thread=True)
    def load_model(self):
        try:
            self.detector.load(progress=self._load_progress)
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
        # nereye tıklanırsa tıklansın odak giriş kutusuna gelir
        box = self.query_one("#inbox", Input)
        if not box.disabled:
            box.focus()

    def on_paste(self, event: events.Paste):
        # odak nerede olursa olsun, bırakılan/yapıştırılan metin giriş kutusuna gitsin
        box = self.query_one("#inbox", Input)
        if box.disabled:
            return
        box.insert_text_at_cursor(event.text.replace("\n", " ").strip())
        box.focus()
        event.stop()

    def on_input_submitted(self, event: Input.Submitted):
        raw = event.value
        event.input.value = ""
        kind, value = self.classify_input(raw)
        if kind == "empty":
            return
        if kind == "quit":
            self.exit("Görüşmek üzere!")
            return
        self.add_line(f"[bold cyan]›[/] {escape(raw.strip())}", "user")
        self.set_busy(True, "işleniyor...")
        self.run_turn(kind, value)

    @work(thread=True)
    def run_turn(self, kind: str, value: str):
        start = time.perf_counter()
        try:
            self.process_turn(kind, value, self.loader, self.detector,
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
