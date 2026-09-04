# Numan Bekir Özçelik - 04.09.2026
"""Tur kayıtlarını records.json'a yazar"""


class Storage:
    def __init__(self, path):
        self.path = path

    def append(self, record: dict) -> bool:
        # yarım yazım dosyayı bozmasın diye önce geçici dosyaya yazılır
        # yazılamazsa False döner, akış devam eder
        raise NotImplementedError
