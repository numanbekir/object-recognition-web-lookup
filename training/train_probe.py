# Numan Bekir Özçelik - 07.09.2026
"""CLIP özniteliklerinin üstünde tek katmanlı sınıflandırıcı eğitir.

Girdi 512 boyutlu birim vektör, çıktı sınıf sayısı kadar skor. Eğitim döngüsü
burada yazılmıştır. Çapraz entropi kaybı, Adam eniyileyici, ağırlık çürümesi,
sınıf dengeli eğitim ve doğrulama ayrımı, doğrulama kaybı artınca erken
durdurma. Aynı doğrulama kümesinde CLIP sıfır atış doğruluğu da ölçülür ki
eğitimin katkısı görülebilsin. Model ve sınıf listesi models klasörüne yazılır.
"""

import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import config

FEATURES = Path(__file__).parent / "data" / "caltech101_clip.npz"
MAPPING = Path(__file__).parent / "caltech_to_lvis.json"
OUTPUT = config.MODELS_DIR / "probe.pt"

SEED = 7
VAL_RATIO = 0.2
EPOCHS = 300
LEARNING_RATE = 1e-2
WEIGHT_DECAY = 1e-4
BATCH_SIZE = 128
PATIENCE = 10  # doğrulama kaybı bu kadar epoch iyileşmezse durulur


def stratified_split(labels: np.ndarray, ratio: float, seed: int):
    """Her sınıftan aynı oranda doğrulama örneği ayırır."""
    rng = np.random.default_rng(seed)
    train, val = [], []
    for label in np.unique(labels):
        idx = np.where(labels == label)[0]
        rng.shuffle(idx)
        cut = max(1, int(len(idx) * ratio))
        val += idx[:cut].tolist()
        train += idx[cut:].tolist()
    return np.array(train), np.array(val)


def accuracy(scores: np.ndarray, labels: np.ndarray) -> float:
    return float((scores.argmax(axis=1) == labels).mean())


def zero_shot_accuracy(x: np.ndarray, text: np.ndarray, labels: np.ndarray) -> float:
    return accuracy(x @ text.T, labels)


def train(x, y, num_classes, epochs=EPOCHS, lr=LEARNING_RATE, weight_decay=WEIGHT_DECAY,
          batch_size=BATCH_SIZE, patience=PATIENCE, seed=SEED, x_val=None, y_val=None, log=print):
    """Lineer sınıflandırıcıyı eğitir, en iyi doğrulama kaybındaki ağırlıkları döndürür."""
    import torch
    torch.manual_seed(seed)
    x_t, y_t = torch.tensor(x), torch.tensor(y)
    layer = torch.nn.Linear(x.shape[1], num_classes)
    optimizer = torch.optim.Adam(layer.parameters(), lr=lr, weight_decay=weight_decay)
    loss_fn = torch.nn.CrossEntropyLoss()
    best, best_state, stale = float("inf"), None, 0
    for epoch in range(1, epochs + 1):
        order = torch.randperm(len(x_t))
        layer.train()
        for start in range(0, len(order), batch_size):
            batch = order[start:start + batch_size]
            optimizer.zero_grad()
            loss = loss_fn(layer(x_t[batch]), y_t[batch])
            loss.backward()
            optimizer.step()
        if x_val is None:
            continue
        layer.eval()
        with torch.no_grad():
            val_loss = float(loss_fn(layer(torch.tensor(x_val)), torch.tensor(y_val)))
        if val_loss < best - 1e-4:
            best, stale = val_loss, 0
            best_state = {k: v.clone() for k, v in layer.state_dict().items()}
        else:
            stale += 1
        if epoch % 10 == 0:
            log(f"epoch {epoch:3d}  doğrulama kaybı {val_loss:.4f}")
        if stale >= patience:
            log(f"erken durdurma, epoch {epoch}")
            break
    if best_state:
        layer.load_state_dict(best_state)
    return layer


def main():
    import torch
    data = np.load(FEATURES, allow_pickle=True)
    x, y, text = data["x"].astype(np.float32), data["y"], data["text"]
    classes = [str(c) for c in data["classes"]]  # saf metin, güvenli yükleme için
    train_idx, val_idx = stratified_split(y, VAL_RATIO, SEED)
    print(f"{len(x)} görsel, {len(classes)} sınıf, eğitim {len(train_idx)}, doğrulama {len(val_idx)}")

    layer = train(x[train_idx], y[train_idx], len(classes), x_val=x[val_idx], y_val=y[val_idx])
    with torch.no_grad():
        val_scores = layer(torch.tensor(x[val_idx])).numpy()
        train_scores = layer(torch.tensor(x[train_idx])).numpy()
    print(f"eğitim doğruluğu     {accuracy(train_scores, y[train_idx]):.3f}")
    print(f"doğrulama doğruluğu  {accuracy(val_scores, y[val_idx]):.3f}")
    print(f"sıfır atış doğruluğu {zero_shot_accuracy(x[val_idx], text, y[val_idx]):.3f}  (aynı doğrulama kümesi)")

    mapping = json.loads(MAPPING.read_text(encoding="utf-8"))
    config.MODELS_DIR.mkdir(exist_ok=True)
    torch.save({"weight": layer.weight.detach(), "bias": layer.bias.detach(), "classes": classes,
                "lvis": [str(mapping.get(c, "")) for c in classes],
                "hyperparameters": {"epochs": EPOCHS, "lr": LEARNING_RATE, "weight_decay": WEIGHT_DECAY,
                                    "batch_size": BATCH_SIZE, "patience": PATIENCE, "val_ratio": VAL_RATIO}},
               OUTPUT)
    print(f"model yazıldı, {OUTPUT}")


if __name__ == "__main__":
    main()
