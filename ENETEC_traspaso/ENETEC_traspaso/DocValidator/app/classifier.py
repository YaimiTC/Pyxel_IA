"""Clasificador de tipo de documento (EfficientNetV2 entrenado en training/train.py).
Si todavia no hay modelo entrenado, devuelve 'unknown' con confianza 0 y el
pipeline lo trata como documento no valido."""
from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

# Debe coincidir con el tamano usado en training/train.py
IMG_SIZE = 384


@lru_cache
def _load_model(model_path: str, classes_path: str, device: str):
    import timm
    import torch
    from torchvision import transforms

    if device == "cpu":
        import os
        n = max(1, os.cpu_count() or 1)
        torch.set_num_threads(n)
        torch.set_num_interop_threads(max(1, n // 2))

    with open(classes_path, "r", encoding="utf-8") as fh:
        classes = json.load(fh)

    model = timm.create_model(
        "tf_efficientnetv2_s", pretrained=False, num_classes=len(classes)
    )
    model.load_state_dict(torch.load(model_path, map_location=device))
    model.eval().to(device)

    tfm = transforms.Compose(
        [
            transforms.Resize((IMG_SIZE, IMG_SIZE)),
            transforms.ToTensor(),
            transforms.Normalize([0.485, 0.456, 0.406], [0.229, 0.224, 0.225]),
        ]
    )
    return model, classes, tfm


def predict(image_rgb_pil, model_path: Path, classes_path: Path, device: str) -> dict:
    if not Path(model_path).exists() or not Path(classes_path).exists():
        return {"label": "unknown", "confidence": 0.0, "scores": {}}

    import torch

    model, classes, tfm = _load_model(str(model_path), str(classes_path), device)
    x = tfm(image_rgb_pil).unsqueeze(0).to(device)
    with torch.no_grad():
        probs = torch.softmax(model(x), dim=1).cpu().numpy()[0]
    idx = int(probs.argmax())
    return {
        "label": classes[idx],
        "confidence": round(float(probs[idx]) * 100, 1),
        "scores": {classes[i]: round(float(probs[i]) * 100, 1) for i in range(len(classes))},
    }
