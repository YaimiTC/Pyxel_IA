"""Renderiza una pagina web y guarda un screenshot, usando el Google Chrome del
sistema (Playwright channel='chrome'). No requiere descargar Chromium.

Uso:
    python scripts/web_shot.py <url-o-ruta> [salida.png] [--login] [--full]
Ejemplos:
    python scripts/web_shot.py https://example.com C:\\tmp\\shot.png
    python scripts/web_shot.py /my/verification/4 C:\\tmp\\shot.png   # portal Odoo (login auto)
    python scripts/web_shot.py /web C:\\tmp\\back.png --admin          # backend Odoo (admin)
"""
import sys

from playwright.sync_api import sync_playwright

BASE = "http://localhost:8069"
PORTAL_LOGIN, PORTAL_PWD = "cliente@demo.cu", "cliente123"
ADMIN_LOGIN, ADMIN_PWD = "admin", "admin"

args = [a for a in sys.argv[1:] if not a.startswith("--")]
flags = [a for a in sys.argv[1:] if a.startswith("--")]
target = args[0] if args else "/my/verification/4"
out = args[1] if len(args) > 1 else r"C:\Proyectos\images\_shot.png"

is_url = target.startswith("http")
url = target if is_url else BASE + target
use_admin = "--admin" in flags
do_login = (not is_url) or use_admin or ("--login" in flags)
login = ADMIN_LOGIN if use_admin else PORTAL_LOGIN
pwd = ADMIN_PWD if use_admin else PORTAL_PWD


def make_browser(p):
    try:
        return p.chromium.launch(channel="chrome", headless=True)
    except Exception:
        return p.chromium.launch(headless=True)  # Chromium propio, si existiera


with sync_playwright() as p:
    browser = make_browser(p)
    page = browser.new_page(viewport={"width": 1440, "height": 1000})
    if do_login:
        page.goto(BASE + "/web/login", wait_until="domcontentloaded")
        try:
            page.fill("input[name='login']", login)
            page.fill("input[name='password']", pwd)
            page.click("button[type='submit']")
            page.wait_for_load_state("networkidle")
        except Exception:
            pass
    page.goto(url, wait_until="networkidle")
    page.wait_for_timeout(1000)
    page.screenshot(path=out, full_page=True)
    browser.close()

print("OK ->", out)
