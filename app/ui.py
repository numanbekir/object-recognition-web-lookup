# Numan Bekir Özçelik - 04.09.2026
"""Konsol çıktıları
--debug açıkken pipeline kararları da ekrana yazılır"""

try:
    import readline  # noqa: F401  input() içinde ok tuşları ve geçmiş çalışsın
except ImportError:
    pass


class ConsoleUI:
    def __init__(self, debug: bool = False):
        self.debug = debug

    def welcome(self, vocab_size: int = 0):
        line = "─" * 46
        print(line)
        print("  GÖRÜNTÜLÜ SOHBET")
        print("  Görselindeki objeyi tanır, web'den bilgi derlerim.")
        if vocab_size:
            print(f"  Model hazır ({vocab_size} kavram).")
        print(line)
        print("Bana bir görsel adresi (URL / dosya yolu) ya da mesaj yazabilirsin.")
        print("Görseli bu pencereye sürükleyip bırakman da yeterli. Çıkış için: q")

    def prompt(self) -> str:
        return input("\n> ")

    def info(self, message: str):
        print(message)

    def show_result(self, object_tr: str, confidence: float, keywords: list,
                    final_text: str, sources: list):
        raise NotImplementedError

    def debug_line(self, stage: str, message: str):
        if self.debug:
            print(f"[{stage}] {message}")
