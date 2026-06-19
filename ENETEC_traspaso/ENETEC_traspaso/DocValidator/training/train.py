"""Entrena el clasificador de tipos de documento a partir de dataset/.

Estructura esperada (una carpeta por tipo, mas _basura para negativos):
    dataset/carnet_identidad/*.jpg
    dataset/certificacion_legal/*.jpg
    dataset/doc_empresa/*.jpg
    dataset/_basura/*.jpg

Uso:
    python -m training.train --epochs 15 --batch 16
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import timm
import torch
from torch import nn
from torch.utils.data import DataLoader
from torchvision import datasets, transforms

BASE_DIR = Path(__file__).resolve().parent.parent
DATASET = BASE_DIR / "dataset"
MODELS = BASE_DIR / "models"
IMG_SIZE = 384  # debe coincidir con app/classifier.py


def build_loader(batch: int, dataset_dir: Path = DATASET):
    # Augmentation fuerte para que el modelo generalice a documentos REALES
    # (fotos en angulo, en gris tras el realce, con brillo/desenfoque variable),
    # no solo al dataset sintetico. No se voltea horizontal (el texto se espejaria).
    train_tfm = transforms.Compose(
        [
            transforms.Resize((IMG_SIZE, IMG_SIZE)),
            transforms.RandomApply([transforms.RandomRotation(8)], p=0.5),
            transforms.RandomPerspective(distortion_scale=0.3, p=0.5),
            transforms.ColorJitter(0.3, 0.3, 0.3, 0.05),
            transforms.RandomGrayscale(p=0.3),
            transforms.RandomApply([transforms.GaussianBlur(3, sigma=(0.1, 1.5))], p=0.3),
            transforms.ToTensor(),
            transforms.Normalize([0.485, 0.456, 0.406], [0.229, 0.224, 0.225]),
        ]
    )
    ds = datasets.ImageFolder(dataset_dir, transform=train_tfm)
    loader = DataLoader(ds, batch_size=batch, shuffle=True, num_workers=0)
    return ds, loader


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--epochs", type=int, default=15)
    ap.add_argument("--batch", type=int, default=16)
    ap.add_argument("--lr", type=float, default=3e-4)
    ap.add_argument("--dataset", default=str(DATASET), help="carpeta del dataset")
    ap.add_argument("--out", default="classifier", help="nombre base del modelo (classifier / classifier_pyme)")
    args = ap.parse_args()

    device = "cuda" if torch.cuda.is_available() else "cpu"
    print(f"Entrenando en: {device}")

    ds, loader = build_loader(args.batch, Path(args.dataset))
    classes = ds.classes
    print(f"Clases detectadas: {classes}")

    model = timm.create_model(
        "tf_efficientnetv2_s", pretrained=True, num_classes=len(classes)
    ).to(device)
    opt = torch.optim.AdamW(model.parameters(), lr=args.lr)
    crit = nn.CrossEntropyLoss()

    model.train()
    for epoch in range(args.epochs):
        loss_sum, correct, total = 0.0, 0, 0
        for imgs, labels in loader:
            imgs, labels = imgs.to(device), labels.to(device)
            opt.zero_grad()
            out = model(imgs)
            loss = crit(out, labels)
            loss.backward()
            opt.step()
            loss_sum += loss.item()
            correct += (out.argmax(1) == labels).sum().item()
            total += labels.size(0)
        acc = 100 * correct / max(total, 1)
        print(f"Epoch {epoch + 1}/{args.epochs}  loss={loss_sum / len(loader):.4f}  acc={acc:.1f}%")

    MODELS.mkdir(exist_ok=True)
    model_path = MODELS / f"{args.out}.pt"
    classes_path = MODELS / (f"{args.out}.json" if args.out != "classifier" else "classes.json")
    torch.save(model.state_dict(), model_path)
    with open(classes_path, "w", encoding="utf-8") as fh:
        json.dump(classes, fh, ensure_ascii=False, indent=2)
    print(f"\nModelo guardado en: {model_path}")
    print(f"Clases guardadas en: {classes_path}")


if __name__ == "__main__":
    main()
