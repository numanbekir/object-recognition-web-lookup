# Numan Bekir Özçelik - 06.09.2026
"""Cümle etiketleme aracı.

    1 = bilgi (metne girebilir)
    0 = dolgu (pazarlama/kişisel/kopuk; metne girmemeli)
    s = atla (kararsız kalınan cümle etiketlenmez)
    q = kaydet ve çık

Etiketler anında yazılır, araç kapatılıp açıldığında kaldığı yerden
devam eder. Ölçütler label.md dosyasındadır.
"""

import json
import random
from pathlib import Path

DATA_DIR = Path(__file__).parent / "data"
RAW = DATA_DIR / "raw_sentences.jsonl"
LABELS = DATA_DIR / "labels.jsonl"


def load_jsonl(path):
    if not path.exists():
        return []
    with open(path, encoding="utf-8") as file:
        return [json.loads(line) for line in file if line.strip()]


def main():
    rows = load_jsonl(RAW)
    if not rows:
        print(f"{RAW} yok ya da boş, önce collect_sentences.py çalıştırılmalı.")
        return
    labeled = {row["cumle"] for row in load_jsonl(LABELS)}
    # sabit tohumla nesneler karışık gelir ama sıra oturumlar arası değişmez
    random.Random(42).shuffle(rows)
    pending = [row for row in rows if row["cumle"] not in labeled]
    done = len(labeled)
    print(f"{len(rows)} cümle, {done} etiketli, {len(pending)} bekliyor.")
    print("1=bilgi  0=dolgu  s=atla  q=kaydet ve çık\n")

    with open(LABELS, "a", encoding="utf-8") as out:
        for row in pending:
            print(f"[{done + 1}] ({row['obje']} · {row['domain']})")
            print(f"  {row['cumle']}")
            while True:
                try:
                    answer = input("> ").strip().lower()
                except (KeyboardInterrupt, EOFError):
                    answer = "q"
                if answer in ("1", "0", "s", "q"):
                    break
                print("1, 0, s ya da q bekleniyor.")
            if answer == "q":
                break
            if answer == "s":
                continue
            out.write(json.dumps({**row, "etiket": int(answer)},
                                 ensure_ascii=False) + "\n")
            out.flush()
            done += 1
    print(f"\nToplam {done} etiket. Devam etmek için aracı tekrar çalıştır.")


if __name__ == "__main__":
    main()
