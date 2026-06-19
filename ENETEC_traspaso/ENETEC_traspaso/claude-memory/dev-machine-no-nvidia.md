---
name: dev-machine-no-nvidia
description: Hardware PC de desarrollo — AHORA con GPU NVIDIA RTX 3060 (antes solo Intel UHD 630)
metadata: 
  node_type: memory
  type: reference
  originSessionId: 0852c323-f81a-4b41-90ea-80b200e8aa52
---

**ACTUALIZADO 2026-06-15: la PC de desarrollo (Windows 11, `C:\Proyectos`) AHORA SÍ tiene GPU NVIDIA — GeForce RTX 3060, 12 GB VRAM**, driver 610.47 (CUDA UMD 13.3). Antes solo tenía Intel UHD 630 (sin NVIDIA) y se trabajaba en CPU; el UHD 630 sigue como gráficos integrados.

Para usar la GPU con PyTorch: instalar el build CUDA correcto → **torch 2.12.0 + torchvision 0.27.0 desde el índice `cu130`** (`pip install torch==2.12.0 torchvision==0.27.0 --index-url https://download.pytorch.org/whl/cu130 --force-reinstall`). OJO: el índice `cu124` NO tiene la 2.12.0 (máx 2.6.0); el que la tiene es `cu130`. Tras instalar, poner `DOCVAL_DEVICE=cuda` en `DocValidator/.env` y entrenar/servir en GPU (mucho más rápido que CPU).

Python 3.11.9 vía winget en `C:\Users\Home\AppData\Local\Programs\Python\Python311\python.exe`. El lanzador `py` funciona.

Relacionado con [[docvalidator-project]].
