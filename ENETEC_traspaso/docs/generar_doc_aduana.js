const {
  Document, Packer, Paragraph, TextRun, Table, TableRow, TableCell,
  Header, Footer, AlignmentType, HeadingLevel, BorderStyle, WidthType,
  ShadingType, VerticalAlign, PageNumber, LevelFormat, ExternalHyperlink,
} = require("docx");
const fs = require("fs");

// ── Colores corporativos ─────────────────────────────────────────────────────
const AZUL       = "1F4E79";
const AZUL_CLARO = "2E75B6";
const AZUL_FONDO = "D6E4F0";
const GRIS_FONDO = "F2F2F2";
const GRIS_LINEA = "BFBFBF";
const ROJO       = "C00000";
const VERDE      = "375623";
const NARANJA    = "C55A11";

// ── Helpers ──────────────────────────────────────────────────────────────────
const borde = (color = GRIS_LINEA) => ({ style: BorderStyle.SINGLE, size: 1, color });
const bordes = (color = GRIS_LINEA) => ({ top: borde(color), bottom: borde(color), left: borde(color), right: borde(color) });
const sinBorde = () => ({ style: BorderStyle.NONE, size: 0, color: "FFFFFF" });
const sinBordes = () => ({ top: sinBorde(), bottom: sinBorde(), left: sinBorde(), right: sinBorde() });

const parrafo = (texto, opciones = {}) => new Paragraph({
  children: [new TextRun({ text: texto, font: "Arial", size: 20, ...opciones })],
  spacing: { after: 120 },
});

const bullet = (texto, bold = false) => new Paragraph({
  numbering: { reference: "bullets", level: 0 },
  children: [new TextRun({ text: texto, font: "Arial", size: 20, bold })],
  spacing: { after: 80 },
});

const espacio = (pts = 160) => new Paragraph({ children: [], spacing: { after: pts } });

const filaCabecera = (textos, anchos) => new TableRow({
  tableHeader: true,
  children: textos.map((t, i) => new TableCell({
    borders: bordes(AZUL_CLARO),
    width: { size: anchos[i], type: WidthType.DXA },
    shading: { fill: AZUL, type: ShadingType.CLEAR },
    margins: { top: 80, bottom: 80, left: 120, right: 120 },
    children: [new Paragraph({
      children: [new TextRun({ text: t, font: "Arial", size: 20, bold: true, color: "FFFFFF" })],
    })],
  })),
});

const fila = (celdas, anchos, sombreado = false) => new TableRow({
  children: celdas.map((txt, i) => new TableCell({
    borders: bordes(GRIS_LINEA),
    width: { size: anchos[i], type: WidthType.DXA },
    shading: { fill: sombreado ? GRIS_FONDO : "FFFFFF", type: ShadingType.CLEAR },
    margins: { top: 80, bottom: 80, left: 120, right: 120 },
    verticalAlign: VerticalAlign.CENTER,
    children: [new Paragraph({
      children: [new TextRun({ text: txt, font: "Arial", size: 20 })],
    })],
  })),
});

// ── Tabla de preguntas por sección ───────────────────────────────────────────
const tablaPreguntas = (preguntas) => {
  const anchos = [600, 8400];
  const rows = [filaCabecera(["#", "Pregunta"], anchos)];
  preguntas.forEach(([num, texto], idx) => {
    rows.push(fila([num, texto], anchos, idx % 2 === 1));
  });
  return new Table({
    width: { size: 9000, type: WidthType.DXA },
    columnWidths: anchos,
    rows,
  });
};

// ── Tabla del flujo de proceso ───────────────────────────────────────────────
const tablaFlujo = (pasos) => {
  const anchos = [600, 2400, 6000];
  const rows = [filaCabecera(["#", "Sistema", "Acción"], anchos)];
  pasos.forEach(([num, sistema, accion], idx) => {
    rows.push(new TableRow({
      children: [
        new TableCell({
          borders: bordes(GRIS_LINEA),
          width: { size: 600, type: WidthType.DXA },
          shading: { fill: idx % 2 === 1 ? GRIS_FONDO : "FFFFFF", type: ShadingType.CLEAR },
          margins: { top: 80, bottom: 80, left: 120, right: 120 },
          children: [new Paragraph({ children: [new TextRun({ text: num, font: "Arial", size: 20, bold: true, color: AZUL_CLARO })] })],
        }),
        new TableCell({
          borders: bordes(GRIS_LINEA),
          width: { size: 2400, type: WidthType.DXA },
          shading: { fill: idx % 2 === 1 ? GRIS_FONDO : "FFFFFF", type: ShadingType.CLEAR },
          margins: { top: 80, bottom: 80, left: 120, right: 120 },
          children: [new Paragraph({ children: [new TextRun({ text: sistema, font: "Arial", size: 20, bold: true })] })],
        }),
        new TableCell({
          borders: bordes(GRIS_LINEA),
          width: { size: 6000, type: WidthType.DXA },
          shading: { fill: idx % 2 === 1 ? GRIS_FONDO : "FFFFFF", type: ShadingType.CLEAR },
          margins: { top: 80, bottom: 80, left: 120, right: 120 },
          children: [new Paragraph({ children: [new TextRun({ text: accion, font: "Arial", size: 20 })] })],
        }),
      ],
    }));
  });
  return new Table({ width: { size: 9000, type: WidthType.DXA }, columnWidths: anchos, rows });
};

// ── Tabla resumen de realidades ──────────────────────────────────────────────
const tablaRealidades = () => {
  const anchos = [3000, 6000];
  return new Table({
    width: { size: 9000, type: WidthType.DXA },
    columnWidths: anchos,
    rows: [
      filaCabecera(["Realidad", "Implicacion para la plataforma"], anchos),
      new TableRow({ children: [
        new TableCell({ borders: bordes(), width: { size: 3000, type: WidthType.DXA }, shading: { fill: "FFF2CC", type: ShadingType.CLEAR }, margins: { top: 80, bottom: 80, left: 120, right: 120 },
          children: [new Paragraph({ children: [new TextRun({ text: "DM Plus genera fichero propietario", font: "Arial", size: 20, bold: true })] })] }),
        new TableCell({ borders: bordes(), width: { size: 6000, type: WidthType.DXA }, shading: { fill: "FFFFFF", type: ShadingType.CLEAR }, margins: { top: 80, bottom: 80, left: 120, right: 120 },
          children: [new Paragraph({ children: [new TextRun({ text: "Si se puede parsear, se extrae automaticamente DM#, contenedor, BL y valores. Si no, entrada manual.", font: "Arial", size: 20 })] })] }),
      ]}),
      new TableRow({ children: [
        new TableCell({ borders: bordes(), width: { size: 3000, type: WidthType.DXA }, shading: { fill: GRIS_FONDO, type: ShadingType.CLEAR }, margins: { top: 80, bottom: 80, left: 120, right: 120 },
          children: [new Paragraph({ children: [new TextRun({ text: "SUA y Portal del Mariel son portales web sin API publica", font: "Arial", size: 20, bold: true })] })] }),
        new TableCell({ borders: bordes(), width: { size: 6000, type: WidthType.DXA }, shading: { fill: GRIS_FONDO, type: ShadingType.CLEAR }, margins: { top: 80, bottom: 80, left: 120, right: 120 },
          children: [new Paragraph({ children: [new TextRun({ text: "La plataforma actua como tracker de estados con entrada manual asistida; no se puede automatizar directamente.", font: "Arial", size: 20 })] })] }),
      ]}),
      new TableRow({ children: [
        new TableCell({ borders: bordes(), width: { size: 3000, type: WidthType.DXA }, shading: { fill: "FFF2CC", type: ShadingType.CLEAR }, margins: { top: 80, bottom: 80, left: 120, right: 120 },
          children: [new Paragraph({ children: [new TextRun({ text: "VUA solo acepta subida manual de expediente", font: "Arial", size: 20, bold: true })] })] }),
        new TableCell({ borders: bordes(), width: { size: 6000, type: WidthType.DXA }, shading: { fill: "FFFFFF", type: ShadingType.CLEAR }, margins: { top: 80, bottom: 80, left: 120, right: 120 },
          children: [new Paragraph({ children: [new TextRun({ text: "La plataforma puede ensamblar y nombrar correctamente los archivos del expediente antes de que el tramitador los suba.", font: "Arial", size: 20 })] })] }),
      ]}),
    ],
  });
};

// ── DOCUMENTO ────────────────────────────────────────────────────────────────
const doc = new Document({
  numbering: {
    config: [
      { reference: "bullets", levels: [{ level: 0, format: LevelFormat.BULLET, text: "•", alignment: AlignmentType.LEFT,
          style: { paragraph: { indent: { left: 720, hanging: 360 } } } }] },
    ],
  },
  styles: {
    default: { document: { run: { font: "Arial", size: 20 } } },
    paragraphStyles: [
      { id: "Heading1", name: "Heading 1", basedOn: "Normal", next: "Normal", quickFormat: true,
        run: { size: 36, bold: true, font: "Arial", color: AZUL },
        paragraph: { spacing: { before: 320, after: 160 }, outlineLevel: 0,
          border: { bottom: { style: BorderStyle.SINGLE, size: 4, color: AZUL_CLARO, space: 4 } } } },
      { id: "Heading2", name: "Heading 2", basedOn: "Normal", next: "Normal", quickFormat: true,
        run: { size: 26, bold: true, font: "Arial", color: AZUL_CLARO },
        paragraph: { spacing: { before: 240, after: 120 }, outlineLevel: 1 } },
      { id: "Heading3", name: "Heading 3", basedOn: "Normal", next: "Normal", quickFormat: true,
        run: { size: 22, bold: true, font: "Arial", color: AZUL },
        paragraph: { spacing: { before: 160, after: 80 }, outlineLevel: 2 } },
    ],
  },
  sections: [{
    properties: {
      page: {
        size: { width: 12240, height: 15840 },
        margin: { top: 1080, right: 1080, bottom: 1080, left: 1080 },
      },
    },
    headers: {
      default: new Header({
        children: [new Paragraph({
          children: [
            new TextRun({ text: "ENETEC / ODIN 2.0  ", font: "Arial", size: 18, bold: true, color: AZUL }),
            new TextRun({ text: "Proceso de Despacho Aduanero  —  Documento de Trabajo", font: "Arial", size: 18, color: "888888" }),
          ],
          border: { bottom: { style: BorderStyle.SINGLE, size: 4, color: AZUL_CLARO, space: 4 } },
        })],
      }),
    },
    footers: {
      default: new Footer({
        children: [new Paragraph({
          children: [
            new TextRun({ text: "Confidencial  |  Junio 2026", font: "Arial", size: 16, color: "888888" }),
            new TextRun({ text: "          Pagina ", font: "Arial", size: 16, color: "888888" }),
            new TextRun({ children: [PageNumber.CURRENT], font: "Arial", size: 16, color: "888888" }),
          ],
          alignment: AlignmentType.RIGHT,
          border: { top: { style: BorderStyle.SINGLE, size: 4, color: AZUL_CLARO, space: 4 } },
        })],
      }),
    },
    children: [

      // ── PORTADA ─────────────────────────────────────────────────────────────
      new Paragraph({
        children: [new TextRun({ text: "Proceso de Despacho Aduanero", font: "Arial", size: 56, bold: true, color: AZUL })],
        alignment: AlignmentType.CENTER,
        spacing: { before: 1440, after: 240 },
      }),
      new Paragraph({
        children: [new TextRun({ text: "Rol del Tramitador / Apoderado de Aduana", font: "Arial", size: 32, color: AZUL_CLARO })],
        alignment: AlignmentType.CENTER,
        spacing: { after: 480 },
      }),
      new Paragraph({
        children: [new TextRun({ text: "Valoracion tecnica e integracion con plataforma ODIN 2.0", font: "Arial", size: 24, color: "555555", italics: true })],
        alignment: AlignmentType.CENTER,
        spacing: { after: 1440 },
      }),

      // Caja de metadatos
      new Table({
        width: { size: 6000, type: WidthType.DXA },
        columnWidths: [2400, 3600],
        rows: [
          new TableRow({ children: [
            new TableCell({ borders: bordes(AZUL_CLARO), width: { size: 2400, type: WidthType.DXA }, shading: { fill: AZUL_FONDO, type: ShadingType.CLEAR }, margins: { top: 80, bottom: 80, left: 120, right: 120 },
              children: [new Paragraph({ children: [new TextRun({ text: "Proyecto", font: "Arial", size: 20, bold: true, color: AZUL })] })] }),
            new TableCell({ borders: bordes(AZUL_CLARO), width: { size: 3600, type: WidthType.DXA }, shading: { fill: "FFFFFF", type: ShadingType.CLEAR }, margins: { top: 80, bottom: 80, left: 120, right: 120 },
              children: [new Paragraph({ children: [new TextRun({ text: "ENETEC S.A. / ODIN 2.0", font: "Arial", size: 20 })] })] }),
          ]}),
          new TableRow({ children: [
            new TableCell({ borders: bordes(AZUL_CLARO), width: { size: 2400, type: WidthType.DXA }, shading: { fill: AZUL_FONDO, type: ShadingType.CLEAR }, margins: { top: 80, bottom: 80, left: 120, right: 120 },
              children: [new Paragraph({ children: [new TextRun({ text: "Fecha", font: "Arial", size: 20, bold: true, color: AZUL })] })] }),
            new TableCell({ borders: bordes(AZUL_CLARO), width: { size: 3600, type: WidthType.DXA }, shading: { fill: "FFFFFF", type: ShadingType.CLEAR }, margins: { top: 80, bottom: 80, left: 120, right: 120 },
              children: [new Paragraph({ children: [new TextRun({ text: "Junio 2026", font: "Arial", size: 20 })] })] }),
          ]}),
          new TableRow({ children: [
            new TableCell({ borders: bordes(AZUL_CLARO), width: { size: 2400, type: WidthType.DXA }, shading: { fill: AZUL_FONDO, type: ShadingType.CLEAR }, margins: { top: 80, bottom: 80, left: 120, right: 120 },
              children: [new Paragraph({ children: [new TextRun({ text: "Estado", font: "Arial", size: 20, bold: true, color: AZUL })] })] }),
            new TableCell({ borders: bordes(AZUL_CLARO), width: { size: 3600, type: WidthType.DXA }, shading: { fill: "FFFFFF", type: ShadingType.CLEAR }, margins: { top: 80, bottom: 80, left: 120, right: 120 },
              children: [new Paragraph({ children: [new TextRun({ text: "Borrador para revision", font: "Arial", size: 20, color: NARANJA, bold: true })] })] }),
          ]}),
        ],
      }),

      espacio(2880),

      // ── SECCION 1: DOCUMENTOS DE ENTRADA ─────────────────────────────────
      new Paragraph({ heading: HeadingLevel.HEADING_1, children: [new TextRun("1. Documentos de Entrada del Tramitador")] }),
      parrafo("El apoderado de aduana opera a partir de tres documentos que entrega el proveedor extranjero:"),
      espacio(80),
      new Table({
        width: { size: 9000, type: WidthType.DXA },
        columnWidths: [1800, 7200],
        rows: [
          filaCabecera(["Documento", "Descripcion y uso"], [1800, 7200]),
          fila(["BL (Bill of Lading)", "Titulo de transporte maritimo. Identifica el contenedor, la escala (numero de manifiesto) y al consignatario. Es la llave para buscar en el Portal del Mariel y en SUA."], [1800, 7200], false),
          fila(["Lista de empaque (Packing List)", "Detalla el contenido por contenedor: productos, cantidades, pesos bruto/neto, dimensiones. Se cruza con la factura comercial."], [1800, 7200], true),
          fila(["Factura del proveedor (Commercial Invoice)", "Precio de venta, terminos Incoterm, valor CIF/FOB. Es la base para la valoracion aduanera y para la facturacion al cliente en ODIN 2.0."], [1800, 7200], false),
        ],
      }),

      espacio(200),

      // ── SECCION 2: FLUJO DEL PROCESO ─────────────────────────────────────
      new Paragraph({ heading: HeadingLevel.HEADING_1, children: [new TextRun("2. Flujo del Proceso de Despacho")] }),
      parrafo("El proceso atraviesa cuatro sistemas externos en secuencia obligatoria. Ningun paso puede iniciarse si el anterior no se completa satisfactoriamente."),
      espacio(80),
      tablaFlujo([
        ["1", "Portal del Mariel", "Verificar que el contenedor esta Arribado. Confirmar: estado (en patio / pronosticado), hora de entrada, No. de manifiesto, No. de contenedor y House BL."],
        ["2", "SUA — Aduana", "Consultar listado de manifiestos. Verificar que el BL esta registrado y consignado a la importadora. La Escala en SUA equivale al No. de manifiesto del Portal del Mariel."],
        ["3", "DM Plus", "Crear la Declaracion de Mercancia (DM). Requiere contenedor arribado y manifestado en SUA. Pasos internos: foto general, generar factura de entrada, Orden 1, validar DM, crear fichero."],
        ["4", "SUA — Despacho Centralizado", "Subir el fichero generado por DM Plus. Obtener el numero de DM. Descargar el reporte de despacho."],
        ["5", "DM Plus", "Capturar el numero de DM del SUA, el canal emitido y la fecha de liquidacion. Imprimir la declaracion final."],
        ["6", "VUA", "Subir el expediente completo a la Ventanilla Unica de la Aduana para cierre del proceso."],
      ]),

      espacio(200),

      // ── SECCION 3: VALORACION TECNICA ────────────────────────────────────
      new Paragraph({ heading: HeadingLevel.HEADING_1, children: [new TextRun("3. Valoracion Tecnica")] }),

      new Paragraph({ heading: HeadingLevel.HEADING_2, children: [new TextRun("3.1 Las tres realidades que definen el alcance")] }),
      tablaRealidades(),

      espacio(160),

      new Paragraph({ heading: HeadingLevel.HEADING_2, children: [new TextRun("3.2 Hipotesis de trabajo")] }),
      new Paragraph({
        children: [new TextRun({ text: "Construir la plataforma como un tracker de estados + carga manual de documentos, con un parser del fichero DM Plus como primer paso de automatizacion real. Si ese fichero es legible, el 80% del valor se consigue sin depender de APIs de sistemas gubernamentales.", font: "Arial", size: 20, italics: true, color: "444444" })],
        spacing: { after: 120 },
        shading: { fill: AZUL_FONDO, type: ShadingType.CLEAR },
        border: { left: { style: BorderStyle.SINGLE, size: 12, color: AZUL_CLARO, space: 8 } },
        indent: { left: 360 },
      }),

      espacio(160),

      new Paragraph({ heading: HeadingLevel.HEADING_2, children: [new TextRun("3.3 Necesidades de la plataforma ODIN 2.0")] }),
      bullet("Recibir y almacenar los documentos de embarque (BL, packing list, factura comercial) vinculados al proceso de importacion."),
      bullet("Registrar y trazar el estado en cada sistema externo (Portal del Mariel, SUA, DM Plus, VUA)."),
      bullet("Permitir al tramitador subir el fichero DM Plus y extraer automaticamente: DM#, contenedor, BL, valor CIF, aranceles."),
      bullet("Tomar el numero de DM comercial y los valores del despacho para generar la factura al cliente."),
      bullet("Ensamblar el expediente VUA con la nomenclatura y estructura correcta antes de la subida manual."),

      espacio(200),

      // ── SECCION 4: PREGUNTAS A PROVEEDORES ───────────────────────────────
      new Paragraph({ heading: HeadingLevel.HEADING_1, children: [new TextRun("4. Preguntas para los Proveedores de Servicio")] }),
      parrafo("Las siguientes preguntas deben responderse antes de iniciar el desarrollo de integraciones. Las respuestas determinan si la plataforma puede automatizar un paso o debe manejarlo como entrada manual asistida."),

      espacio(120),
      new Paragraph({ heading: HeadingLevel.HEADING_2, children: [new TextRun("4.1 DM Plus  (prioridad maxima)")] }),
      tablaPreguntas([
        ["1", "¿Cual es el formato exacto del fichero que genera DM Plus — XML, TXT delimitado, propietario binario? ¿Existe especificacion tecnica publicada?"],
        ["2", "¿El fichero contiene campos estructurados para: DM#, No. de contenedor, House BL, valor CIF, valor FOB, aranceles e impuestos? ¿Con que nombre de campo exacto?"],
        ["3", "¿DM Plus tiene alguna API, servicio web o interfaz de linea de comando para generar o leer declaraciones sin abrir la UI grafica?"],
        ["4", "¿La licencia de DM Plus permite que un sistema externo lea o escriba en su base de datos local (acceso directo a BD)?"],
        ["5", "¿El boletin (canal emitido + fecha de liquidacion) que devuelve SUA aparece en algun archivo descargable, o solo se visualiza en pantalla?"],
      ]),

      espacio(160),
      new Paragraph({ heading: HeadingLevel.HEADING_2, children: [new TextRun("4.2 SUA — Sistema Unico Aduanero")] }),
      tablaPreguntas([
        ["6", "¿SUA tiene algun endpoint de consulta de manifiesto por BL o por Escala (No. de manifiesto) accesible desde sistemas externos (REST, SOAP, otro)?"],
        ["7", "¿El reporte que se descarga del Despacho Centralizado tiene formato estructurado (XML / JSON / CSV) o es un PDF imagen sin texto extraible?"],
        ["8", "¿El numero de DM que emite SUA aparece en ese reporte descargable de forma parseeable (campo de texto, no imagen)?"],
        ["9", "¿Existe un entorno de pruebas (sandbox) de SUA habilitado para desarrollo e integracion sin afectar datos reales?"],
      ]),

      espacio(160),
      new Paragraph({ heading: HeadingLevel.HEADING_2, children: [new TextRun("4.3 Portal del Mariel")] }),
      tablaPreguntas([
        ["10", "¿El Portal del Mariel tiene API REST o SOAP para consultar el estado del contenedor por No. de BL o por No. de contenedor?"],
        ["11", "Si no hay API, ¿existe algun feed (RSS, exportacion periodica, correo automatico) con el estado de arribo de contenedores?"],
        ["12", "¿Quien administra tecnicamente el portal (ZEDM, Almacenes Universales, otra entidad) y cual es el contacto tecnico para integraciones?"],
      ]),

      espacio(160),
      new Paragraph({ heading: HeadingLevel.HEADING_2, children: [new TextRun("4.4 VUA — Ventanilla Unica de la Aduana")] }),
      tablaPreguntas([
        ["13", "¿VUA acepta subida del expediente por API (REST / SOAP) o exclusivamente por interfaz web manual?"],
        ["14", "¿Cual es la estructura exacta del expediente que exige VUA: nombres de archivos, tipos permitidos, orden, tamano maximo por archivo?"],
        ["15", "¿VUA devuelve un acuse de recibo estructurado (numero de radicacion, timestamp) que se pueda capturar automaticamente o guardar en la plataforma?"],
      ]),

      espacio(160),
      new Paragraph({ heading: HeadingLevel.HEADING_2, children: [new TextRun("4.5 Proceso y datos (tramitador / apoderado)")] }),
      tablaPreguntas([
        ["16", "¿Un BL puede estar asociado a multiples contenedores, o la relacion es siempre 1:1?"],
        ["17", "¿La factura que genera DM Plus ('dando entrada a la factura del proveedor') es una factura aduanera interna o una reformat de la factura comercial original?"],
        ["18", "¿Los valores que ENETEC necesita para facturar al cliente (CIF, aranceles, otros gastos) provienen todos del DM, o hay valores que solo estan en la factura comercial del proveedor?"],
        ["19", "¿Cuanto tiempo transcurre tipicamente entre la llegada del contenedor al Mariel y la obtencion del numero de DM de SUA? (Para definir timeouts y estados de espera en la plataforma.)"],
        ["20", "¿El canal emitido por SUA (rojo / amarillo / verde) determina si hay inspeccion fisica, y eso afecta el timeline de facturacion al cliente?"],
      ]),

      espacio(200),

      // ── SECCION 5: PROXIMOS PASOS ─────────────────────────────────────────
      new Paragraph({ heading: HeadingLevel.HEADING_1, children: [new TextRun("5. Proximos Pasos Sugeridos")] }),
      new Table({
        width: { size: 9000, type: WidthType.DXA },
        columnWidths: [600, 5400, 3000],
        rows: [
          filaCabecera(["#", "Accion", "Responsable"], [600, 5400, 3000]),
          fila(["1", "Enviar cuestionario DM Plus al proveedor del software y solicitar formato del fichero y especificacion tecnica.", "Equipo ENETEC / PYXEL"], [600, 5400, 3000], false),
          fila(["2", "Gestionar acceso tecnico al Portal del Mariel y confirmar existencia de API o feed de datos.", "Equipo ENETEC"], [600, 5400, 3000], true),
          fila(["3", "Solicitar a la Aduana acceso al sandbox de SUA y documentacion de endpoints disponibles.", "Equipo ENETEC"], [600, 5400, 3000], false),
          fila(["4", "Obtener la especificacion del expediente VUA (nombres, tipos, estructura de carpetas).", "Tramitador / Apoderado"], [600, 5400, 3000], true),
          fila(["5", "Con las respuestas anteriores, definir que pasos se automatizan y cuales se gestionan como entrada manual en ODIN 2.0.", "Equipo PYXEL"], [600, 5400, 3000], false),
        ],
      }),

      espacio(300),

      // Nota final
      new Paragraph({
        children: [
          new TextRun({ text: "Nota: ", font: "Arial", size: 18, bold: true, color: ROJO }),
          new TextRun({ text: "Este documento es un borrador de trabajo generado a partir de la sesion de levantamiento del 17 de junio de 2026. Debe ser revisado y completado por el tramitador de aduana antes de su uso en el diseno tecnico de la plataforma.", font: "Arial", size: 18, color: "555555", italics: true }),
        ],
        spacing: { after: 120 },
        shading: { fill: "FFF2CC", type: ShadingType.CLEAR },
        border: { left: { style: BorderStyle.SINGLE, size: 12, color: NARANJA, space: 8 } },
        indent: { left: 360 },
      }),

    ],
  }],
});

// ── Guardar ──────────────────────────────────────────────────────────────────
Packer.toBuffer(doc).then(buffer => {
  fs.writeFileSync("D:\\trabajo\\Pyxel\\IA\\ENETEC_traspaso\\docs\\Proceso_Despacho_Aduanero_ENETEC.docx", buffer);
  console.log("OK: Proceso_Despacho_Aduanero_ENETEC.docx generado");
}).catch(err => { console.error("ERROR:", err); process.exit(1); });
