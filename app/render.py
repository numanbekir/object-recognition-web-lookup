# Numan Bekir Özçelik - 07.09.2026
"""Bilgi bloklarını markdown metnine çevirir.

Aynı metin terminal arayüzünde kart gövdesi olarak çizilir, düz modda
renkli basılır ve kayıt dosyasına yazılır. Kaynaklar numaralı dipnottur.
"""


def collect_sources(blocks: list) -> list:
    sources = []
    for block in blocks:
        for passage in block["paragraflar"]:
            if passage["kaynak"] not in sources:
                sources.append(passage["kaynak"])
        shape = block.get("yapi")
        if shape and shape["kaynak"] not in sources:
            sources.append(shape["kaynak"])
        if shape and shape.get("adim_kaynak") and shape["adim_kaynak"] not in sources:
            sources.append(shape["adim_kaynak"])
    return sources


def source_urls(blocks: list) -> dict:
    """Her kaynak alanı için ilk görülen sayfa adresi."""
    urls = {}
    for block in blocks:
        for passage in block["paragraflar"]:
            urls.setdefault(passage["kaynak"], passage["url"])
        shape = block.get("yapi")
        if shape:
            urls.setdefault(shape["kaynak"], shape["url"])
            if shape.get("adim_kaynak"):
                urls.setdefault(shape["adim_kaynak"], shape.get("adim_url", ""))
    return urls


def footnote(number: int, url: str = "") -> str:
    """Dipnot işareti. Adres verilirse markdown bağlantısı olur, ekranda tıklanabilir."""
    return f"[\\[{number}\\]]({url})" if url else f"[{number}]"


def definition_markdown(passage: dict, linked: bool = False) -> str:
    return f"### ▸ Tanım\n\n{passage['metin']} {footnote(1, passage['url'] if linked else '')}\n"


def block_markdown(block: dict, sources: list, urls: dict = None) -> str:
    urls = urls or {}
    lines = [f"### ▸ {block['baslik']}", ""]
    for passage in block["paragraflar"]:
        number = sources.index(passage["kaynak"]) + 1
        lines += [f"{passage['metin']} {footnote(number, urls.get(passage['kaynak'], ''))}", ""]
    shape = block.get("yapi")
    if shape:
        ref = footnote(sources.index(shape["kaynak"]) + 1, urls.get(shape["kaynak"], ""))
        if shape["tip"] == "tarif":
            if shape["malzemeler"]:
                lines += ["**Malzemeler**", ""] + [f"- {item}" for item in shape["malzemeler"]] + [""]
            if shape["adimlar"]:
                lines += ["**Yapılışı**", ""]
                lines += [f"{number}. {step}" for number, step in enumerate(shape["adimlar"], 1)]
                lines += [""]
                if shape.get("adim_kaynak"):
                    ref += " adımlar " + footnote(sources.index(shape["adim_kaynak"]) + 1,
                                                 urls.get(shape["adim_kaynak"], ""))
        elif shape["tip"] == "basliklar":
            lines += [f"- **{item['baslik']}** {item['metin']}" for item in shape["ogeler"]] + [""]
        elif shape["tip"] == "madde":
            if shape.get("etiket"):
                lines += [f"**{shape['etiket']}**", ""]
            lines += [f"- {item}" for item in shape["maddeler"]] + [""]
        lines += [ref, ""]
    return "\n".join(lines)


BLOCK_GAP = "\n\u00a0\n\n"  # görünmez paragraf, ekranda bloklar arasına bir satır boşluk açar


def blocks_markdown(blocks: list, for_screen: bool = False) -> tuple:
    """Tüm blokların markdown metnini ve kaynak listesini döndürür.

    Ekran biçimi bloklar arasına görünmez bir satır koyar ve dipnotları
    bağlantı yapar. Kayıt dosyası için sade biçim kullanılır.
    """
    sources = collect_sources(blocks)
    urls = source_urls(blocks) if for_screen else {}
    parts = [block_markdown(block, sources, urls) for block in blocks]
    text = (BLOCK_GAP if for_screen else "\n").join(parts)
    return text.strip() + "\n", sources


def sources_line(sources: list) -> str:
    return "  ".join(f"[{i}] {source}" for i, source in enumerate(sources, 1))
