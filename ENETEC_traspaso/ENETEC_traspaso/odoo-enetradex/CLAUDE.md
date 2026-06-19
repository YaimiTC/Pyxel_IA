# Proyecto Odoo — ENETEC (Sistema de Gestión Comercial ODIN 2.0)

> Este proyecto nació como clon del proyecto AGRIMPEX (C:\odoo_agrimpex), que a su
> vez fue clon de CEIMPEX. Se rebrandeó a **ENETEC / ODIN 2.0**: contenedores,
> puertos, base de datos, los 4 módulos de marca (`pyxel_agrimpex_*` ->
> `pyxel_enetradex_*`), sus modelos (`pyxel.agrimpex.conciliation.*` ->
> `pyxel.enetradex.conciliation.*`), ids y referencias técnicas. El resto de
> módulos (`pyxel_import_*`, `transport_hub`, etc.) son genéricos y mantienen su
> nombre original.
>
> CLIENTE: Sociedad Mercantil **ENETEC S.A.** (100% cubano, NIT 30004148361),
> importadora de **COMBUSTIBLES** (gasolinas, diésel, Jet A-1, fuel oíl, GLP)
> vinculada a CUPET. Cadena logística: depósito/custodia = ENCC; transporte = EPEP;
> distribución por servicentros = CIMEX y KM0. Proveedor del software = PCT de La
> Habana (3CE) / PYXEL Solutions (modalidad SaaS). Sistema = "ODIN 2.0".
>
> ALCANCE ODIN 2.0 (3 servicios): (1) Importación Online, (2) Tienda Online con
> pago en el exterior, (3) Gestión de actividades comerciales (módulos Odoo
> estándar). Tarifas: Importación 0.3% AWB/CIF/CFR; Comercialización 0.01 USD/litro.
>
> ⚠️ REDISEÑO WEB: el tema `pyxel_enetradex_custom_web_theme` AÚN tiene la identidad
> visual de Agrimpex (textos "Agrimpex Caribe", clases `.ag-*`, imágenes del agro
> `logo_agrimpex.png`, sectores agrícolas). Es PROVISIONAL — se rediseñará por
> completo para ENETEC/combustibles cuando el usuario aporte mockups y paleta. NO
> editar home/navbar/footer desde el editor web de Odoo (crea copias COW que tapan
> los cambios del módulo): editar SOLO por código + `-u pyxel_enetradex_custom_web_theme`.

## Stack técnico
- Odoo 17 en Docker (imagen custom: enetradex/odoo:17)
- PostgreSQL 15 en Docker
- Containers: enetradex_odoo (servicio odoo) + enetradex_postgres (servicio db)
- Base de datos Odoo: enetradex_dev (NUEVA y limpia; sin datos de Agrimpex)
- URL local: http://localhost:8469 (host 8469 -> container 8069)
- Longpolling: http://localhost:8472 (host 8472 -> container 8072)
- Credenciales DB (dev): user odoo / pass odoo / host db / puerto 5432
- SO host: Windows + PowerShell 7
- Idioma de trabajo: espanol

## Rutas clave (host)
- Raiz: C:\odoo_enetradex
- Addons: C:\odoo_enetradex\addons\ -> /mnt/extra-addons
- Config: C:\odoo_enetradex\config\odoo.conf -> /etc/odoo/odoo.conf
- Filestore: C:\odoo_enetradex\odoo-data\ -> /var/lib/odoo
- Postgres data: C:\odoo_enetradex\postgres-data\
- Documentacion del cliente: C:\odoo_enetradex\ENETEC SA\ (contratos, manual, logo; texto extraido en _txt\)

## Modulos custom (16) en addons/
- pyxel_enetradex_backend            (marca)
- pyxel_enetradex_conciliation_report (marca; modelos pyxel.enetradex.conciliation.*)
- pyxel_enetradex_custom_web_theme   (marca; tema web, visual aun de Agrimpex = provisional)
- pyxel_enetradex_website            (marca)
- pyxel_custom_invoice_format
- pyxel_import_api
- pyxel_import_backend               (motor del proceso de importacion; generico)
- pyxel_import_conciliation_report
- pyxel_import_email_excel
- pyxel_import_recaptcha
- pyxel_import_website
- pyxel_phone_signup_signin
- pyxel_po_so_report_currency
- pyxel_sale_available_budget
- pyxel_sale_process_sequence
- transport_hub

## Sobre el usuario
- Idioma: espanol (responder siempre en espanol)
- Hay otros proyectos Odoo corriendo en paralelo en esta máquina. NO TOCAR:
  - avilmat_odoo  / avilmat_postgres  -> puerto 8069
  - ceimpex_odoo  / ceimpex_postgres  -> puerto 8169
  - odoo_scem     / odoo_scem_db      -> puerto 8269
  - agrimpex_odoo / agrimpex_postgres -> puerto 8369 (proyecto origen de este clon)

## Conocimiento tecnico del usuario
- Docker: docker exec, docker compose, docker cp, docker logs
- PostgreSQL: pg_dump, restore
- PowerShell: Get-Content, Select-String, Copy-Item, Compress-Archive
- QWeb / Jinja2 (web y PDF)
- publicWidget (JS frontend Odoo)
- Backend Odoo: modelos Python, vistas XML, security CSV
- Migraciones de datos, hooks de instalacion
- Edicion cuidadosa de Dockerfile y odoo.conf

## Reglas de autonomia

### Pre-aprobados (ejecutar sin preguntar)
- docker exec contra enetradex_odoo y enetradex_postgres
- docker compose dentro de C:\odoo_enetradex
- docker cp, docker logs
- curl.exe contra localhost (8469, 8472)
- PowerShell read-only: Get-Content, Get-Item, Get-ChildItem, Select-String
- Copy-Item, Compress-Archive
- Remove-Item SOLO dentro de backup/ o tmp_*
- Comandos con $() o $variable
- Crear/editar archivos dentro de C:\odoo_enetradex\addons\
- pg_dump contra enetradex_postgres

### Preguntar antes de ejecutar
- Remove-Item -Recurse fuera de backup/ o tmp_*
- DROP o DELETE FROM sin WHERE
- Modificar docker-compose.yml, Dockerfile o odoo.conf
- Tocar containers que NO sean enetradex_* (especialmente avilmat_*, ceimpex_*, odoo_scem, agrimpex_*)
- Tocar core de Odoo (todo lo que no sea un addon custom)
- Restore de base de datos
- Acciones sobre postgres-data/ o odoo-data/ desde el host

## Restricciones tecnicas
- Comandos PowerShell deben ser <965 bytes
- Si exceden: dividir en pasos o usar archivo + docker cp

## Estilo de trabajo
- Prompts atomicos: 1 tarea por vez
- Despues de cada cambio importante:
  1. Backup BD con pg_dump
  2. Snapshot zip del modulo con Compress-Archive
- Test visual obligatorio: modo incognito + Ctrl+Shift+R

## Flujo estandar para cambios en modulo
1. Backup BD + snapshot zip del modulo
2. Aplicar cambio en addons/<modulo>/
3. docker exec enetradex_odoo odoo -u <modulo> -d enetradex_dev --stop-after-init
4. docker restart enetradex_odoo
5. Test visual en http://localhost:8469 en incognito con Ctrl+Shift+R
6. Revisar docker logs enetradex_odoo si hay error
