# ══════════════════════════════════════════════════════════
#  Imagen Odoo 17 personalizada para ENETEC (ODIN 2.0)
# ══════════════════════════════════════════════════════════
FROM odoo:17

USER root

RUN apt-get update && apt-get install -y --no-install-recommends \
        python3-pandas \
        python3-numpy \
        python3-openpyxl \
        python3-xlrd \
        python3-xlsxwriter \
        python3-chardet \
    && rm -rf /var/lib/apt/lists/*


# ── FIX SCSS: Odoo 17.0-20260609 regression ─────────────────────────────────
# bootstrap_overridden_frontend.scss usa $gray-200 y $black antes de que estén
# definidas. Fix 1: inyectar $gray-200 en secondary_variables.scss (idempotente).
RUN SCSS=/usr/lib/python3/dist-packages/odoo/addons/web/static/src/scss/secondary_variables.scss && \
    grep -q '\$gray-200: #e9ecef' "$SCSS" || \
    sed -i '1s/^/$gray-200: #e9ecef !default;\n/' "$SCSS"

# Fix 2: añadir pre_variables.scss al inicio de web._assets_frontend_helpers
# en el __manifest__.py del módulo web (idempotente via Python).
RUN python3 - <<'PYEOF'
import re, sys
path = '/usr/lib/python3/dist-packages/odoo/addons/web/__manifest__.py'
with open(path) as f:
    src = f.read()
marker = "'web/static/src/scss/pre_variables.scss',  # scss-fix"
if marker in src:
    print('manifest: ya parcheado, sin cambios')
    sys.exit(0)
old = ("'web._assets_frontend_helpers': [\n"
       "            'web/static/src/scss/bootstrap_overridden_frontend.scss',")
new = ("'web._assets_frontend_helpers': [\n"
       "            'web/static/src/scss/pre_variables.scss',  # scss-fix\n"
       "            'web/static/src/scss/bootstrap_overridden_frontend.scss',")
if old not in src:
    print('manifest: patron no encontrado (version distinta), sin cambios')
    sys.exit(0)
with open(path, 'w') as f:
    f.write(src.replace(old, new, 1))
print('manifest: parcheado OK')
PYEOF
# ─────────────────────────────────────────────────────────────────────────────

USER odoo
