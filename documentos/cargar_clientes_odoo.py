"""
Carga clientes desde Analisis_completo_clientes.xlsx (hoja Clientes_con_ops) a Odoo via XML-RPC.
Procesa solo los registros con Correo O Teléfono no vacíos.

DRY_RUN = True  -> solo imprime lo que haría, sin crear nada
DRY_RUN = False -> ejecuta de verdad
"""

import xmlrpc.client
import pandas as pd
import re
import sys

# ── Configuración ──────────────────────────────────────────────────────────────
ODOO_URL  = "http://localhost:8469"
ODOO_DB   = "enetradex_dev"
ODOO_USER = "admin"
ODOO_PASS = "admin"

EXCEL_PATH = r"D:\trabajo\Pyxel\ENETET\Analisis_completo_clientes.xlsx"
SHEET_NAME = "Clientes_con_ops"

TEMP_PASSWORD = "Enetec2026!"

DRY_RUN = True   # ← Cambiar a False para ejecutar de verdad
# ──────────────────────────────────────────────────────────────────────────────

def conectar():
    common = xmlrpc.client.ServerProxy(f"{ODOO_URL}/xmlrpc/2/common")
    uid = common.authenticate(ODOO_DB, ODOO_USER, ODOO_PASS, {})
    if not uid:
        print("ERROR: No se pudo autenticar en Odoo.")
        sys.exit(1)
    models = xmlrpc.client.ServerProxy(f"{ODOO_URL}/xmlrpc/2/object")
    return uid, models

def call(models, uid, model, method, args, kwargs=None):
    return models.execute_kw(ODOO_DB, uid, ODOO_PASS, model, method, args, kwargs or {})

def limpiar_str(val):
    if pd.isna(val):
        return None
    s = str(val).strip()
    return s if s else None

def limpiar_nit(val):
    if pd.isna(val):
        return None
    try:
        # Viene como float científico (ej. 5.000431e+10) -> entero -> string
        return str(int(float(val)))
    except Exception:
        s = str(val).strip()
        return s if s else None

def primer_telefono(val):
    """Extrae el primer número de teléfono de strings como '58061679 - 58210405'."""
    if pd.isna(val):
        return None
    s = str(val).strip()
    # Tomar el primer token separado por -, coma o espacio doble
    partes = re.split(r"\s*[-,]\s*", s)
    for p in partes:
        p = p.strip()
        if re.search(r"\d{7,}", p):
            # Quitar texto no numérico al final (ej. "- 85042608421" en nombres)
            m = re.search(r"\d[\d\s]{6,}", p)
            if m:
                return m.group(0).strip()
    return s[:20]  # fallback: truncar

def primer_correo(val):
    """Extrae el primer correo de strings con múltiples correos."""
    if pd.isna(val):
        return None
    s = str(val).strip()
    # Buscar patrón de email
    emails = re.findall(r"[\w.\-+]+@[\w.\-]+\.[a-zA-Z]{2,}", s)
    if emails:
        return emails[0].strip()
    return None

def primer_nombre_representante(val):
    """De 'Nombre Apellido - CI, Otro Nombre - ...' extrae solo el primer nombre completo."""
    if pd.isna(val):
        return None
    s = str(val).strip()
    if not s:
        return None
    # Tomar el primer bloque antes de coma o salto de línea
    primer = re.split(r"[,\n]", s)[0].strip()
    # Quitar sufijos como "- CI", "- Administrador", "- Gerente", "- Presidente..."
    primer = re.sub(r"\s*-\s*(CI|Presidente|Administrador|Gerente|Director|Pdte|Esp\.?|[A-Z]{2,})[^\-]*$", "", primer, flags=re.IGNORECASE).strip()
    # Quitar número de CI (9-11 dígitos) con guion previo
    primer = re.sub(r"\s*-\s*\d{9,}\s*$", "", primer).strip()
    primer = primer.rstrip(" -").strip()
    return primer if primer else None

def buscar_contact_type(models, uid, nombre="Cliente nacional"):
    ids = call(models, uid, "res.partner.contact.type", "search", [[["name", "=", nombre]]])
    return ids[0] if ids else None

def buscar_management_type(models, uid):
    """Devuelve dict {name: id} de todos los tipos de gestión."""
    recs = call(models, uid, "res.partner.management.type", "search_read", [[]], {"fields": ["id", "name"]})
    return {r["name"]: r["id"] for r in recs}

def buscar_grupo_portal(models, uid):
    ids = call(models, uid, "res.groups", "search", [[["full_name", "=", "Extra Rights / Portal"]]])
    if not ids:
        ids = call(models, uid, "res.groups", "search", [[["name", "=", "Portal"]]])
    return ids[0] if ids else None

def buscar_empresa(models, uid, nombre, nit):
    """Busca empresa por NIT primero, luego por nombre exacto."""
    if nit:
        ids = call(models, uid, "res.partner", "search",
                   [[["vat", "=", nit], ["is_company", "=", True]]])
        if ids:
            return ids[0]
    ids = call(models, uid, "res.partner", "search",
               [[["name", "=", nombre], ["is_company", "=", True]]])
    return ids[0] if ids else None

def buscar_contacto(models, uid, parent_id):
    ids = call(models, uid, "res.partner", "search",
               [[["parent_id", "=", parent_id], ["company_type", "=", "person"]]])
    return ids[0] if ids else None

def buscar_usuario(models, uid, login):
    ids = call(models, uid, "res.users", "search", [[["login", "=", login]]])
    return ids[0] if ids else None

def buscar_lead(models, uid, partner_id):
    ids = call(models, uid, "crm.lead", "search",
               [[["partner_id", "=", partner_id], ["type", "=", "opportunity"]]])
    return ids[0] if ids else None

def main():
    print("=" * 60)
    print(f"MODO: {'DRY RUN (sin cambios)' if DRY_RUN else '*** EJECUCIÓN REAL ***'}")
    print("=" * 60)

    # ── Leer Excel ────────────────────────────────────────────────────────────
    df = pd.read_excel(EXCEL_PATH, sheet_name=SHEET_NAME)
    print(f"\nExcel cargado: {len(df)} filas, columnas: {list(df.columns)}\n")

    # Filtrar solo los que tienen Correo o Teléfono
    mask = df["Correo"].notna() | df["Teléfono"].notna()
    df = df[mask].copy()
    print(f"Registros con Correo o Teléfono: {len(df)}\n")

    # ── Conectar a Odoo ───────────────────────────────────────────────────────
    uid, models = conectar()
    print(f"Conectado a Odoo como uid={uid}\n")

    # Cachear datos auxiliares
    contact_type_id  = buscar_contact_type(models, uid)
    management_types = buscar_management_type(models, uid)
    grupo_portal_id  = buscar_grupo_portal(models, uid)

    print(f"contact_type 'Cliente nacional' id={contact_type_id}")
    print(f"management_types disponibles: {list(management_types.keys())}")
    print(f"grupo portal id={grupo_portal_id}\n")

    # ── Contadores ────────────────────────────────────────────────────────────
    empresas_creadas    = 0
    empresas_actualizadas = 0
    contactos_creados   = 0
    usuarios_creados    = 0
    leads_creados       = 0
    errores             = []

    # ── Procesar cada fila ────────────────────────────────────────────────────
    for idx, row in df.iterrows():
        nombre_empresa = limpiar_str(row.get("Cliente"))
        if not nombre_empresa:
            print(f"[FILA {idx}] Sin nombre de empresa, saltando.")
            continue

        nit          = limpiar_nit(row.get("NIT"))
        correo_raw   = limpiar_str(row.get("Correo"))
        telefono_raw = limpiar_str(row.get("Teléfono"))
        correo       = primer_correo(correo_raw)
        telefono     = primer_telefono(telefono_raw)
        municipio    = limpiar_str(row.get("Municipio"))
        provincia    = limpiar_str(row.get("Provincia"))
        representante_raw = limpiar_str(row.get("Representante"))
        representante = primer_nombre_representante(representante_raw)

        print(f"\n{'-'*60}")
        print(f"[FILA {idx}] Empresa: {nombre_empresa}")
        print(f"  NIT={nit}  Correo={correo}  Tel={telefono}")
        print(f"  Representante={representante}  Municipio={municipio}  Provincia={provincia}")

        try:
            # ── PASO 1: res.partner empresa ──────────────────────────────────
            vals_empresa = {
                "name"          : nombre_empresa,
                "is_company"    : True,
                "company_type"  : "company",
                "customer_rank" : 1,
            }
            if nit:
                vals_empresa["vat"] = nit
            if municipio:
                vals_empresa["city"] = municipio
            if provincia:
                vals_empresa["street"] = provincia   # No hay campo provincia estándar; usamos comment/street
            if telefono:
                vals_empresa["phone"] = telefono
            if correo:
                vals_empresa["email"] = correo
            if contact_type_id:
                vals_empresa["contact_type_id"] = contact_type_id

            empresa_id = buscar_empresa(models, uid, nombre_empresa, nit)

            if empresa_id:
                print(f"  -> Empresa ya existe (id={empresa_id}), actualizando...")
                if not DRY_RUN:
                    call(models, uid, "res.partner", "write", [[empresa_id], vals_empresa])
                empresas_actualizadas += 1
            else:
                print(f"  -> Creando empresa nueva...")
                if not DRY_RUN:
                    empresa_id = call(models, uid, "res.partner", "create", [vals_empresa])
                    print(f"     Empresa creada id={empresa_id}")
                else:
                    empresa_id = f"<nuevo:{nombre_empresa}>"
                empresas_creadas += 1

            # ── PASO 2: res.partner contacto individual ───────────────────────
            nombre_contacto = representante or nombre_empresa
            vals_contacto = {
                "name"         : nombre_contacto,
                "company_type" : "person",
                "type"         : "contact",
            }
            if correo:
                vals_contacto["email"] = correo
            if telefono:
                vals_contacto["phone"] = telefono
            if not DRY_RUN and isinstance(empresa_id, int):
                vals_contacto["parent_id"] = empresa_id

            contacto_id = None
            if not DRY_RUN and isinstance(empresa_id, int):
                contacto_id = buscar_contacto(models, uid, empresa_id)

            if contacto_id:
                print(f"  -> Contacto ya existe (id={contacto_id}), actualizando...")
                if not DRY_RUN:
                    call(models, uid, "res.partner", "write", [[contacto_id], vals_contacto])
            else:
                print(f"  -> Creando contacto individual: {nombre_contacto}")
                if not DRY_RUN and isinstance(empresa_id, int):
                    vals_contacto["parent_id"] = empresa_id
                    contacto_id = call(models, uid, "res.partner", "create", [vals_contacto])
                    print(f"     Contacto creado id={contacto_id}")
                else:
                    contacto_id = f"<nuevo_contacto:{nombre_contacto}>"
                contactos_creados += 1

            # ── PASO 3: res.users usuario portal ─────────────────────────────
            login = correo if correo else telefono
            if login:
                usuario_existente = None
                if not DRY_RUN:
                    usuario_existente = buscar_usuario(models, uid, login)

                if usuario_existente:
                    print(f"  -> Usuario ya existe (login={login}), NO se crea.")
                else:
                    print(f"  -> Creando usuario portal: login={login}")
                    if not DRY_RUN and isinstance(contacto_id, int) and grupo_portal_id:
                        vals_user = {
                            "name"       : nombre_contacto,
                            "login"      : login,
                            "partner_id" : contacto_id,
                            "password"   : TEMP_PASSWORD,
                            "groups_id"  : [(6, 0, [grupo_portal_id])],
                        }
                        user_id = call(models, uid, "res.users", "create", [vals_user])
                        print(f"     Usuario creado id={user_id}")
                    usuarios_creados += 1
            else:
                print(f"  -> Sin login disponible, no se crea usuario.")

            # ── PASO 4: crm.lead oportunidad ──────────────────────────────────
            lead_existente = None
            if not DRY_RUN and isinstance(empresa_id, int):
                lead_existente = buscar_lead(models, uid, empresa_id)

            if lead_existente:
                print(f"  -> Lead ya existe (id={lead_existente}), NO se crea otro.")
            else:
                print(f"  -> Creando oportunidad: Acreditación — {nombre_empresa}")
                if not DRY_RUN and isinstance(empresa_id, int):
                    vals_lead = {
                        "name"       : f"Acreditación — {nombre_empresa}",
                        "partner_id" : empresa_id,
                        "type"       : "opportunity",
                        "user_id"    : False,
                    }
                    # Campo en_initiated_by — existe solo en módulos personalizados
                    try:
                        vals_lead["en_initiated_by"] = "self"
                        lead_id = call(models, uid, "crm.lead", "create", [vals_lead])
                    except Exception:
                        del vals_lead["en_initiated_by"]
                        lead_id = call(models, uid, "crm.lead", "create", [vals_lead])
                    print(f"     Lead creado id={lead_id}")
                leads_creados += 1

        except Exception as e:
            msg = f"[FILA {idx}] ERROR en '{nombre_empresa}': {e}"
            print(f"  *** {msg}")
            errores.append(msg)
            continue

    # ── Resumen ───────────────────────────────────────────────────────────────
    print("\n" + "=" * 60)
    print("RESUMEN FINAL")
    print("=" * 60)
    print(f"  Empresas creadas:      {empresas_creadas}")
    print(f"  Empresas actualizadas: {empresas_actualizadas}")
    print(f"  Contactos creados:     {contactos_creados}")
    print(f"  Usuarios creados:      {usuarios_creados}")
    print(f"  Leads creados:         {leads_creados}")
    print(f"  Errores:               {len(errores)}")
    if errores:
        print("\nDetalle de errores:")
        for e in errores:
            print(f"  - {e}")
    print("=" * 60)
    if DRY_RUN:
        print("RECUERDA: esto fue un DRY RUN. Cambia DRY_RUN = False para ejecutar.")

if __name__ == "__main__":
    main()
