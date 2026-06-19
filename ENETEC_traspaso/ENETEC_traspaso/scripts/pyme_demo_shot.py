"""Demo visual del expediente PYME: abre /pyme, sube los 5 PDFs reales por la UI,
valida cada uno y captura el checklist poblado + (opcional) la vista del revisor."""
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

BASE = "http://localhost:8069"
PDFS = {
    "registro_mercantil": r"C:\Proyectos\DocValidator\_pyme_eval\certifico de registro mercantil-20260616T183620Z-3-001\certifico de registro mercantil\Certific registro Mercantil_. (1).pdf",
    "escritura_notarial": r"C:\Proyectos\DocValidator\_pyme_eval\Escritura notarial-20260616T183622Z-3-001\Escritura notarial\EP 692 DEL 30 NOV 2022 (1).pdf",
    "identificacion_fiscal": r"C:\Proyectos\DocValidator\_pyme_eval\Identificación Fiscal-20260616T183623Z-3-001\Identificación Fiscal\identificacion fiscal pruebalo.pdf",
    "no_adeudo": r"C:\Proyectos\DocValidator\_pyme_eval\No Adeudo-20260616T183624Z-3-001\No Adeudo\2. No adeudo Lazaro.pdf",
    "contrato_cuentas": r"C:\Proyectos\DocValidator\_pyme_eval\Ctto de cuentas-20260616T183621Z-3-001\Ctto de cuentas\CONTRATO BANDEC CUENTA CORRIENTE CUP.pdf",
}
OUT = sys.argv[1] if len(sys.argv) > 1 else r"C:\Proyectos\images\_pyme_front.png"

with sync_playwright() as p:
    try:
        browser = p.chromium.launch(channel="chrome", headless=True)
    except Exception:
        browser = p.chromium.launch(headless=True)
    page = browser.new_page(viewport={"width": 1100, "height": 1200})
    page.goto(BASE + "/pyme?nuevo=1", wait_until="networkidle")
    for code, path in PDFS.items():
        if not Path(path).exists():
            print("FALTA:", path)
            continue
        card = page.query_selector(f".pycard[data-code='{code}']")
        card.query_selector("input.pyfile").set_input_files(path)
        card.query_selector("button.pybtn").click()
        # espera a que aparezca el informe de esa tarjeta
        try:
            page.wait_for_function(
                "(c)=>{var el=document.querySelector(\".pycard[data-code='\"+c+\"'] .pyreport\");return el&&el.style.display!=='none'&&el.innerHTML.trim().length>0;}",
                arg=code, timeout=90000,
            )
        except Exception:
            print("timeout informe:", code)
    page.wait_for_timeout(800)
    page.screenshot(path=OUT, full_page=True)
    print("OK ->", OUT)
    browser.close()
