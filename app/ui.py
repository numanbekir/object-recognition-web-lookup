# Numan Bekir Özçelik - 04.09.2026
"""Konsol çıktıları
--debug açıkken pipeline kararları da ekrana yazılır"""


class ConsoleUI:
    def __init__(self, debug: bool = False):
        self.debug = debug

    def welcome(self, vocab_size: int):
        raise NotImplementedError

    def show_result(self, object_tr: str, confidence: float, keywords: list,
                    final_text: str, sources: list):
        raise NotImplementedError

    def info(self, message: str):
        raise NotImplementedError

    def debug_line(self, stage: str, message: str):
        raise NotImplementedError
