---
name: identidad-web-enetradex
description: Identidad visual y estructura del home de ENETRADEX (mockup Home.png) para el rediseño web
metadata: 
  node_type: memory
  type: project
  originSessionId: 4c1918a5-33b6-4251-837d-dc0bfe097d44
---

Mockup del home en `C:\odoo_enetradex\images\Home.png` (1024x1536, hecho con ChatGPT). Marca = **ENETRADEX** (coincide con el prefijo de módulos). Sector: importación/comercio de combustibles y energía. Reemplaza la identidad agro de Agrimpex en `pyxel_enetradex_custom_web_theme`. Bandas en `images\_bands\`.

**Paleta:** azul royal primario `#0f44ce`–`#0d3cc9` (botones, navbar, acentos), navy muy oscuro `#03132e` (footer y overlays del hero), blanco para cards, hay un banner CTA verde y un acento cian para palabras destacadas ("oportunidades"). Tipografía sans moderna.

**Estructura del home (de arriba a abajo):**
- Topbar: "Atención Comercial · +1 (305) 123-4567" · "Rastrear pedido" | "Noticias" · selector idioma "ES".
- Navbar: logo ENETRADEX (icono hexagonal/molécula) + tagline "Plataforma de importación y comercio online" · buscador "Buscar productos, proveedores, destinos…" · iconos "MI ENETRADEX" + wishlist + carrito + botón "Acreditarme".
- Menú: Inicio · Importar · Marketplace ▾ · Combustibles ▾ · Trading · Proveedores · Servicios ▾ · Contacto.
- Hero: "Conectamos energía con **oportunidades**" + sub "Plataforma de importación de combustibles y comercialización de productos energéticos." + CTAs "Acreditarme" / "Explorar Marketplace" sobre foto puerto/buque tanque. Fila de 4 features: Combustibles de calidad · Red global confiable · Operaciones seguras · Información en tiempo real.
- Dos cards: **IMPORTAR** ("Importación integral de combustibles y derivados energéticos." → Importar ahora) y **MARKETPLACE ENERGÉTICO** ("Compra productos y suministros para el sector energético." → Comprar productos).
- Banner CTA: "Comience a operar con ENETRADEX… → Acreditarme ahora".
- NUESTROS SERVICIOS (5): Importación · Trading · Marketplace energético · Logística internacional · Inteligencia comercial.
- PRODUCTOS MÁS VENDIDOS (6 cards): GASOIL EN590 · GASOLINA RON 93 · FUEL OIL 180 CST · JET FUEL A1 · LUBRICANTES · ADITIVOS (botón "Ver producto"). + "Ver todos".
- CÓMO FUNCIONA ENETRADEX (4 pasos): Solicitud · Cotización · Importación · Entrega.
- ACTUALIDAD DEL MERCADOS (4 noticias con fecha).
- Fila de confianza: Red Global · Transparencia · Tecnología · Seguridad.
- Footer navy: logo + "Conectamos energía con oportunidades" + redes; columnas PLATAFORMA / EMPRESA / RECURSOS / CONTÁCTANOS.

**⚠️ Datos placeholder del mockup (confirmar reales con ENETEC):** contacto Miami/+1 (305)/info@enetradex.com NO es real (ENETEC es de La Habana, Cuba — ver topbar real direccion@enetec.telmark.com.cu, etc. en [[requisitos-enetec-cliente]] / [[proyecto-enetec-odin]]). Productos/precios/noticias son de muestra. "PRODUCTOS MÁS VENDIDOS" arrancaría como cards estáticas (como hizo Agrimpex) y luego dinámico (product.template is_published).

**IMPLEMENTADO (2026-06-13) — home + navbar + footer:** rediseño aplicado en `pyxel_enetradex_custom_web_theme` y funcionando en http://localhost:8469.
- Paleta recoloreada verde→azul vía variables `$ag-*` y `$cx-*` en `agrimpex_redesign.scss` / `agrimpex_theme.scss` + barrido de hex verdes hardcodeados → azul. `.ag-btn-primary` ahora azul royal con texto blanco.
- `home.xml` reescrito a combustibles (hero, dual IMPORTAR/MARKETPLACE, banner CTA, 5 servicios, 6 productos combustible, 4 pasos "Cómo funciona", 4 noticias de mercado). Clases nuevas con estilos al final del redesign.scss (`.ag-hero-feats`, `.ag-cta-band*`, `.ag-steps/.ag-step*`, `.ag-news-4`).
- `navbar.xml`: logo `en_logo.png`, menú Inicio/Importar/Marketplace/Combustibles/Trading/Proveedores/Servicios/Contacto, "Mi ENETRADEX", contacto real.
- `footer.xml`: navy, 4 columnas (Plataforma/Empresa/Recursos/Contáctanos) + marca, datos reales ENETEC (Calle 30 Nº512 Miramar, +53 5280 7765, comercial@enetec.telmark.com.cu).
- Assets recortados del mockup en `static/src/img/`: `en_hero.jpg`, `en_card_import.jpg`, `en_card_market.jpg`, `en_prod_1..6.jpg`, `en_news_1..4.jpg`, `en_logo.png`.

**Afinado visual (2026-06-13):** hero rediseñado a overlay azul oscuro (`linear-gradient` navy izq) + texto BLANCO + acento cian "oportunidades" + features blancas (legible sobre cualquier foto). Botón `.ag-btn-primary` azul royal. Footer navy (quitado `#021f10` verde). Barrido total de verdes hardcodeados residuales (`#073d24`, `#4ade80`, tintes verdosos) → azul/neutro en ambos SCSS. Verificado con preview (proxy 8470→8469, ver `.claude/preview_proxy.py` + `launch.json`).

**Imágenes REALES del usuario ya integradas** (generadas con ChatGPT, en `images\`): hero `banner (2).png`→`en_hero.jpg` (buque tanque al atardecer), `import.png`→`en_card_import.jpg` (portacontenedores), `imgtienda.png`→`en_card_market.jpg` (bidones GASOIL/LUBRICANTE). Se optimizan con PIL (resize+jpg q88) y se colocan en static/src/img sobreescribiendo los recortes.

**Revisión de fidelidad vs mockup (2026-06-13):** hero cambiado a tratamiento del MOCKUP (gradiente claro a la izquierda + título NAVY + acento azul "oportunidades" + features con icono azul y texto oscuro), no overlay oscuro. Añadida la **fila de confianza** que faltaba (Red global / Transparencia / Tecnología / Seguridad, clases `.ag-trust*`). **Logo real** del usuario integrado: `images/logo.png` (1536×1024) recortado a la banda del logo (aspecto ~3.6) → `en_logo.png` para la navbar (altura 56px). Footer sigue con wordmark blanco en texto. Iconos: TODOS renderizan vía FA4.7 de Odoo (ver [[optimizacion-rendimiento-web]]).

**Ajustes de maquetado (2026-06-13, 2ª ronda):** (1) Hero — el texto no se leía sobre la imagen oscura del atardecer; se reforzó el gradiente claro de la izquierda (`.ag-hero-banner::before`: blanco casi sólido 0–48% del ancho) para que el título navy + acento cian sean legibles. (2) "Nuestros Servicios" se veía descentrado porque `.ag-solutions` tenía `repeat(6,1fr)` con solo 5 servicios → cambiado a `repeat(5,1fr)` (+ responsive 3/2). (3) Las imágenes de los bloques Importar/Marketplace se veían pegadas a la derecha (eran media card con `position:center` y las fotos tienen fondo claro a la izq) → ahora la imagen es **fondo completo de la card** (`.ag-dual-img` absolute inset:0, `background-position:right center`) con el texto sobre `.ag-dual-card::after` (degradado blanco izq), como el mockup.

**Rediseño página ACREDITACIÓN (2026-06-14, mockup `images/acreditacion (2).png`):** en `pyxel_enetradex_custom_web_theme/views/pages/accreditation.xml` + `accreditation.js` + SCSS, y `pyxel_enetradex_website` (sección de documentos). Estructura fiel al mockup: banner azul "Acreditación corporativa" + stepper (Registro/Revisión/Validación/Activación, iconos FA); ① "Tipo de entidad" = **5 tarjetas** `.en-typecard` (las 4 management types cliente: Pymes/Sucursal Extranjera/Estatal/CNA + Proveedor) con icono+descripción, cada una con `data-ct`(contact_type id) y `data-mt`(nombre gestión); el JS `AgrimpexTypeCards` fija ambos selects (espera async a que carguen las opciones de `#fgne_type`); ② "Información básica"; ③ "Documentación requerida" = **grid de tarjetas** `.en-doc-card` (28 docs en total entre los 5 sets `endoc_*`), cada una con botón "Subir documento" (label-for sobre input `.en-doc-input` oculto), se pone verde `.is-done` al subir; + "Documentación adicional (opcional)"; + barra `.en-helpbar` "¿Necesita ayuda?" (email/tel ENETEC). Se quitaron las secciones agro (Proceso/Beneficios/Testimonios/CTA "campo cubano"). Verificado server-side por curl autenticado (28 botones "Subir documento", 5 tarjetas, banner, help bar). Pendiente: verificación visual del usuario (el navegador headless del preview no mantiene sesión vía el proxy 8470 — limitación de tooling, el login real funciona).

**PENDIENTE web:** faltan imágenes del usuario para los **6 productos** (`prod_*.png`) y **4 noticias** (`news_*.png`) — siguen como recortes del mockup; y el **logo** limpio (`logo.png` transparente + `logo_white.png`/SVG) — sigue el recorte `en_logo.png`. Ver hoja `images\nuevas\_INSTRUCCIONES.md`. Páginas internas /about, /contactus, /shop, acreditación aún agro (rediseñar). Nombres SCSS aún `agrimpex_*.scss` (cosmético).
