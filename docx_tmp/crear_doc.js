const { Document, Packer, Paragraph, TextRun, Table, TableRow, TableCell,
        BorderStyle, WidthType, ShadingType, HeadingLevel } = require('docx');
const fs = require('fs');

const border = { style: BorderStyle.SINGLE, size: 1, color: 'CCCCCC' };
const borders = { top: border, bottom: border, left: border, right: border };

const ESTADO = {
  OK:      { text: 'OK',      color: '2E7D32' },
  ERR404:  { text: '404',     color: 'C62828' },
  LOGOUT:  { text: 'Logout',  color: '757575' },
  EXTERNO: { text: 'Externo', color: '1565C0' },
};

// ─── LISTA 1: NO AUTENTICADO ────────────────────────────────────────────────
const anonLinks = [
  { url: '/',                                         desc: 'Inicio',          ubicacion: 'Nav',                  estado: 'OK' },
  { url: '/business-register?type=import',            desc: 'Importaciones',   ubicacion: 'Nav',                  estado: 'OK' },
  { url: '/business-register?type=accreditation',     desc: 'Acreditacion',    ubicacion: 'Nav',                  estado: 'OK' },
  { url: '/shop',                                     desc: 'Tienda',          ubicacion: 'Nav',                  estado: 'OK' },
  { url: '/contactus',                                desc: 'Contactenos',     ubicacion: 'Nav',                  estado: 'OK' },
  { url: '/web/login',                                desc: 'Iniciar sesion',  ubicacion: 'Nav',                  estado: 'OK' },
  { url: '/business-register?type=import',            desc: 'Importaciones',   ubicacion: 'Hero - tarjeta 1',     estado: 'OK' },
  { url: '/business-register?type=import',            desc: 'Importaciones',   ubicacion: 'Hero - tarjeta 2',     estado: 'OK' },
  { url: '/business-register?type=accreditation',     desc: 'Acreditacion',    ubicacion: 'Hero - tarjeta',       estado: 'OK' },
  { url: '/business-register?type=import',            desc: 'Importaciones',   ubicacion: 'Footer - Servicios',   estado: 'OK' },
  { url: '/business-register?type=accreditation',     desc: 'Acreditacion',    ubicacion: 'Footer - Servicios',   estado: 'OK' },
  { url: '/cookie-policy',                            desc: 'Politica cookies',ubicacion: 'Cookie banner',        estado: 'OK' },
  { url: 'https://www.facebook.com/PyxelSolutions/',  desc: 'Facebook',        ubicacion: 'Footer - Siguenos',    estado: 'EXTERNO' },
  { url: 'https://www.instagram.com/pyxelsolutions/', desc: 'Instagram',       ubicacion: 'Footer - Siguenos',    estado: 'EXTERNO' },
  { url: 'https://cu.linkedin.com/company/pyxel-solutions', desc: 'LinkedIn', ubicacion: 'Footer - Siguenos',    estado: 'EXTERNO' },
];

// ─── LISTA 2: AUTENTICADO NO ACREDITADO ─────────────────────────────────────
const authLinks = [
  // Homepage
  { url: '/my/home',                                  desc: 'Mi cuenta',       ubicacion: 'Dropdown top bar',             estado: 'OK',     pagina: '/' },
  { url: '/web/session/logout?redirect=/',            desc: 'Cerrar sesion',   ubicacion: 'Dropdown top bar',             estado: 'LOGOUT', pagina: '/' },
  { url: '/',                                         desc: 'Inicio',          ubicacion: 'Nav',                          estado: 'OK',     pagina: '/' },
  { url: '/business-register?type=import',            desc: 'Importaciones',   ubicacion: 'Nav',                          estado: 'OK',     pagina: '/' },
  { url: '/business-register?type=accreditation',     desc: 'Acreditacion',    ubicacion: 'Nav',                          estado: 'OK',     pagina: '/' },
  { url: '/shop',                                     desc: 'Tienda',          ubicacion: 'Nav',                          estado: 'OK',     pagina: '/' },
  { url: '/contactus',                                desc: 'Contactenos',     ubicacion: 'Nav',                          estado: 'OK',     pagina: '/' },
  { url: '/business-register?type=import',            desc: 'Importaciones',   ubicacion: 'Hero - tarjeta 1',             estado: 'OK',     pagina: '/' },
  { url: '/business-register?type=import',            desc: 'Importaciones',   ubicacion: 'Hero - tarjeta 2',             estado: 'OK',     pagina: '/' },
  { url: '/business-register?type=accreditation',     desc: 'Acreditacion',    ubicacion: 'Hero - tarjeta',               estado: 'OK',     pagina: '/' },
  { url: '/business-register?type=import',            desc: 'Importaciones',   ubicacion: 'Footer - Servicios',           estado: 'OK',     pagina: '/' },
  { url: '/business-register?type=accreditation',     desc: 'Acreditacion',    ubicacion: 'Footer - Servicios',           estado: 'OK',     pagina: '/' },
  { url: '/cookie-policy',                            desc: 'Politica cookies',ubicacion: 'Cookie banner',                estado: 'OK',     pagina: '/' },
  { url: 'https://www.facebook.com/PyxelSolutions/',  desc: 'Facebook',        ubicacion: 'Footer - Siguenos',            estado: 'EXTERNO',pagina: '/' },
  { url: 'https://www.instagram.com/pyxelsolutions/', desc: 'Instagram',       ubicacion: 'Footer - Siguenos',            estado: 'EXTERNO',pagina: '/' },
  { url: 'https://cu.linkedin.com/company/pyxel-solutions', desc: 'LinkedIn', ubicacion: 'Footer - Siguenos',            estado: 'EXTERNO',pagina: '/' },
  // /my/home
  { url: '/',                                         desc: 'Inicio',          ubicacion: 'Breadcrumb',                   estado: 'OK',     pagina: '/my/home' },
  { url: '/my/home',                                  desc: 'Mi Cuenta',       ubicacion: 'Breadcrumb',                   estado: 'OK',     pagina: '/my/home' },
  { url: '/my/home',                                  desc: 'Mi cuenta',       ubicacion: 'Dropdown top bar',             estado: 'OK',     pagina: '/my/home' },
  { url: '/web/session/logout?redirect=/',            desc: 'Cerrar sesion',   ubicacion: 'Dropdown top bar',             estado: 'LOGOUT', pagina: '/my/home' },
  { url: '/my/quotes',                                desc: 'Pedidos',         ubicacion: 'Widget card',                  estado: 'OK',     pagina: '/my/home' },
  { url: '/my/orders',                                desc: 'Solicitudes',     ubicacion: 'Widget card',                  estado: 'OK',     pagina: '/my/home' },
  { url: '/my/invoices',                              desc: 'Facturas',        ubicacion: 'Widget card',                  estado: 'OK',     pagina: '/my/home' },
  { url: '/model/imports',                            desc: 'Importaciones',   ubicacion: 'Widget card',                  estado: 'OK',     pagina: '/my/home' },
  { url: '/my/account',                               desc: 'Editar informacion',ubicacion:'Panel der. - desktop',         estado: 'OK',     pagina: '/my/home' },
  { url: '/my/quotes',                                desc: 'Historial pedidos',ubicacion: 'Panel der. - desktop',        estado: 'OK',     pagina: '/my/home' },
  { url: '/my/notifications',                         desc: 'Notificaciones',  ubicacion: 'Panel der. - desktop',         estado: 'ERR404', pagina: '/my/home' },
  { url: '/web/session/logout',                       desc: 'Salir',           ubicacion: 'Panel der. - desktop',         estado: 'LOGOUT', pagina: '/my/home' },
  { url: '/my/account',                               desc: 'Editar informacion',ubicacion:'Panel der. - movil',           estado: 'OK',     pagina: '/my/home' },
  { url: '/my/quotes',                                desc: 'Historial pedidos',ubicacion: 'Panel der. - movil',          estado: 'OK',     pagina: '/my/home' },
  { url: '/my/notifications',                         desc: 'Notificaciones',  ubicacion: 'Panel der. - movil',           estado: 'ERR404', pagina: '/my/home' },
  { url: '/web/session/logout',                       desc: 'Salir',           ubicacion: 'Panel der. - movil',           estado: 'LOGOUT', pagina: '/my/home' },
  { url: '/business-register?type=import',            desc: 'Importacion',     ubicacion: 'Footer - Servicios',           estado: 'OK',     pagina: '/my/home' },
  { url: '/business-register?type=accreditation',     desc: 'Acreditacion',    ubicacion: 'Footer - Servicios',           estado: 'OK',     pagina: '/my/home' },
  { url: '/cookie-policy',                            desc: 'Politica cookies',ubicacion: 'Cookie banner',                estado: 'OK',     pagina: '/my/home' },
  { url: 'https://www.facebook.com/PyxelSolutions/',  desc: 'Facebook',        ubicacion: 'Footer - Siguenos',            estado: 'EXTERNO',pagina: '/my/home' },
  { url: 'https://www.instagram.com/pyxelsolutions/', desc: 'Instagram',       ubicacion: 'Footer - Siguenos',            estado: 'EXTERNO',pagina: '/my/home' },
  { url: 'https://cu.linkedin.com/company/pyxel-solutions', desc: 'LinkedIn', ubicacion: 'Footer - Siguenos',            estado: 'EXTERNO',pagina: '/my/home' },
];

// ─── HELPERS ────────────────────────────────────────────────────────────────
function makeHeader(cols) {
  return new TableRow({
    children: cols.map(([t, w]) => new TableCell({
      borders,
      width: { size: w, type: WidthType.DXA },
      shading: { fill: '2E75B6', type: ShadingType.CLEAR },
      margins: { top: 80, bottom: 80, left: 120, right: 120 },
      children: [new Paragraph({ children: [new TextRun({ text: t, bold: true, color: 'FFFFFF', font: 'Arial', size: 18 })] })]
    }))
  });
}

function makeRow(cells, idx) {
  const fill = idx % 2 === 0 ? 'F2F7FB' : 'FFFFFF';
  return new TableRow({
    children: cells.map(({ t, w, color, mono }) => new TableCell({
      borders,
      width: { size: w, type: WidthType.DXA },
      shading: { fill, type: ShadingType.CLEAR },
      margins: { top: 60, bottom: 60, left: 120, right: 120 },
      children: [new Paragraph({ children: [new TextRun({ text: t, font: mono ? 'Courier New' : 'Arial', size: 16, color: color || '222222' })] })]
    }))
  });
}

function makeTable(links, hasPagina) {
  const cols = hasPagina
    ? [['URL / Enlace', 3200], ['Descripcion', 1800], ['Ubicacion', 2200], ['Pagina', 1000], ['Estado', 720]]
    : [['URL / Enlace', 3600], ['Descripcion', 1900], ['Ubicacion', 2500], ['Estado', 760]];
  const colWidths = cols.map(c => c[1]);

  const hdr = makeHeader(cols);
  const rows = links.map((l, i) => {
    const est = ESTADO[l.estado];
    const cells = hasPagina
      ? [
          { t: l.url,      w: colWidths[0], mono: true },
          { t: l.desc,     w: colWidths[1] },
          { t: l.ubicacion,w: colWidths[2] },
          { t: l.pagina,   w: colWidths[3], mono: true, color: '555555' },
          { t: est.text,   w: colWidths[4], color: est.color },
        ]
      : [
          { t: l.url,      w: colWidths[0], mono: true },
          { t: l.desc,     w: colWidths[1] },
          { t: l.ubicacion,w: colWidths[2] },
          { t: est.text,   w: colWidths[3], color: est.color },
        ];
    return makeRow(cells, i);
  });

  return new Table({
    width: { size: 8920, type: WidthType.DXA },
    columnWidths: colWidths,
    rows: [hdr, ...rows]
  });
}

function heading1(text) {
  return new Paragraph({
    heading: HeadingLevel.HEADING_1,
    children: [new TextRun({ text, font: 'Arial', size: 28, bold: true, color: '1F3864' })]
  });
}

function heading2(text) {
  return new Paragraph({
    spacing: { before: 200, after: 100 },
    children: [new TextRun({ text, font: 'Arial', size: 22, bold: true, color: '2E75B6' })]
  });
}

function subtitle(text) {
  return new Paragraph({
    spacing: { after: 160 },
    children: [new TextRun({ text, font: 'Arial', size: 18, color: '555555', italics: true })]
  });
}

function spacer() {
  return new Paragraph({ children: [new TextRun('')] });
}

// ─── TABLA COMPARATIVA CLIENTE POR ESTADOS ───────────────────────────────────
const estadosHdr = [
  ['URL / Enlace', 3400],
  ['Sin solicitud', 1300],
  ['Solicitud', 1300],
  ['Sol. en proceso', 1400],
  ['Aprobado cartera', 1400],
  ['Ganado', 1060],
];
const estColWidths = estadosHdr.map(c => c[1]);

const S  = { text: '200 OK',   color: '2E7D32' };
const R  = { text: '303 →thanks', color: 'E65100' };
const RI = { text: '303 →login', color: 'E65100' };
const N  = { text: '404',      color: 'C62828' };
const L  = { text: 'logout',   color: '757575' };
const NE = { text: '—',        color: 'AAAAAA' };

const estadosRows = [
  // [url, sinSolicitud, solicitud, solEnProceso, aprobadoCartera, ganado]
  // — enlaces que cambian entre estados —
  ['/business-register?type=accreditation', S,  R,  R,  R,  R ],
  ['/business-register?type=import',        S,  R,  R,  S,  S ],
  ['/business-register-thanks',             NE, S,  S,  NE, NE],
  ['/descargar/load_products',              NE, NE, NE, S,  S ],
  ['/descargar/solicitud',                  NE, NE, NE, S,  S ],
  ['/nomenclador?from=import_registration', NE, NE, NE, S,  S ],
  // — enlaces estables en todos los estados —
  ['/',                                     S,  S,  S,  S,  S ],
  ['/contactus',                            S,  S,  S,  S,  S ],
  ['/cookie-policy',                        S,  S,  S,  S,  S ],
  ['/model/imports',                        S,  S,  S,  S,  S ],
  ['/my/',                                  S,  S,  S,  S,  S ],
  ['/my/account',                           S,  S,  S,  S,  S ],
  ['/my/home',                              S,  S,  S,  S,  S ],
  ['/my/invoices',                          S,  S,  S,  S,  S ],
  ['/my/invoices?filterby=all',             S,  S,  S,  S,  S ],
  ['/my/invoices?filterby=bills',           S,  S,  S,  S,  S ],
  ['/my/invoices?filterby=invoices',        S,  S,  S,  S,  S ],
  ['/my/invoices?sortby=date',              S,  S,  S,  S,  S ],
  ['/my/invoices?sortby=duedate',           S,  S,  S,  S,  S ],
  ['/my/invoices?sortby=name',              S,  S,  S,  S,  S ],
  ['/my/invoices?sortby=state',             S,  S,  S,  S,  S ],
  ['/my/notifications',                     N,  N,  N,  N,  N ],
  ['/my/orders',                            S,  S,  S,  S,  S ],
  ['/my/orders?sortby=date',                S,  S,  S,  S,  S ],
  ['/my/orders?sortby=name',                S,  S,  S,  S,  S ],
  ['/my/orders?sortby=stage',               S,  S,  S,  S,  S ],
  ['/my/quotes',                            S,  S,  S,  S,  S ],
  ['/my/quotes?sortby=date',                S,  S,  S,  S,  S ],
  ['/my/quotes?sortby=name',                S,  S,  S,  S,  S ],
  ['/my/quotes?sortby=stage',               S,  S,  S,  S,  S ],
  ['/shop',                                 S,  S,  S,  S,  S ],
  ['/shop/change_pricelist/1',              S,  S,  S,  S,  S ],
  ['/shop?order=create_date+desc',          S,  S,  S,  S,  S ],
  ['/shop?order=list_price+asc',            S,  S,  S,  S,  S ],
  ['/shop?order=list_price+desc',           S,  S,  S,  S,  S ],
  ['/shop?order=name+asc',                  S,  S,  S,  S,  S ],
  ['/shop?order=website_sequence+asc',      S,  S,  S,  S,  S ],
  ['/web/session/logout',                   L,  L,  L,  L,  L ],
  ['/web/session/logout?redirect=/',        L,  L,  L,  L,  L ],
];

function makeEstadosTable() {
  const hdr = new TableRow({
    children: estadosHdr.map(([t, w]) => new TableCell({
      borders,
      width: { size: w, type: WidthType.DXA },
      shading: { fill: '1F3864', type: ShadingType.CLEAR },
      margins: { top: 80, bottom: 80, left: 120, right: 120 },
      children: [new Paragraph({ children: [new TextRun({ text: t, bold: true, color: 'FFFFFF', font: 'Arial', size: 16 })] })]
    }))
  });

  const rows = estadosRows.map((row, i) => {
    const [url, ...celdas] = row;
    const fill = i % 2 === 0 ? 'F2F7FB' : 'FFFFFF';
    return new TableRow({
      children: [
        new TableCell({
          borders, width: { size: estColWidths[0], type: WidthType.DXA },
          shading: { fill, type: ShadingType.CLEAR },
          margins: { top: 60, bottom: 60, left: 120, right: 120 },
          children: [new Paragraph({ children: [new TextRun({ text: url, font: 'Courier New', size: 15, color: '222222' })] })]
        }),
        ...celdas.map((c, ci) => new TableCell({
          borders, width: { size: estColWidths[ci + 1], type: WidthType.DXA },
          shading: { fill, type: ShadingType.CLEAR },
          margins: { top: 60, bottom: 60, left: 120, right: 120 },
          children: [new Paragraph({ children: [new TextRun({ text: c.text, font: 'Arial', size: 15, bold: c.text !== '—', color: c.color })] })]
        }))
      ]
    });
  });

  return new Table({
    width: { size: 9860, type: WidthType.DXA },
    columnWidths: estColWidths,
    rows: [hdr, ...rows]
  });
}

// ─── TABLA COMPARATIVA PROVEEDOR POR ESTADOS ─────────────────────────────────
const RB = { text: '200 bloqueado', color: 'B71C1C' }; // 200 pero con mensaje "No eres Cliente nacional"

const provEstadosRows = [
  // — enlaces que cambian entre estados —
  ['/business-register?type=accreditation', S,  R,  R,  R,  R ],
  ['/business-register?type=import',        RB, RB, RB, RB, RB],
  ['/business-register-thanks',             NE, S,  S,  NE, NE],
  ['/descargar/cuban_partner',              S,  NE, NE, NE, NE],
  ['/descargar/ficha_cliente_estatal',      S,  NE, NE, NE, NE],
  ['/descargar/ficha_cliente_fgne_tcp',     S,  NE, NE, NE, NE],
  ['/descargar/perfil_proveedor',           S,  NE, NE, NE, NE],
  // — enlaces estables en todos los estados —
  ['/',                                     S,  S,  S,  S,  S ],
  ['/contactus',                            S,  S,  S,  S,  S ],
  ['/cookie-policy',                        S,  S,  S,  S,  S ],
  ['/model/imports',                        S,  S,  S,  S,  S ],
  ['/my/',                                  S,  S,  S,  S,  S ],
  ['/my/account',                           S,  S,  S,  S,  S ],
  ['/my/home',                              S,  S,  S,  S,  S ],
  ['/my/invoices',                          S,  S,  S,  S,  S ],
  ['/my/invoices?filterby=all',             S,  S,  S,  S,  S ],
  ['/my/invoices?filterby=bills',           S,  S,  S,  S,  S ],
  ['/my/invoices?filterby=invoices',        S,  S,  S,  S,  S ],
  ['/my/invoices?sortby=date',              S,  S,  S,  S,  S ],
  ['/my/invoices?sortby=duedate',           S,  S,  S,  S,  S ],
  ['/my/invoices?sortby=name',              S,  S,  S,  S,  S ],
  ['/my/invoices?sortby=state',             S,  S,  S,  S,  S ],
  ['/my/notifications',                     N,  N,  N,  N,  N ],
  ['/my/orders',                            S,  S,  S,  S,  S ],
  ['/my/orders?sortby=date',                S,  S,  S,  S,  S ],
  ['/my/orders?sortby=name',                S,  S,  S,  S,  S ],
  ['/my/orders?sortby=stage',               S,  S,  S,  S,  S ],
  ['/my/quotes',                            S,  S,  S,  S,  S ],
  ['/my/quotes?sortby=date',                S,  S,  S,  S,  S ],
  ['/my/quotes?sortby=name',                S,  S,  S,  S,  S ],
  ['/my/quotes?sortby=stage',               S,  S,  S,  S,  S ],
  ['/shop',                                 S,  S,  S,  S,  S ],
  ['/shop/change_pricelist/1',              S,  S,  S,  S,  S ],
  ['/shop?order=create_date+desc',          S,  S,  S,  S,  S ],
  ['/shop?order=list_price+asc',            S,  S,  S,  S,  S ],
  ['/shop?order=list_price+desc',           S,  S,  S,  S,  S ],
  ['/shop?order=name+asc',                  S,  S,  S,  S,  S ],
  ['/shop?order=website_sequence+asc',      S,  S,  S,  S,  S ],
  ['/web/session/logout',                   L,  L,  L,  L,  L ],
  ['/web/session/logout?redirect=/',        L,  L,  L,  L,  L ],
];

function makeProvEstadosTable() {
  const hdr = new TableRow({
    children: estadosHdr.map(([t, w]) => new TableCell({
      borders,
      width: { size: w, type: WidthType.DXA },
      shading: { fill: '4A235A', type: ShadingType.CLEAR },
      margins: { top: 80, bottom: 80, left: 120, right: 120 },
      children: [new Paragraph({ children: [new TextRun({ text: t, bold: true, color: 'FFFFFF', font: 'Arial', size: 16 })] })]
    }))
  });
  const rows = provEstadosRows.map((row, i) => {
    const [url, ...celdas] = row;
    const fill = i % 2 === 0 ? 'F9F0FF' : 'FFFFFF';
    return new TableRow({
      children: [
        new TableCell({
          borders, width: { size: estColWidths[0], type: WidthType.DXA },
          shading: { fill, type: ShadingType.CLEAR },
          margins: { top: 60, bottom: 60, left: 120, right: 120 },
          children: [new Paragraph({ children: [new TextRun({ text: url, font: 'Courier New', size: 15, color: '222222' })] })]
        }),
        ...celdas.map((c, ci) => new TableCell({
          borders, width: { size: estColWidths[ci + 1], type: WidthType.DXA },
          shading: { fill, type: ShadingType.CLEAR },
          margins: { top: 60, bottom: 60, left: 120, right: 120 },
          children: [new Paragraph({ children: [new TextRun({ text: c.text, font: 'Arial', size: 15, bold: c.text !== '—', color: c.color })] })]
        }))
      ]
    });
  });
  return new Table({ width: { size: 9860, type: WidthType.DXA }, columnWidths: estColWidths, rows: [hdr, ...rows] });
}

// ─── DOCUMENT ───────────────────────────────────────────────────────────────
const doc = new Document({
  sections: [{
    properties: {
      page: {
        size: { width: 15840, height: 12240 },  // Letter landscape
        margin: { top: 1080, right: 1080, bottom: 1080, left: 1080 }
      }
    },
    children: [
      heading1('Analisis de Enlaces del Frontend - localhost:8069'),
      subtitle('Fecha: 13/06/2026  |  Sitio: erp_odin  |  Cubre: CLIENTE y PROVEEDOR (portal)'),
      subtitle('Estado: OK = 200, 404 = Not Found, Logout = no testeable, Externo = fuera del sitio'),
      spacer(),

      heading2('1. Usuario No Autenticado'),
      subtitle(`${anonLinks.length} enlaces encontrados en la pagina principal`),
      makeTable(anonLinks, false),
      spacer(),

      heading2('2. Usuario Autenticado No Acreditado  (yaimitccc@gmail.com)'),
      subtitle(`${authLinks.length} enlaces encontrados en / y /my/home`),
      makeTable(authLinks, true),
      spacer(),

      new Paragraph({
        children: [new TextRun({
          text: 'Conclusion: unico enlace con error es /my/notifications (404) en el panel de Mi Cuenta.',
          font: 'Arial', size: 18, italics: true, color: 'C62828'
        })]
      }),
      spacer(),

      heading2('3. CLIENTE — Comparativa de enlaces por estado de acreditacion'),
      subtitle('200 OK = accesible | 303 = redirige | 404 = error | logout = no testeable | — = no existe en este estado'),
      subtitle('35 enlaces base → 34 en Solicitud/En proceso → 38 en Aprobado cartera/Ganado'),
      makeEstadosTable(),
      spacer(),
      new Paragraph({
        children: [new TextRun({
          text: 'Cliente: el cambio clave ocurre en APROBADO EN CARTERA — se habilita el formulario de importacion y aparecen 3 nuevos enlaces (/descargar/load_products, /descargar/solicitud, /nomenclador).',
          font: 'Arial', size: 18, italics: true, color: '1F3864'
        })]
      }),
      spacer(),

      heading2('4. PROVEEDOR — Comparativa de enlaces por estado de acreditacion'),
      subtitle('200 OK = accesible | 200 bloqueado = carga pero muestra "No eres Cliente nacional" | 303 = redirige | — = no existe'),
      subtitle('35 enlaces base → 36 en Solicitud/En proceso → 35 en Aprobado cartera/Ganado'),
      subtitle('Regla: el proveedor NUNCA accede al formulario de importacion en ningun estado.'),
      makeProvEstadosTable(),
      spacer(),
      new Paragraph({
        children: [new TextRun({
          text: 'Proveedor: ningun estado desbloquea enlaces nuevos. Las fichas de descarga (/descargar/cuban_partner, etc.) solo aparecen en Sin solicitud (dentro del formulario de acreditacion accesible) y desaparecen al enviar la solicitud.',
          font: 'Arial', size: 18, italics: true, color: '4A235A'
        })]
      }),
    ]
  }]
});

Packer.toBuffer(doc).then(buf => {
  fs.writeFileSync('D:/trabajo/Pyxel/IA/enlaces_frontend_anonimo.docx', buf);
  console.log('OK');
});
