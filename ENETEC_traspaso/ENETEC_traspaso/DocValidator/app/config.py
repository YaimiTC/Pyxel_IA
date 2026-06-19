"""Configuracion del servicio. Se ajusta por variables de entorno (prefijo DOCVAL_)
o por el fichero .env. Los tipos de documento y sus reglas viven en
config/document_types.json para poder editarlos sin tocar codigo."""
from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="DOCVAL_", env_file=".env", extra="ignore")

    host: str = "0.0.0.0"
    port: int = 8000
    device: str = "cuda"  # "cuda" si hay GPU, "cpu" en caso contrario

    model_path: Path = BASE_DIR / "models" / "classifier.pt"
    classes_path: Path = BASE_DIR / "models" / "classes.json"
    types_config: Path = BASE_DIR / "config" / "document_types.json"

    # Clasificador PYME separado (CNN de apoyo: 5 documentos + _basura).
    pyme_model_path: Path = BASE_DIR / "models" / "classifier_pyme.pt"
    pyme_classes_path: Path = BASE_DIR / "models" / "classifier_pyme.json"

    # DocEnhancer (realce de escaneos). Vacio = sin realce (degrada con elegancia).
    enhancer_url: str = ""

    ocr_lang: str = "es"
    enable_ocr: bool = True

    def load_types(self) -> dict:
        with open(self.types_config, "r", encoding="utf-8") as fh:
            return json.load(fh)


@lru_cache
def get_settings() -> Settings:
    return Settings()
