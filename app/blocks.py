# Numan Bekir Özçelik - 06.09.2026
"""Objenin ailesine göre gösterilecek bilgi bloklarını planlar.

Her tur bir tanım bloğuyla başlar. Arama niyeti obje adından farklıysa
ilgili bloğu eklenir. Sonra objenin ailesine özgü bloklar gelir. Aile,
anahtar kelimelerin aile rolündeki kelimelerinden bulunur. Şema veri
klasöründeki json dosyasında durur ve koda dokunmadan genişletilebilir.
"""

import json

from . import config


class InfoBlock:
    def __init__(self, title: str, query: str, hints: list, required_hints: bool = False,
                 limit: int = 1, fmt: str = "paragraf", section_hints: list = ()):
        self.title = title
        self.query = query  # arama motoruna giden sorgu
        self.hints = hints  # paragraf sıralamasına giren açı kelimeleri
        self.required_hints = required_hints  # paragraf ipuçlarından birini içermeli
        self.limit = limit  # blokta gösterilecek en fazla paragraf
        self.fmt = fmt  # paragraf, tarif, basliklar ya da madde
        self.section_hints = list(section_hints)  # Vikipedi bölüm başlığı ipuçları


class BlockPlanner:
    def __init__(self):
        self.schema = json.loads(config.INFO_BLOCKS_PATH.read_text(encoding="utf-8"))
        self.roles = json.loads(config.WORD_ROLES_PATH.read_text(encoding="utf-8"))
        self.family_of_word = {word: name for name, spec in self.schema.items()
                               for word in spec["aileler"]}
        self.default_family = next(name for name, spec in self.schema.items()
                                   if spec.get("varsayilan"))

    def family(self, keywords: list) -> str:
        """Anahtar kelimelerin aile ve alan rolündekilerine bakar, ilk eşleşen şema kazanır."""
        for word in keywords:
            if self.roles.get(word) in ("aile", "alan") and word in self.family_of_word:
                return self.family_of_word[word]
        return self.default_family

    def plan(self, object_tr: str, keywords: list, intent_query: str,
             confident: bool = True) -> list:
        blocks = [InfoBlock("Tanım", f"{object_tr} nedir", ["nedir", "tanım", "adı verilen"])]
        if not confident:
            return blocks  # objeden emin değilken çeşitlerini listelemek anlamsız
        if intent_query and intent_query.lower() != object_tr.lower():
            blocks.append(InfoBlock("İlgili", intent_query, intent_query.split(), limit=2))
        for spec in self.schema[self.family(keywords)]["bloklar"]:
            blocks.append(InfoBlock(spec["baslik"], f"{object_tr} {spec['sorgu']}",
                                    spec["ipucu"], required_hints=True,
                                    fmt=spec.get("bicim", "paragraf"),
                                    section_hints=spec.get("bolum", ())))
        return blocks
