"""
Carga trabajadores de ENETEC desde 'Permisos Pyxcel.xlsx' como usuarios internos en Odoo.
Por cada trabajador crea:
  - res.partner  (contacto individual vinculado a ENETEC S.A.)
  - res.users    (usuario interno con grupos según cargo)

Grupos descubiertos en enetradex_dev:
  1   Internal User (base de todo usuario interno)
  2   Administration / Access Rights
  4   Administration / Settings
  21  Sales / User: Own Documents Only
  22  Sales / User: All Documents
  23  Sales / Administrator
  25  Technical / Show Accounting Features - Readonly
  27  Technical / Show Full Accounting Features
  78  ENETRADEX / Abogada / Revisora legal
  79  ENETRADEX / Comercial
  80  Aduana / Apoderado de aduana
"""

import xmlrpc.client
import pandas as pd
import sys

ODOO_URL   = "http://localhost:8469"
ODOO_DB    = "enetradex_dev"
ODOO_USER  = "admin"
ODOO_PASS  = "admin"
EXCEL_PATH = r"D:\trabajo\Pyxel\ENETET\Permisos Pyxcel.xlsx"
SHEET_NAME = "23-06"
TEMP_PASS  = "Enetec2026!"
DRY_RUN    = False  # <- cambiar a True para modo seguro

# Empresa ENETEC S.A. en Odoo (res.partner empresa)
EMPRESA_NOMBRE = "ENETEC S.A."

# Mapeo cargo -> lista de group ids (además del 1 = Internal User, siempre incluido)
GRUPOS_POR_CARGO = {
    "gerente general":          [4, 2],          # Admin Settings + Access Rights
    "vice gerente":             [23],            # Sales Administrator
    "gerente de negocios":      [22],            # Sales User All + comercial
    "gerente enetec s.a.":      [22],
    "inteligencia comercial":   [79],            # ENETRADEX Comercial
    "atención al cliente":      [79],            # ENETRADEX Comercial
    "comercial":                [79],            # ENETRADEX Comercial (read enforced by record rules)
    "facturadora":              [79],            # ENETRADEX Comercial (acceso importaciones)
    "asesora jurídica":         [78],            # ENETRADEX Abogada / Revisora legal
    "apoderado de aduana":      [80],            # Aduana / Apoderado de aduana
    "informático":              [4, 2],          # Admin técnico
}


def normalizar_cargo(cargo):
    if not cargo:
        return ""
    c = str(cargo).strip().lower()
    # Buscar coincidencia parcial en el mapa
    for key in GRUPOS_POR_CARGO:
        if key in c or c in key:
            return key
    return c


def call(m, uid, model, method, args, kw=None):
    return m.execute_kw(ODOO_DB, uid, ODOO_PASS, model, method, args, kw or {})


def main():
    print("=" * 60)
    print(f"MODO: {'DRY RUN' if DRY_RUN else '*** EJECUCION REAL ***'}")
    print("=" * 60)

    df = pd.read_excel(EXCEL_PATH, sheet_name=SHEET_NAME, header=3)
    df.columns = ["No", "Nombre", "Cargo", "Correo", "Obs"]
    df = df[df["No"].notna() & df["Nombre"].notna()].copy()
    print(f"\n{len(df)} trabajadores encontrados\n")

    common = xmlrpc.client.ServerProxy(f"{ODOO_URL}/xmlrpc/2/common")
    uid = common.authenticate(ODOO_DB, ODOO_USER, ODOO_PASS, {})
    m = xmlrpc.client.ServerProxy(f"{ODOO_URL}/xmlrpc/2/object")
    print(f"Conectado uid={uid}\n")

    # Buscar empresa ENETEC S.A.
    emp_ids = call(m, uid, "res.partner", "search",
                   [[["name", "ilike", "ENETEC"], ["is_company", "=", True]]])
    empresa_id = emp_ids[0] if emp_ids else None
    print(f"Empresa ENETEC id={empresa_id}\n")

    creados = errores = omitidos = 0

    for _, row in df.iterrows():
        nombre = str(row["Nombre"]).strip()
        cargo  = str(row["Cargo"]).strip() if pd.notna(row["Cargo"]) else ""
        correo = str(row["Correo"]).strip() if pd.notna(row["Correo"]) else ""
        obs    = str(row["Obs"]).strip() if pd.notna(row["Obs"]) else ""

        if not correo or correo.lower() == "pendiente":
            print(f"  [SKIP] {nombre} — correo pendiente")
            omitidos += 1
            continue

        cargo_key = normalizar_cargo(cargo)
        grupos_extra = GRUPOS_POR_CARGO.get(cargo_key, [])
        todos_grupos = list(set([1] + grupos_extra))  # 1 = Internal User siempre

        print(f"\n  {nombre} | {cargo}")
        print(f"    login={correo}  grupos={todos_grupos}")

        try:
            # Verificar si ya existe usuario
            exist = call(m, uid, "res.users", "search", [[["login", "=", correo]]])
            if exist:
                print(f"    -> Usuario ya existe (id={exist[0]}), saltando.")
                omitidos += 1
                continue

            if not DRY_RUN:
                # 1. Crear contacto
                vals_p = {
                    "name":         nombre,
                    "company_type": "person",
                    "type":         "contact",
                    "email":        correo,
                    "function":     cargo,
                }
                if empresa_id:
                    vals_p["parent_id"] = empresa_id

                partner_id = call(m, uid, "res.partner", "create", [vals_p])
                print(f"    -> Contacto creado id={partner_id}")

                # 2. Crear usuario interno
                vals_u = {
                    "name":       nombre,
                    "login":      correo,
                    "password":   TEMP_PASS,
                    "partner_id": partner_id,
                    "groups_id":  [(6, 0, todos_grupos)],
                }
                user_id = call(m, uid, "res.users", "create", [vals_u])
                print(f"    -> Usuario creado id={user_id}")
            else:
                print(f"    -> [DRY] Crearía contacto + usuario")

            creados += 1

        except Exception as e:
            print(f"    *** ERROR: {e}")
            errores += 1

    print("\n" + "=" * 60)
    print(f"  Creados:  {creados}")
    print(f"  Omitidos: {omitidos}")
    print(f"  Errores:  {errores}")
    print("=" * 60)
    if DRY_RUN:
        print("DRY RUN: cambia DRY_RUN = False para ejecutar de verdad.")


if __name__ == "__main__":
    main()
