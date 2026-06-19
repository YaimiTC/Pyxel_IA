# DocValidator

Servicio local (offline) de validación de documentos por IA. Recibe un documento
por API y devuelve un veredicto **🟢 passed / 🟡 doubt / 🔴 rejected** junto con el
tipo detectado, la calidad, los campos extraídos y los motivos. Pensado para que
**Odoo** lo consuma como primer filtro antes de la revisión humana.

```
Documento → [Calidad] → [Clasificación IA] → [OCR + Reglas] → Veredicto + Motivos
```

Todo corre en tu máquina con GPU NVIDIA. Nada sale a internet.

---

## 1. Requisitos

- Windows 11 + Python 3.11
- GPU NVIDIA con drivers + CUDA (para entrenar/servir rápido)

## 2. Instalación

```powershell
# 1) Entorno virtual
cd C:\Proyectos\DocValidator
python -m venv .venv
.\.venv\Scripts\Activate.ps1

# 2) Dependencias base
pip install -r requirements.txt

# 3) PyTorch con CUDA (ajusta cu121 a tu versión de CUDA)
pip install torch torchvision --index-url https://download.pytorch.org/whl/cu121

# 4) OCR (PaddleOCR). Si falla la GPU, usa la variante CPU (paddlepaddle)
pip install paddlepaddle-gpu==2.6.1
pip install paddleocr==2.8.1

# 5) Configuración
copy .env.example .env
```

> Si no quieres OCR todavía, pon `DOCVAL_ENABLE_OCR=false` en `.env`: el servicio
> funciona igual (clasificación + calidad) sin instalar Paddle.

## 3. Probar el pipeline completo HOY (con datos sintéticos)

Aún no tienes documentos reales, así que generamos un set de prueba:

```powershell
# Genera dataset/ sintético (carnet, certificación, empresa, _basura)
python -m training.make_synthetic_data

# Entrena el clasificador (usa la GPU automáticamente)
python -m training.train --epochs 15

# Evalúa
python -m training.evaluate
```

## 4. Levantar la API

```powershell
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

- Documentación interactiva: http://127.0.0.1:8000/docs
- Salud del servicio: http://127.0.0.1:8000/health

Probar una validación:

```powershell
python odoo_client_example.py dataset\carnet_identidad\carnet_identidad_000.jpg carnet_identidad
```

## 5. Usar tus documentos reales

1. Borra el contenido sintético de `dataset/`.
2. Crea una carpeta por tipo y mete **todas tus variantes**:
   ```
   dataset/carnet_identidad/   ← todas las variantes de carnet
   dataset/certificacion_legal/
   dataset/doc_empresa/
   dataset/_basura/            ← ejemplos de lo que NO es (recibos, fotos random)
   ```
3. Reentrena: `python -m training.train --epochs 20`
4. Reinicia la API. Listo.

> Recomendado: empezar con varias decenas de imágenes por tipo. Cuantas más
> variantes (fotos torcidas, con flash, escaneadas, móvil), mejor generaliza.

## 6. Añadir un tipo de documento nuevo

1. Crea `dataset/<nuevo_tipo>/` con sus variantes y reentrena.
2. Añade su bloque en `config/document_types.json` (palabras clave, regex, umbral).

No hay que tocar código.

## 7. Cómo se conecta Odoo

El módulo Odoo (modelo `verification.engine`) hace exactamente lo que
`odoo_client_example.py`: un `POST /verify` con `{file_b64, expected_type}`.
La URL del servicio se guarda en Odoo como parámetro del sistema
(`doc_verification.engine_url`), apuntando a la IP del servidor con GPU en la LAN.

Respuesta del servicio:

```json
{
  "verdict": "passed",
  "score": 92.4,
  "expected_type": "carnet_identidad",
  "classified_type": "carnet_identidad",
  "quality": {"score": 78.0, "resolution": [900, 560]},
  "fields": {"numero": "85010112345"},
  "reasons": ["Documento valido"]
}
```

## 8. Estructura

```
DocValidator/
├── app/            servicio FastAPI (API + pipeline + IA)
├── training/       entrenamiento, evaluación y datos sintéticos
├── config/         tipos de documento y reglas (editable)
├── dataset/        tus documentos por carpeta (no se versiona)
├── models/         modelo entrenado (no se versiona)
└── odoo_client_example.py   ejemplo de integración
```

## 9. Roadmap

- **Ahora:** clasificación + calidad + OCR/reglas (filtra "lo que no es ni se parece").
- **Siguiente:** extracción de más campos + validaciones (vigencia, nombre coincide).
- **Después:** migrar clasificador a LayoutLMv3 con datos etiquetados por los revisores.
- **Opcional:** detección de manipulación / anti-falsificación.
