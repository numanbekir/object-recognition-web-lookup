# Numan Bekir Özçelik - 06.09.2026
"""Sayfanın html yapısından liste ve alt başlık çıkarır.

Tarif ya da çeşit listesi gibi içerikler düz paragraf değil yapıdır. Malzeme
listesi liste etiketlerinde, çeşitler alt başlıklar altında durur. Bu modül
belge ağacını okuyup madde listelerini, adım listelerini ve alt başlıkları
döndürür. Dil modeli yoktur. Ana içerik alanı seçilir, gezinme ve altbilgi
atılır, kısa ve tekrarsız maddeler tutulur.
"""

import re

import lxml.html

STRIP_TAGS = ("script", "style", "nav", "footer", "header", "aside", "form", "noscript")
NOISE_HEADINGS = ("yorum", "ilgili", "benzer", "paylaş", "etiket", "kategori", "son yazılar",
                  "popüler", "bunlar da", "hakkında", "iletişim", "abone", "sepet", "kampanya",
                  "yardım", "kurumsal", "hakkımızda", "müşteri", "sıkça sorulan", "menü")
MIN_ITEMS, MAX_ITEMS = 3, 12
MIN_HEADINGS, MAX_HEADINGS = 3, 6
SENTENCE_END = re.compile(r"(?<=[.!?])\s")


def _clean(text: str) -> str:
    return " ".join((text or "").split())


def _first_sentence(text: str, max_chars: int = 220) -> str:
    sentence = SENTENCE_END.split(_clean(text), maxsplit=1)[0]
    return sentence if len(sentence) <= max_chars else sentence[:max_chars].rsplit(" ", 1)[0] + "…"


def _root(html: str):
    try:
        document = lxml.html.fromstring(html)
    except Exception:
        return None
    for tag in STRIP_TAGS:
        for node in document.iter(tag):
            node.drop_tree()
    for expression in ("//article", "//main", "//*[@role='main']"):
        found = document.xpath(expression)
        if found:
            return found[0]
    body = document.find("body")
    return body if body is not None else document


def _label_before(node) -> str:
    """Listeden hemen önce gelen başlık ya da kısa satırı döndürür."""
    previous = node.getprevious()
    hops = 0
    while previous is not None and hops < 3:
        text = _clean(previous.text_content())
        if text and len(text) <= 60:
            return text.rstrip(":")
        if text:
            break
        previous = previous.getprevious()
        hops += 1
    parent = node.getparent()
    if parent is not None and parent.tag in ("section", "div"):
        heading = next((h for tag in ("h2", "h3", "h4")
                        for h in [parent.find(f".//{tag}")] if h is not None), None)
        if heading is not None:
            return _clean(heading.text_content()).rstrip(":")[:60]
    return ""


def extract_lists(html: str) -> list:
    """Etiket, maddeler ve sıralı alanlarından oluşan liste sözlükleri döndürür"""
    root = _root(html)
    if root is None:
        return []
    lists = []
    for node in root.iter("ul", "ol"):
        items, seen = [], set()
        for li in node.findall("li"):
            text = _clean(li.text_content())
            if 3 <= len(text) <= 160 and text.lower() not in seen and "http" not in text:
                seen.add(text.lower())
                items.append(text)
        if MIN_ITEMS <= len(items) <= MAX_ITEMS:
            label = _label_before(node)
            if any(noise in label.lower() for noise in NOISE_HEADINGS):
                continue
            lists.append({"etiket": label, "maddeler": items, "sirali": node.tag == "ol"})
    return lists


def extract_sections(html: str) -> list:
    """Alt başlıkları ve altındaki ilk cümleyi sözlük listesi olarak döndürür."""
    root = _root(html)
    if root is None:
        return []
    sections = []
    for heading in root.iter("h2", "h3"):
        title = _clean(heading.text_content()).rstrip(":")
        if not 3 <= len(title) <= 70 or any(noise in title.lower() for noise in NOISE_HEADINGS):
            continue
        body = ""
        sibling = heading.getnext()
        hops = 0
        while sibling is not None and hops < 4 and not body:
            if sibling.tag in ("h1", "h2", "h3"):
                break
            text = _clean(sibling.text_content())
            if len(text) >= 40:
                body = _first_sentence(text)
            sibling = sibling.getnext()
            hops += 1
        if body:
            sections.append({"baslik": title, "metin": body})
    return sections


def pick_list(lists: list, label_hints: tuple, max_items: int) -> dict:
    """Etiketi ipuçlarından birini içeren ilk listeyi, yoksa ilk listeyi döndürür."""
    for entry in lists:
        if any(hint in entry["etiket"].lower() for hint in label_hints):
            return {**entry, "maddeler": entry["maddeler"][:max_items]}
    return None


def pick_sections(sections: list, anchor_stems: list, limit: int) -> list:
    """Obje kökünü içeren başlıkları önceliklendirir, asgari başlık sayısını ister."""
    related = [s for s in sections if any(stem in s["baslik"].lower() for stem in anchor_stems)]
    chosen = related if len(related) >= MIN_HEADINGS else sections
    return chosen[:limit] if len(chosen) >= MIN_HEADINGS else []


STEP_HINTS = ("yapılış", "yapılışı", "hazırlan", "nasıl yapılır", "tarifi", "adım")


def extract_steps(html: str) -> list:
    """Yapılış başlığından sonra gelen ardışık paragrafları adım listesi olarak döndürür.
    Tarif sitelerinde adımlar çoğu zaman liste yerine art arda paragraf olarak durur.
    """
    root = _root(html)
    if root is None:
        return []
    for heading in root.iter("h2", "h3", "h4"):
        title = _clean(heading.text_content()).lower()
        if not any(hint in title for hint in STEP_HINTS) or "malzeme" in title:
            continue
        steps, sibling, hops = [], heading.getnext(), 0
        while sibling is not None and hops < 20:
            if sibling.tag in ("h1", "h2", "h3", "h4"):
                break
            if sibling.tag in ("ol", "ul"):
                steps += [_clean(li.text_content()) for li in sibling.findall("li")]
            else:
                text = _clean(sibling.text_content())
                if 20 <= len(text) <= 400:
                    steps.append(text)
            sibling = sibling.getnext()
            hops += 1
        steps = [s for s in steps if 20 <= len(s) <= 400]
        if 2 <= len(steps) <= MAX_ITEMS:
            return steps
    return []


COMMERCIAL_HEADINGS = ("fiyat", "en iyi", "hangi", "almalı", "tavsiye", "hashtag", "sosyal",
                       "indirim", "kampanya", "sipariş", "satın")


def score_sections(sections: list, anchor_stems: list) -> float:
    """Alt başlık listesinin bir çeşit listesi olma olasılığını puanlar
    Obje kökünü taşıyan kısa başlıklar artı, satış ve rehber kalıpları eksi puan alır.
    """
    if len(sections) < MIN_HEADINGS:
        return 0.0
    total = 0.0
    for section in sections:
        title = section["baslik"].lower()
        total += 1.0 if any(stem in title for stem in anchor_stems) else 0.3
        total -= 1.0 if any(word in title for word in COMMERCIAL_HEADINGS) else 0.0
        total -= 0.3 if len(title) > 45 else 0.0
    return total / len(sections)


def best_sections(candidates: list, anchor_stems: list, limit: int, min_score: float = 0.6):
    """Kaynak, adres ve bölüm üçlüleri arasından en iyi çeşit listesini seçer."""
    best, best_score = None, min_score
    for source, url, sections in candidates:
        # yalnız objeyi anan, satış dili taşımayan alt başlıklar çeşit sayılır
        clean = [s for s in sections
                 if any(stem in s["baslik"].lower() for stem in anchor_stems)
                 and not any(word in s["baslik"].lower() for word in COMMERCIAL_HEADINGS)]
        score = score_sections(clean, anchor_stems)
        if score > best_score:
            best, best_score = (source, url, clean[:limit]), score
    return best
