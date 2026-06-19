# Validador de Documentos — Entorno de trabajo (multi-PC)

Repo privado (`validador-de-documentos`) con el proyecto y la **memoria de Claude**. Permite continuar
el trabajo en cualquier PC clonando este repositorio.

> ⚠️ **Clona SIEMPRE en `C:\Proyectos`** (la misma ruta en todas las PCs). Varias
> referencias (montaje de Docker, ruta de la memoria de Claude) dependen de esa ruta.

## Contenido

| Carpeta | Qué es |
|---------|--------|
| `DocValidator/` | Servicio de IA (FastAPI) que valida documentos. Solo código. |
| `doc_verification/` | Módulo Odoo que consume la API de DocValidator. |
| `odoo17/` | Stack Docker de Odoo 17 (compose + config). |
| `claude-memory/` | 🧠 Memoria de Claude (contexto del proyecto entre sesiones/PCs). |
| `.claude/settings.local.json` | Permisos + `autoMemoryDirectory` (apunta a `claude-memory/`). |

## Qué NO está en el repo (y por qué)

- `DocValidator/.venv/` → entorno Python (se recrea con pip).
- `DocValidator/models/*.pt` → modelo entrenado (pesado; se regenera con `train.py`).
- `DocValidator/dataset/` → documentos de muestra (pueden ser datos reales sensibles).
- `**/.env` → configuración local.
- Volúmenes Docker de Odoo (base de datos) → no son ficheros; se recrean.
- Modelos de PaddleOCR (`~/.paddleocr`) → se descargan en el primer uso (o se copian).

## Continuar en una PC nueva (paso a paso)

### 0. Requisitos
- Git, [GitHub CLI](https://cli.github.com/), Python 3.11, Docker Desktop.

### 1. Clonar
```powershell
git clone https://github.com/ntdiaz87-sudo/validador-de-documentos.git C:\Proyectos
cd C:\Proyectos
```

### 2. DocValidator (servicio de IA)
```powershell
cd C:\Proyectos\DocValidator
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
pip install torch torchvision        # + CUDA si hay GPU (ver README de DocValidator)
pip install paddlepaddle==2.6.2 paddleocr==2.8.1
# Reentrenar el clasificador (el modelo no viaja en el repo):
python -m training.make_synthetic_data   # o coloca tus documentos reales en dataset/
python -m training.train --epochs 15
# Levantar la API:
uvicorn app.main:app --host 127.0.0.1 --port 8000
```

### 3. Odoo + módulo
```powershell
cd C:\Proyectos\odoo17
docker compose up -d
# Inicializar BD e instalar el módulo (primera vez en esta PC):
docker exec odoo17-app odoo -d docverif -i base,doc_verification --stop-after-init --without-demo=all
docker restart odoo17-app
```
Luego en Odoo (http://localhost:8069): ajusta el parámetro del sistema
`doc_verification.engine_url` a `http://host.docker.internal:8000`.

### 4. Memoria de Claude
Ya viene en `claude-memory/` y `.claude/settings.local.json` la apunta con
`autoMemoryDirectory`. **Reinicia Claude Code** tras el primer clon para que cargue
la memoria desde el repo.

## Flujo de trabajo (local-first)

Se trabaja **en local** (localhost corriendo, probando todo). Git se usa así:

```powershell
cd C:\Proyectos
git add -A
git commit -m "avance del dia"     # commits LOCALES, cuantos quieras
```

➡️ El **push a la nube (GitHub) se hace SOLO cuando tu decidas** que esta listo:
```powershell
git push                            # solo cuando apruebes subir
```
En la otra PC: `git pull` antes de empezar.

## Base de datos (Odoo) — backups locales

La BD de Odoo y los adjuntos (carnes, etc.) **NO van a Git** (viven en volumenes
Docker y pueden contener datos sensibles). Se gestionan con scripts locales:

```powershell
# Guardar una copia (genera ficheros en C:\Proyectos\backups\ , gitignored)
.\scripts\db-backup.ps1

# Restaurar desde una copia (recrea la BD; CUIDADO: borra la actual)
.\scripts\db-restore.ps1 -DumpFile C:\Proyectos\backups\docverif_AAAAMMDD_HHMMSS.dump

# Restaurar tambien los adjuntos:
.\scripts\db-restore.ps1 -DumpFile <...>.dump -FilestoreDir C:\Proyectos\backups\docverif_filestore_AAAAMMDD_HHMMSS
```

> 💡 Para llevar la BD a otra PC: copia el `.dump` (y la carpeta `_filestore_`) por un
> medio privado (USB, almacenamiento cifrado) y restaura alli. **No subas dumps con
> datos personales a la nube.**

> El **dataset de DocValidator** (`DocValidator/dataset/`) tampoco va a Git por la
> misma razon (puede tener documentos reales). Respaldarlo aparte de forma segura.
