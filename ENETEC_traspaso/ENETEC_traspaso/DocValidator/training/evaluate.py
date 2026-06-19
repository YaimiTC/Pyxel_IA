"""Evaluacion rapida del clasificador entrenado sobre dataset/. Imprime accuracy
global y una matriz de confusion sencilla (real -> predicho).

Uso:
    python -m training.evaluate
"""
from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path

import timm
import torch
from torch.utils.data import DataLoader
from torchvision import datasets, transforms

BASE_DIR = Path(__file__).resolve().parent.parent
DATASET = BASE_DIR / "dataset"
MODELS = BASE_DIR / "models"
IMG_SIZE = 384


def main() -> None:
    device = "cuda" if torch.cuda.is_available() else "cpu"
    classes = json.loads((MODELS / "classes.json").read_text(encoding="utf-8"))

    tfm = transforms.Compose(
        [
            transforms.Resize((IMG_SIZE, IMG_SIZE)),
            transforms.ToTensor(),
            transforms.Normalize([0.485, 0.456, 0.406], [0.229, 0.224, 0.225]),
        ]
    )
    ds = datasets.ImageFolder(DATASET, transform=tfm)
    loader = DataLoader(ds, batch_size=16)

    model = timm.create_model("tf_efficientnetv2_s", pretrained=False, num_classes=len(classes))
    model.load_state_dict(torch.load(MODELS / "classifier.pt", map_location=device))
    model.eval().to(device)

    confusion: dict = defaultdict(lambda: defaultdict(int))
    correct = total = 0
    with torch.no_grad():
        for imgs, labels in loader:
            preds = model(imgs.to(device)).argmax(1).cpu()
            for t, p in zip(labels, preds):
                confusion[ds.classes[int(t)]][classes[int(p)]] += 1
                correct += int(int(t) == int(p))
                total += 1

    print(f"Accuracy global: {100 * correct / max(total, 1):.1f}%\n")
    print("Matriz de confusion (real -> predicho):")
    for real in confusion:
        print(f"  {real}: {dict(confusion[real])}")


if __name__ == "__main__":
    main()
