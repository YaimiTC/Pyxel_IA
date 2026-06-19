# DocEnhancer

Microservicio **local** (offline) de realce de imagen de documentos. Es el
**primer paso** del flujo de verificacion: recibe lo que el cliente sube, lo
lleva al maximo de legibilidad y devuelve la imagen mejorada para que el
OCR/clasificador de **DocValidator** lean mucho mejor.

```
Cliente sube  ->  Odoo  ->  [DocEnhancer /enhance]  ->  DocValidator /verify  ->  veredicto
                              (realce de imagen)         (clasifica + OCR)
```

## Que hace (todo con vision por computador, sin nube)

1. Auto-orientacion
2. **Deteccion del documento + correccion de perspectiva (dewarp)** — aplana fotos tomadas en angulo
3. **Deskew** — endereza la inclinacion fina del escaneo
4. **Eliminacion de sombras / iluminacion despareja** (normalizacion de fondo)
5. **Reduccion de ruido** preservando bordes del texto
6. **Contraste local adaptativo (CLAHE)**
7. **Super-resolucion** — DNN local (si hay modelo en `models/`) o interpolacion cubica
8. **Nitidez** (unsharp mask)

Cada paso es defensivo: ante un fallo conserva el resultado anterior.

## Ejecutar

```bash
python -m venv .venv
.venv\Scripts\pip install -r requirements.txt
.venv\Scripts\python -m uvicorn app.main:app --host 0.0.0.0 --port 8800
```

## API

- `GET /health` — estado y modo de super-resolucion.
- `POST /enhance` — JSON `{file_b64, filename?, dewarp?}` → `{ok, image_b64, mime, meta}` (lo consume Odoo).
- `POST /enhance-upload` — multipart `file` → devuelve el PNG realzado (pruebas manuales / navegador).

## Super-resolucion por DNN (opcional, local)

Por defecto usa interpolacion cubica. Para activar super-resolucion neuronal,
coloca un modelo de OpenCV en `models/` (se cargan automaticamente):

- `models/EDSR_x2.pb`  (mejor calidad, mas lento)
- `models/FSRCNN_x2.pb` (muy rapido, ligero)

Modelos oficiales: https://github.com/opencv/opencv_contrib/tree/master/modules/dnn_superres
Una vez descargado el `.pb`, queda 100% local/offline.

## PDF

Si `PyMuPDF` esta instalado, rasteriza la primera pagina del PDF antes de realzar.
