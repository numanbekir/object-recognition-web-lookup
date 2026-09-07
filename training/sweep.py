# Numan Bekir Özçelik - 07.09.2026
"""Hiperparametre taraması. Öğrenme oranı ve ağırlık çürümesi için birkaç değeri
aynı eğitim ve doğrulama kümesinde dener. Doğruluğun yanında güven kalibrasyonu
da ölçülür, çünkü uygulama sınıflandırıcının görüşünü güvenine göre kullanır.
Yanlış tahminlerde yüksek güven tehlikelidir. Eğitim kodu değişmez, seçilen
değerler train_probe içindeki sabitlere elle yazılır."""

import sys
import time
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from training.train_probe import FEATURES, SEED, VAL_RATIO, accuracy, stratified_split, train  # noqa: E402

LEARNING_RATES = (0.001, 0.005, 0.01, 0.02)
WEIGHT_DECAYS = (0.0, 0.0001, 0.001)


def main():
    import torch
    data = np.load(FEATURES, allow_pickle=True)
    x, y = data["x"].astype(np.float32), data["y"]
    classes = len(data["classes"])
    train_idx, val_idx = stratified_split(y, VAL_RATIO, SEED)
    print(f"{'öğrenme oranı':>14} {'çürüme':>8} {'epoch':>6} {'doğrulama':>10} "
          f"{'yanlışta güven':>15} {'yanlış ve >0.8':>15} {'süre':>6}")
    for lr in LEARNING_RATES:
        for wd in WEIGHT_DECAYS:
            start = time.time()
            epochs_run = []
            layer = train(x[train_idx], y[train_idx], classes, lr=lr, weight_decay=wd,
                          x_val=x[val_idx], y_val=y[val_idx],
                          log=lambda m: epochs_run.append(m) if "erken" in m else None)
            with torch.no_grad():
                probs = layer(torch.tensor(x[val_idx])).softmax(dim=-1).numpy()
            score = accuracy(probs, y[val_idx])
            wrong = probs.argmax(axis=1) != y[val_idx]
            wrong_conf = probs.max(axis=1)[wrong]
            stopped = epochs_run[0].split()[-1] if epochs_run else "300"
            print(f"{lr:>14} {wd:>8} {stopped:>6} {score:>10.3f} {wrong_conf.mean():>15.2f} "
                  f"{(wrong_conf > 0.8).mean():>15.2f} {time.time() - start:>5.0f}s")


if __name__ == "__main__":
    main()
