# Numan Bekir Özçelik - 04.09.2026
"""Önceki turların obje ve kelimelerini tutar, sonraki aramalara bağlam verir"""


class SessionContext:
    def __init__(self, window: int):
        self.window = window
        self.turns = []

    def add_turn(self, object_tr: str, keywords: list):
        raise NotImplementedError

    def context_terms(self) -> list:
        raise NotImplementedError

    def last_object(self):
        raise NotImplementedError
