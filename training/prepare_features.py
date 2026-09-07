# Numan Bekir Özçelik - 07.09.2026
"""Caltech-101 görsellerini CLIP görüntü kodlayıcısından geçirip öznitelik dosyası üretir.

Veri seti torchvision üzerinden indirilir. Sınıflar dengesiz olduğu için her
sınıftan en fazla belirli sayıda görsel alınır. Çıktı tek bir npz dosyasıdır,
her satır bir görselin 512 boyutlu birim vektörü ve sınıf indeksidir. Aynı
dosyaya sınıf adlarının metin vektörleri de yazılır, sıfır atış kıyası için.
"""

import sys
import time
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.vision import VisionModel, OBJECT_PROMPTS

DATA_DIR = Path(__file__).parent / "data"
OUTPUT = DATA_DIR / "caltech101_clip.npz"
PER_CLASS = 60  # sınıf başına en fazla görsel, dengeli ve hızlı
SKIP = {"Faces", "Faces_easy", "BACKGROUND_Google"}  # nesne olmayan sınıflar


def clean_name(name: str) -> str:
    return name.lower().replace("_", " ").rstrip("s") if name.endswith("s") and name not in ("bass",) else name.lower().replace("_", " ")


def main():
    import torch
    import torchvision

    dataset = torchvision.datasets.Caltech101(str(DATA_DIR), download=True)
    model = VisionModel()
    model.load()
    counts, rows, labels = {}, [], []
    classes = [c for c in dataset.categories if c not in SKIP]
    index = {c: i for i, c in enumerate(classes)}
    start = time.time()
    for image, target in dataset:
        name = dataset.categories[target]
        if name in SKIP or counts.get(name, 0) >= PER_CLASS:
            continue
        counts[name] = counts.get(name, 0) + 1
        image = image.convert("RGB")
        with torch.no_grad():
            tensor = model._preprocess(image).unsqueeze(0)
            vector = model._model.encode_image(tensor).float()[0]
        vector = vector / vector.norm()
        rows.append(vector.numpy())
        labels.append(index[name])
        if len(rows) % 500 == 0:
            print(f"{len(rows)} görsel, {time.time() - start:.0f} sn")
    prompts = [clean_name(c) for c in classes]
    text = model._encode_texts(prompts, OBJECT_PROMPTS).numpy()
    np.savez(OUTPUT, x=np.stack(rows), y=np.array(labels), classes=np.array(classes),
             prompts=np.array(prompts), text=text)
    print(f"{len(rows)} görsel, {len(classes)} sınıf, {time.time() - start:.0f} sn -> {OUTPUT}")


if __name__ == "__main__":
    main()
