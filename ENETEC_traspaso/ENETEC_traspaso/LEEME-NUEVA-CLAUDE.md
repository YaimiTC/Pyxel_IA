# 📦 Traspaso de proyectos — ENETEC (ODIN 2.0) + DocValidator

> Léeme primero. Este paquete es un **clon de trabajo** de la PC anterior para
> seguir desarrollando estos proyectos en una PC nueva. Contiene los proyectos,
> la base de datos con datos de prueba, el filestore, la memoria de Claude, las
> configuraciones y este instructivo. Responde **siempre en español**.

---

## 0. Resumen de qué hay aquí

| Carpeta | Qué es |
|---|---|
| `odoo-enetradex/` | Proyecto principal: **Odoo 17 en Docker** — sistema ENETEC / ODIN 2.0 (importación de combustibles, acreditación, facturación). Incluye `addons/`, `config/`, `docker-compose.yml`, `Dockerfile`, el **filestore** (`odoo-data/`) y el historial git (`.git/`). |
| `DocValidator/` | **Evaluador de documentos por IA** (FastAPI, offline). Clasifica/valida documentos (passed/doubt/rejected). Odoo lo consume como primer filtro. Puerto 8000. |
| `DocEnhancer/` | Servicio que **realza imágenes/escaneos** antes del OCR (lo usa DocValidator para PYME). Puerto 8800. |
| `claude-memory/` | **Memoria persistente de Claude** (MEMORY.md + fichas .md). Cópiala a la ubicación de memoria de la PC nueva. |
| `db/enetradex_dev.sql.gz` | **Volcado de la base de datos** Odoo con los datos de prueba. |
| `scripts/`, `.claude/` | Proxies de preview y configuración local de Claude Code (`launch.json`, `settings.local.json`). |
| `SETUP.md` | Notas de setup previas (referencia). |

**Importante (rutas):** todo está pensado para vivir en **`C:\Proyectos\`**.
Descomprime ahí para que coincidan las rutas absolutas de `.claude/launch.json`.
Si usas otra ruta, ajusta ese archivo.

Lo que **NO** viene (para no inflar el paquete) y hay que recrear:
- `DocValidator/.venv` y `DocValidator/wheels` (entorno Python de torch CUDA, ~6 GB).
- `DocEnhancer/.venv`.
- `odoo-enetradex/postgres-data/` (la BD viene como volcado en `db/`).
- backups antiguos.
Todo se recrea con los pasos de abajo (hay `requirements.txt` en cada servicio).

---

## 1. Quién es el usuario y cómo trabajar (LEER)

- Usuario: **Nilo** (ntdiaz87@gmail.com). Idioma: **español siempre**.
- Conoce: Docker, PostgreSQL (pg_dump/restore), PowerShell, QWeb/Jinja2, Odoo
  (modelos Python, vistas XML, security CSV), publicWidget JS.

**Forma de trabajo (de la memoria — respétala):**
- **Autonomía:** opera sin pedir permisos para cosas reversibles/locales. Solo
  pregunta cuando sea una **decisión de flujo/negocio** (no para permisos técnicos).
- **Local-first:** trabaja en local. **Solo haz `git push` a la nube con
  aprobación explícita.** Backups de BD locales.
- **Verifica visualmente:** toda UI se revisa con captura/preview y se corre el
  flujo antes de darla por buena (no pedir al usuario que verifique a mano).
- **Idioma de trabajo y de la interfaz: español.**
- PowerShell en Windows: comandos < 965 bytes; si exceden, dividir o usar archivo + `docker cp`.

Lee también:
- `claude-memory/MEMORY.md` (índice) y sus fichas: `working-style-autonomy.md`,
  `git-workflow.md`, `verify-web-designs.md`, `docvalidator-project.md`,
  `pyme-acreditacion.md`, `enetec-workspace-activo.md`, `dev-machine-no-nvidia.md`.
- `odoo-enetradex/CLAUDE.md` (instrucciones detalladas del proyecto Odoo).

> ⚠️ La regla de la memoria/CLAUDE.md de "no tocar contenedores avilmat_/ceimpex_/
> odoo_scem/agrimpex_" era específica de la PC vieja (allí corrían otros proyectos
> en paralelo). En la PC nueva probablemente no existan. Aun así, **solo toca los
> contenedores `enetradex_*`** salvo que el usuario indique lo contrario.

---

## 2. Prerrequisitos en la PC nueva

- **Docker Desktop** (con WSL2).
- **Python 3.11** (para DocValidator / DocEnhancer).
- (Opcional) **GPU NVIDIA + CUDA** para DocValidator/DocEnhancer rápidos. Si no
  hay GPU, funciona en CPU (ver nota en cada servicio).
- Git.

Descomprime el paquete en **`C:\Proyectos\`** de modo que queden:
`C:\Proyectos\odoo-enetradex`, `C:\Proyectos\DocValidator`, etc.

---

## 3. Memoria de Claude

La PC nueva tiene su propia Claude. Copia la carpeta de memoria a la ruta que
Claude use para memoria (en esta PC era **`C:\Proyectos\claude-memory\`**):

```powershell
Copy-Item -Recurse C:\Proyectos\_traspaso\claude-memory C:\Proyectos\claude-memory
```

(Ajusta el origen a donde hayas descomprimido.) `MEMORY.md` es el índice que se
carga cada sesión; cada `.md` es un hecho. Mantén ese sistema.

---

## 4. Montar **odoo-enetradex** (Docker + restaurar BD)

```powershell
cd C:\Proyectos\odoo-enetradex

# 1) Construir y levantar (crea contenedores enetradex_odoo + enetradex_postgres)
docker compose up -d --build

# 2) Esperar a que Postgres esté listo, luego crear la BD vacía
docker exec enetradex_postgres psql -U odoo -d postgres -c "CREATE DATABASE enetradex_dev OWNER odoo;"

# 3) Restaurar el volcado (con los datos de prueba)
docker cp C:\Proyectos\odoo-enetradex\..\db\enetradex_dev.sql.gz enetradex_postgres:/tmp/db.sql.gz
docker exec enetradex_postgres bash -lc "gunzip -c /tmp/db.sql.gz | psql -U odoo -d enetradex_dev"

# 4) Reiniciar Odoo para que tome la BD restaurada
docker compose restart odoo
```

- El **filestore** ya viene en `odoo-enetradex/odoo-data/` (mapeado por compose),
  así que los adjuntos/documentos resuelven sin pasos extra.
- Accede: **http://localhost:8469** (longpolling en 8472).
- Datos de la BD: usuario `odoo` / clave `odoo` (definidos en `docker-compose.yml`).

**Flujo estándar para cambios en un módulo:**
```powershell
docker exec enetradex_odoo odoo -u <modulo> -d enetradex_dev --stop-after-init
docker restart enetradex_odoo
```
Luego prueba en http://localhost:8469 (incógnito + Ctrl+Shift+R).

---

## 5. Montar **DocValidator** (evaluador de documentos, puerto 8000)

Ver `DocValidator/README.md` para el detalle. Resumen:

```powershell
cd C:\Proyectos\DocValidator
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
# torch con CUDA (en esta PC se usaba el índice cu130):
#   pip install torch --index-url https://download.pytorch.org/whl/cu130
# Si NO hay GPU: instala torch CPU y pon DOCVAL_DEVICE=cpu en el .env

# Arrancar el servicio
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

- Config en `DocValidator/.env` (host, puerto, `DOCVAL_DEVICE=cuda|cpu`, OCR,
  y `DOCVAL_ENHANCER_URL=http://127.0.0.1:8800`).
- Los **modelos** entrenados vienen en `DocValidator/models/` y los **datasets**
  de entrenamiento/prueba en `dataset*/` y `Pyme/` (documentos PYME reales).
- Odoo lo llama vía `host.docker.internal:8000` (endpoint `/pyme/verify`).

## 6. Montar **DocEnhancer** (realce de imágenes, puerto 8800)

```powershell
cd C:\Proyectos\DocEnhancer
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn app.main:app --host 0.0.0.0 --port 8800
```
- Sus modelos vienen en `DocEnhancer/models/`.
- DocValidator lo usa para realzar escaneos antes del OCR (campo
  `DOCVAL_ENHANCER_URL` del `.env` de DocValidator).

## 7. Preview de Claude Code (opcional)

`.claude/launch.json` define proxies para previsualizar Odoo (puerto 8470 → 8469)
con scripts en `scripts/` y `odoo-enetradex/.claude/`. Usa rutas absolutas
`C:\Proyectos\...`; si descomprimiste en otra ruta, edítalas.

---

## 8. Credenciales y accesos (entorno de prueba)

- Odoo admin: **admin / admin**.
- BD Postgres: **odoo / odoo**.
- Usuarios de prueba creados (todos con clave **Test1234!**):
  - `cliente.final@enetradex.test` → Pyme Combustibles del Este S.R.L. (cliente **acreditado**).
  - `pyme.exp@test.cu` → cliente **no acreditado** (sirve para ver el flujo completo de acreditación).
- Estos son datos de prueba; cámbialos antes de cualquier uso real.

---

## 9. Estado actual del trabajo (resumen)

El proyecto Odoo implementa, además del core de importación, lo construido en las
últimas sesiones (todo en `pyxel_enetradex_backend` / `pyxel_enetradex_website`):

- **Asistente web `/en/wizard`**: acreditación + solicitud de importación
  (multiproducto, formas de pago, presupuesto, especificaciones, documentos del
  embarque + país de origen + certificados, socio cubano, etc.).
- **Expediente de acreditación** (3 pasos: IA → abogada → comercial) con
  validación real por DocValidator al subir documentos.
- **Flujo de aprobación de solicitud**: botón "Aprobar solicitud" (comercial) que
  crea **orden de compra al proveedor** + **oferta de venta al cliente** (borrador)
  y mueve la etapa a **SOLICITUDES APROBADAS** (antes "Trámites en origen").
  Precarga **líneas de costo** desde la categoría de producto "Costos de importación".
- **Multimoneda**: cada línea de costo lleva su moneda; "Generar venta de costos"
  crea **una venta/factura por moneda** (USD/CUP). CUP activada.
- **Diseño de documentos ENETEC**: compañía configurada (ENETEC S.A., NIT
  30004148361, La Habana), reportes en español, layout propio
  (`external_layout_enetec`) con cabecera de marca + pie, aplicado a TODOS los
  documentos (factura, venta, compra). **Pendiente:** poner el **logo real de
  ENETEC** (ahora hay uno temporal) y los **datos bancarios** del pie.
- **Fase 2 pendiente (DocValidator)**: extraer por IA el precio desde el documento
  de oferta del proveedor para rellenar PO/oferta y calcular el margen.

Para el detalle técnico fino, revisa el historial git de `odoo-enetradex` y las
fichas de `claude-memory/`.

---

## 10. Checklist rápido de arranque

1. Descomprimir en `C:\Proyectos\`.
2. Copiar `claude-memory/` a la ruta de memoria de la Claude nueva.
3. `docker compose up -d --build` en `odoo-enetradex/` + restaurar BD (sección 4).
4. Crear venv + instalar DocValidator (8000) y DocEnhancer (8800).
5. Abrir http://localhost:8469 (admin/admin) y verificar.
