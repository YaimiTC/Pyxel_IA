const { Document, Packer, Paragraph, TextRun, HeadingLevel, AlignmentType, BorderStyle, ShadingType, WidthType, Table, TableRow, TableCell } = require('docx');
const fs = require('fs');

const AZUL = '1F3864';
const AZUL_CLARO = 'D6E4F0';
const GRIS = 'F5F5F5';
const ROJO = 'C0392B';
const VERDE = '1A5276';
const MORADO = 'E8DAEF';

function titulo(text) {
  return new Paragraph({
    heading: HeadingLevel.HEADING_1,
    spacing: { before: 0, after: 200 },
    children: [new TextRun({ text, bold: true, size: 28, color: AZUL, font: 'Arial' })]
  });
}

function seccion(text) {
  return new Paragraph({
    heading: HeadingLevel.HEADING_2,
    spacing: { before: 300, after: 120 },
    children: [new TextRun({ text, bold: true, size: 24, color: VERDE, font: 'Arial' })]
  });
}

function incidenciaTitulo(text) {
  return new Paragraph({
    spacing: { before: 240, after: 80 },
    children: [new TextRun({ text, bold: true, size: 22, color: ROJO, font: 'Arial' })]
  });
}

function parrafo(text) {
  return new Paragraph({
    spacing: { before: 60, after: 60 },
    alignment: AlignmentType.JUSTIFIED,
    children: [new TextRun({ text, size: 20, font: 'Arial' })]
  });
}

function separador() {
  return new Paragraph({
    spacing: { before: 100, after: 100 },
    border: { bottom: { style: BorderStyle.SINGLE, size: 4, color: 'CCCCCC' } },
    children: [new TextRun('')]
  });
}

function celdaHeader(text, color) {
  const border = { style: BorderStyle.SINGLE, size: 1, color: 'AAAAAA' };
  const borders = { top: border, bottom: border, left: border, right: border };
  return new TableCell({
    borders,
    width: { size: 3120, type: WidthType.DXA },
    shading: { fill: color || AZUL_CLARO, type: ShadingType.CLEAR },
    margins: { top: 80, bottom: 80, left: 120, right: 120 },
    children: [new Paragraph({
      children: [new TextRun({ text, bold: true, size: 18, font: 'Arial', color: '000000' })]
    })]
  });
}

function celda(text, shade) {
  const border = { style: BorderStyle.SINGLE, size: 1, color: 'CCCCCC' };
  const borders = { top: border, bottom: border, left: border, right: border };
  return new TableCell({
    borders,
    width: { size: 3120, type: WidthType.DXA },
    shading: { fill: shade || 'FFFFFF', type: ShadingType.CLEAR },
    margins: { top: 80, bottom: 80, left: 120, right: 120 },
    children: [new Paragraph({
      children: [new TextRun({ text, size: 18, font: 'Arial' })]
    })]
  });
}

const doc = new Document({
  sections: [{
    properties: {
      page: {
        size: { width: 12240, height: 15840 },
        margin: { top: 1440, right: 1440, bottom: 1440, left: 1440 }
      }
    },
    children: [

      // TÍTULO PRINCIPAL
      new Paragraph({
        spacing: { before: 0, after: 400 },
        alignment: AlignmentType.CENTER,
        children: [
          new TextRun({ text: 'Análisis de Incidencias — v2', bold: true, size: 36, color: AZUL, font: 'Arial' }),
          new TextRun({ text: '\nPortal de Importaciones — ERP ODIN', bold: false, size: 22, color: '555555', font: 'Arial', break: 1 }),
          new TextRun({ text: '\nFecha: 14 de junio de 2026', bold: false, size: 18, color: '888888', font: 'Arial', break: 1 }),
        ]
      }),

      separador(),

      // SECCIÓN 1: FLUJO
      titulo('1. Flujo del proceso de importación'),

      parrafo('El proceso de importación sigue una secuencia específica que genera distintos documentos en el sistema. Comprender este flujo es necesario para interpretar correctamente el comportamiento del portal.'),

      parrafo('1. El cliente acreditado envía una solicitud de importación desde el portal web. El sistema crea una orden de venta inicial (OV inicial) asociada al cliente.'),
      parrafo('2. El comercial evalúa proveedores desde el backend y envía una solicitud de presupuesto. El sistema crea una orden de compra (OC) para el proveedor evaluado.'),
      parrafo('3. Al completar la evaluación final, el sistema genera una nueva orden de venta (OV final). El comercial la confirma y el proceso de importación queda formalmente iniciado.'),
      parrafo('4. La importación avanza por siete etapas: SOLICITUD, TRÁMITES EN ORIGEN, EN TRÁNSITO A PUERTO DE DESTINO, TRÁMITES EN DESTINO, LISTO PARA EXTRAER, EN ALMACÉN CLIENTE y DEVOLUCIÓN DEL CONTENEDOR.'),
      parrafo('Nota: La OV inicial nunca aparece en el portal del cliente. La OC del proveedor nunca aparece en su portal. Solo la OV final confirmada es visible en el portal del cliente bajo Solicitudes.'),

      separador(),

      // SECCIÓN 2: INCIDENCIAS
      titulo('2. Incidencias identificadas'),

      incidenciaTitulo('Incidencia 1 — Enlace /my/notifications devuelve 404'),
      parrafo('El enlace /my/notifications devuelve error 404 para el cliente y para el proveedor en cualquier estado del proceso. La ruta no está implementada en el portal.'),

      incidenciaTitulo('Incidencia 2 — Contador de importaciones no refleja la etapa actual'),
      parrafo('Para el cliente: el widget Importaciones muestra 1 únicamente cuando la importación está en la primera etapa (SOLICITUD). En cuanto el comercial avanza la importación a cualquier etapa posterior, el contador cae a 0, aunque la importación esté activa y en curso.'),
      parrafo('Para el proveedor: el contador de importaciones siempre muestra 0, en todas las etapas del proceso.'),
      parrafo('La lista de importaciones (/model/imports) y el detalle de cada importación sí funcionan correctamente para ambos usuarios en todas las etapas. Ambos pueden consultar la información y el proveedor puede añadir documentos e información de embarque directamente desde su portal.'),

      incidenciaTitulo('Incidencia 3 — El cliente ve dos solicitudes por importación en la lista'),
      parrafo('Por cada importación, el cliente ve dos solicitudes en la lista /my/orders: la OV de la evaluación final y la OV de la importación. El flujo debería mostrar solo una. El contador de Solicitudes refleja correctamente las órdenes en borrador, pero la lista muestra el doble de lo esperado como consecuencia de esta duplicidad.'),

      incidenciaTitulo('Incidencia 4 — La orden de compra del proveedor nunca aparece en su portal'),
      parrafo('Durante la evaluación de proveedores el comercial genera una orden de compra (OC) asociada al proveedor. Esta OC nunca aparece en el portal del proveedor: el contador de Solicitudes permanece en 0 y la lista aparece vacía. El proveedor no puede ver ni dar seguimiento a la OC desde su portal.'),

      incidenciaTitulo('Incidencia 5 — Contador de facturas siempre en 0'),
      parrafo('El widget Facturas en /my/home del cliente siempre muestra 0, aunque existan facturas confirmadas para su empresa. La lista /my/invoices sí muestra correctamente las facturas cuando están en estado confirmado. Existe un desfase entre lo que cuenta el widget y lo que el usuario puede ver en la lista.'),

      separador(),

      // SECCIÓN 3: CAUSA TÉCNICA
      titulo('3. Causa técnica'),

      seccion('Incidencia 1 — /my/notifications devuelve 404'),
      parrafo('La ruta /my/notifications no está registrada en ningún controlador del portal. El enlace existe en la plantilla pero no tiene una vista ni un controlador que lo atienda.'),

      seccion('Incidencia 2 — Contador de importaciones'),
      parrafo('El contador en portal_controller.py aplica el filtro stage_id = primera_etapa (order="sequence asc", limit=1). En cuanto la importación avanza de etapa, deja de cumplir ese filtro y el contador vuelve a 0. El controlador no tiene lógica para contar importaciones activas en etapas posteriores.'),
      parrafo('Para el proveedor, la lógica del contador busca importaciones en stage_id = primera_etapa filtradas por provider_id. En etapa 1 la importación puede no tener aún proveedor asignado, o el filtro no coincide. En etapas posteriores el mismo problema de stage_id aplica.'),

      seccion('Incidencia 3 — Dos solicitudes por importación'),
      parrafo('El flujo de importación genera dos órdenes de venta distintas para el mismo cliente: la OV de la evaluación final y la OV de importación. Ambas quedan asociadas al partner del cliente y ambas cumplen las condiciones de visibilidad en el portal (/my/orders). El portal no filtra por origen ni distingue entre ambas, por lo que las muestra juntas en la lista.'),
      parrafo('El contador de Solicitudes cuenta únicamente las órdenes en estado borrador (state="draft"). Si alguna de las dos OV está en borrador, el contador la refleja correctamente. La discrepancia entre el contador y la lista se explica porque el contador filtra por estado y la lista muestra todas las accesibles.'),

      seccion('Incidencia 4 — OC del proveedor no aparece en su portal'),
      parrafo('El contador de Solicitudes del proveedor en portal_controller.py busca purchase.order con state="draft". En el momento en que el comercial envía la solicitud al proveedor, la OC pasa automáticamente al estado "sent" (enviada), por lo que deja de cumplir el filtro y el contador permanece en 0.'),
      parrafo('La lista de Solicitudes (/my/orders) está configurada para mostrar sale.order (órdenes de venta), no purchase.order (órdenes de compra), por lo que aunque la OC existiera en el estado correcto tampoco aparecería en esa página.'),

      seccion('Incidencia 5 — Contador de facturas en 0'),
      parrafo('El contador new_invoices_count en portal_controller.py busca account.move con state="draft", move_type="out_invoice" y partner_id=business_partner_id usando sudo(). Las facturas en borrador no son visibles para el usuario en la lista del portal, por lo que el contador refleja documentos que el usuario no puede ver.'),
      parrafo('Cuando las facturas están confirmadas (state="posted"), la lista /my/invoices las muestra correctamente, pero el contador no las incluye porque filtra exclusivamente por state="draft". El resultado es que el contador siempre muestra 0 desde la perspectiva del usuario: los borradores no se ven en la lista y los confirmados no se cuentan en el widget.'),

      separador(),

      // SECCIÓN 4: TABLA COMPARATIVA
      titulo('4. Comportamiento del portal por usuario y etapa'),

      new Paragraph({
        spacing: { before: 60, after: 120 },
        children: [new TextRun({ text: 'La tabla muestra el estado de los widgets y listas principales según la etapa de la importación. Los enlaces que no se mencionan retornan 200 en todas las etapas sin cambio de comportamiento, con excepción de /my/notifications que devuelve 404 siempre (Incidencia 1).', size: 20, font: 'Arial', italics: true })]
      }),

      new Paragraph({ spacing: { before: 0, after: 120 }, children: [] }),

      // Tabla CLIENTE
      new Paragraph({
        spacing: { before: 120, after: 80 },
        children: [new TextRun({ text: 'CLIENTE (yaimitccc@gmail.com)', bold: true, size: 22, color: AZUL, font: 'Arial' })]
      }),

      new Table({
        width: { size: 9360, type: WidthType.DXA },
        columnWidths: [2800, 1640, 1640, 1640, 1640],
        rows: [
          new TableRow({
            tableHeader: true,
            children: [
              celdaHeader('Elemento', AZUL_CLARO),
              celdaHeader('Sin importación', AZUL_CLARO),
              celdaHeader('Etapa 1 (SOLICITUD)', AZUL_CLARO),
              celdaHeader('Etapas 2–6', AZUL_CLARO),
              celdaHeader('Etapa 7 (DEVOLUCIÓN)', AZUL_CLARO),
            ]
          }),
          new TableRow({ children: [
            celda('Widget Importaciones — contador', GRIS),
            celda('0', GRIS),
            celda('1 ✓', GRIS),
            celda('0 ⚠ (Incid. 2)', GRIS),
            celda('0 ⚠ (Incid. 2)', GRIS),
          ]}),
          new TableRow({ children: [
            celda('Lista /model/imports'),
            celda('vacía'),
            celda('1 importación ✓'),
            celda('N importaciones ✓'),
            celda('N importaciones ✓'),
          ]}),
          new TableRow({ children: [
            celda('Detalle e información de importación', GRIS),
            celda('—', GRIS),
            celda('accesible ✓', GRIS),
            celda('accesible ✓', GRIS),
            celda('accesible ✓', GRIS),
          ]}),
          new TableRow({ children: [
            celda('Widget Solicitudes — contador'),
            celda('0'),
            celda('según OVs en borrador (Incid. 3)'),
            celda('según OVs en borrador (Incid. 3)'),
            celda('según OVs en borrador (Incid. 3)'),
          ]}),
          new TableRow({ children: [
            celda('Lista /my/orders', GRIS),
            celda('vacía', GRIS),
            celda('2 por importación ⚠ (Incid. 3)', GRIS),
            celda('2 por importación ⚠ (Incid. 3)', GRIS),
            celda('2 por importación ⚠ (Incid. 3)', GRIS),
          ]}),
          new TableRow({ children: [
            celda('Widget Facturas — contador'),
            celda('0 ⚠ (Incid. 5)'),
            celda('0 ⚠ (Incid. 5)'),
            celda('0 ⚠ (Incid. 5)'),
            celda('0 ⚠ (Incid. 5)'),
          ]}),
          new TableRow({ children: [
            celda('Lista /my/invoices', GRIS),
            celda('vacía', GRIS),
            celda('facturas confirmadas ✓', GRIS),
            celda('facturas confirmadas ✓', GRIS),
            celda('facturas confirmadas ✓', GRIS),
          ]}),
        ]
      }),

      new Paragraph({ spacing: { before: 120, after: 80 }, children: [] }),

      // Tabla PROVEEDOR
      new Paragraph({
        spacing: { before: 200, after: 80 },
        children: [new TextRun({ text: 'PROVEEDOR (yaimitpp@gmail.com)', bold: true, size: 22, color: '6A0572', font: 'Arial' })]
      }),

      new Table({
        width: { size: 9360, type: WidthType.DXA },
        columnWidths: [2800, 1640, 1640, 1640, 1640],
        rows: [
          new TableRow({
            tableHeader: true,
            children: [
              celdaHeader('Elemento', MORADO),
              celdaHeader('Sin importación', MORADO),
              celdaHeader('Etapa 1 (SOLICITUD)', MORADO),
              celdaHeader('Etapas 2–6', MORADO),
              celdaHeader('Etapa 7 (DEVOLUCIÓN)', MORADO),
            ]
          }),
          new TableRow({ children: [
            celda('Widget Importaciones — contador', GRIS),
            celda('0 ⚠ (Incid. 2)', GRIS),
            celda('0 ⚠ (Incid. 2)', GRIS),
            celda('0 ⚠ (Incid. 2)', GRIS),
            celda('0 ⚠ (Incid. 2)', GRIS),
          ]}),
          new TableRow({ children: [
            celda('Lista /model/imports'),
            celda('vacía'),
            celda('1 importación ✓'),
            celda('N importaciones ✓'),
            celda('N importaciones ✓'),
          ]}),
          new TableRow({ children: [
            celda('Detalle, información y carga de docs', GRIS),
            celda('—', GRIS),
            celda('accesible ✓', GRIS),
            celda('accesible ✓', GRIS),
            celda('accesible ✓', GRIS),
          ]}),
          new TableRow({ children: [
            celda('Widget Solicitudes — contador (OC)'),
            celda('0 ⚠ (Incid. 4)'),
            celda('0 ⚠ (Incid. 4)'),
            celda('0 ⚠ (Incid. 4)'),
            celda('0 ⚠ (Incid. 4)'),
          ]}),
          new TableRow({ children: [
            celda('Lista /my/orders (OC)', GRIS),
            celda('vacía ⚠ (Incid. 4)', GRIS),
            celda('vacía ⚠ (Incid. 4)', GRIS),
            celda('vacía ⚠ (Incid. 4)', GRIS),
            celda('vacía ⚠ (Incid. 4)', GRIS),
          ]}),
        ]
      }),

      new Paragraph({ spacing: { before: 120, after: 40 }, children: [
        new TextRun({ text: '✓ = comportamiento correcto    |    ⚠ = incidencia detectada    |    N = número total de importaciones registradas', size: 16, font: 'Arial', italics: true, color: '777777' })
      ]}),
      new Paragraph({ spacing: { before: 0, after: 80 }, children: [
        new TextRun({ text: 'Etapas 2–6 comprenden: TRÁMITES EN ORIGEN, EN TRÁNSITO A PUERTO DE DESTINO, TRÁMITES EN DESTINO, LISTO PARA EXTRAER, EN ALMACÉN CLIENTE. Comportamiento idéntico en todas.', size: 16, font: 'Arial', italics: true, color: '777777' })
      ]}),

      separador(),

      // SECCIÓN 5: COMPARATIVA DE ENLACES
      titulo('5. Comparativa de enlaces por estado'),

      new Paragraph({
        spacing: { before: 60, after: 120 },
        children: [new TextRun({ text: 'La tabla muestra el código de respuesta HTTP de cada enlace clave según el estado del proceso. Los enlaces no listados devuelven 200 en todos los estados sin variación.', size: 20, font: 'Arial', italics: true })]
      }),

      new Paragraph({ spacing: { before: 0, after: 80 }, children: [] }),

      new Paragraph({
        spacing: { before: 120, after: 80 },
        children: [new TextRun({ text: 'CLIENTE (yaimitccc@gmail.com)', bold: true, size: 22, color: AZUL, font: 'Arial' })]
      }),

      new Table({
        width: { size: 9360, type: WidthType.DXA },
        columnWidths: [2500, 1490, 1790, 1790, 1790],
        rows: [
          new TableRow({
            tableHeader: true,
            children: [
              celdaHeader('Enlace', AZUL_CLARO),
              celdaHeader('Sin importación', AZUL_CLARO),
              celdaHeader('Etapa 1 (SOLICITUD)', AZUL_CLARO),
              celdaHeader('Etapas 2–6', AZUL_CLARO),
              celdaHeader('Etapa 7 (DEVOLUCIÓN)', AZUL_CLARO),
            ]
          }),
          new TableRow({ children: [
            celda('/my/home', GRIS), celda('200', GRIS), celda('200', GRIS), celda('200', GRIS), celda('200', GRIS)
          ]}),
          new TableRow({ children: [
            celda('/my/orders (Solicitudes)'), celda('200 — lista vacía'), celda('200 — lista ✓'), celda('200 — lista ✓'), celda('200 — lista ✓')
          ]}),
          new TableRow({ children: [
            celda('/my/invoices (Facturas)', GRIS), celda('200 — lista vacía', GRIS), celda('200 — facturas confirmadas ✓', GRIS), celda('200 — facturas confirmadas ✓', GRIS), celda('200 — facturas confirmadas ✓', GRIS)
          ]}),
          new TableRow({ children: [
            celda('/model/imports (Importaciones)'), celda('200 — lista vacía'), celda('200 — lista ✓'), celda('200 — lista ✓'), celda('200 — lista ✓')
          ]}),
          new TableRow({ children: [
            celda('/business-register?type=accreditation', GRIS), celda('303 → thanks', GRIS), celda('200 → /my/home', GRIS), celda('200 → /my/home', GRIS), celda('200 → /my/home', GRIS)
          ]}),
          new TableRow({ children: [
            celda('/business-register?type=import'), celda('200 formulario'), celda('200 formulario'), celda('200 formulario'), celda('200 formulario')
          ]}),
          new TableRow({ children: [
            celda('/nomenclador?from=import_registration', GRIS), celda('200', GRIS), celda('200', GRIS), celda('200', GRIS), celda('200', GRIS)
          ]}),
          new TableRow({ children: [
            celda('/descargar/load_products'), celda('200'), celda('200'), celda('200'), celda('200')
          ]}),
          new TableRow({ children: [
            celda('/descargar/solicitud', GRIS), celda('200', GRIS), celda('200', GRIS), celda('200', GRIS), celda('200', GRIS)
          ]}),
          new TableRow({ children: [
            celda('/my/notifications'), celda('404 ⚠'), celda('404 ⚠'), celda('404 ⚠'), celda('404 ⚠')
          ]}),
          new TableRow({ children: [
            celda('Resto de enlaces', GRIS), celda('200', GRIS), celda('200 sin cambio', GRIS), celda('200 sin cambio', GRIS), celda('200 sin cambio', GRIS)
          ]}),
        ]
      }),

      new Paragraph({ spacing: { before: 120, after: 80 }, children: [] }),

      new Paragraph({
        spacing: { before: 200, after: 80 },
        children: [new TextRun({ text: 'PROVEEDOR (yaimitpp@gmail.com)', bold: true, size: 22, color: '6A0572', font: 'Arial' })]
      }),

      new Table({
        width: { size: 9360, type: WidthType.DXA },
        columnWidths: [2500, 1490, 1790, 1790, 1790],
        rows: [
          new TableRow({
            tableHeader: true,
            children: [
              celdaHeader('Enlace', MORADO),
              celdaHeader('Sin importación', MORADO),
              celdaHeader('Etapa 1 (SOLICITUD)', MORADO),
              celdaHeader('Etapas 2–6', MORADO),
              celdaHeader('Etapa 7 (DEVOLUCIÓN)', MORADO),
            ]
          }),
          new TableRow({ children: [
            celda('/my/home', GRIS), celda('200', GRIS), celda('200', GRIS), celda('200', GRIS), celda('200', GRIS)
          ]}),
          new TableRow({ children: [
            celda('/my/orders (Solicitudes — OC)'), celda('200 — lista vacía ⚠'), celda('200 — lista vacía ⚠'), celda('200 — lista vacía ⚠'), celda('200 — lista vacía ⚠')
          ]}),
          new TableRow({ children: [
            celda('/my/invoices', GRIS), celda('200 — lista vacía', GRIS), celda('200 — lista vacía', GRIS), celda('200 — lista vacía', GRIS), celda('200 — lista vacía', GRIS)
          ]}),
          new TableRow({ children: [
            celda('/model/imports (Importaciones)'), celda('200 — lista vacía'), celda('200 — lista ✓'), celda('200 — lista ✓'), celda('200 — lista ✓')
          ]}),
          new TableRow({ children: [
            celda('/business-register?type=accreditation', GRIS), celda('303 → thanks', GRIS), celda('200 → /my/home', GRIS), celda('200 → /my/home', GRIS), celda('200 → /my/home', GRIS)
          ]}),
          new TableRow({ children: [
            celda('/business-register?type=import'), celda('200 bloqueado'), celda('200 bloqueado'), celda('200 bloqueado'), celda('200 bloqueado')
          ]}),
          new TableRow({ children: [
            celda('/my/notifications', GRIS), celda('404 ⚠', GRIS), celda('404 ⚠', GRIS), celda('404 ⚠', GRIS), celda('404 ⚠', GRIS)
          ]}),
          new TableRow({ children: [
            celda('Resto de enlaces'), celda('200'), celda('200 sin cambio'), celda('200 sin cambio'), celda('200 sin cambio')
          ]}),
        ]
      }),

      new Paragraph({ spacing: { before: 120, after: 40 }, children: [
        new TextRun({ text: '⚠ = incidencia detectada    |    bloqueado = página accesible pero con mensaje de acceso denegado    |    ✓ = comportamiento correcto', size: 16, font: 'Arial', italics: true, color: '777777' })
      ]}),

      separador(),

      // TABLA RESUMEN
      titulo('6. Resumen de las 5 incidencias'),

      new Paragraph({ spacing: { before: 0, after: 120 }, children: [] }),

      new Table({
        width: { size: 9360, type: WidthType.DXA },
        columnWidths: [500, 1800, 2100, 2400, 2560],
        rows: [
          new TableRow({
            tableHeader: true,
            children: [
              celdaHeader('#', AZUL_CLARO),
              celdaHeader('Afecta', AZUL_CLARO),
              celdaHeader('Widget / Ruta', AZUL_CLARO),
              celdaHeader('Síntoma', AZUL_CLARO),
              celdaHeader('Causa raíz', AZUL_CLARO),
            ]
          }),
          new TableRow({ children: [
            celda('1', GRIS),
            celda('Cliente y Proveedor', GRIS),
            celda('/my/notifications', GRIS),
            celda('Error 404 en todos los estados', GRIS),
            celda('Ruta no implementada en el portal', GRIS),
          ]}),
          new TableRow({ children: [
            celda('2'),
            celda('Cliente y Proveedor'),
            celda('Widget Importaciones'),
            celda('Cliente: 0 en etapas 2–7. Proveedor: siempre 0. Lista y detalle sí funcionan.'),
            celda('El contador filtra stage_id = primera etapa. Al avanzar la importación deja de contarla.'),
          ]}),
          new TableRow({ children: [
            celda('3', GRIS),
            celda('Cliente', GRIS),
            celda('Widget Solicitudes / /my/orders', GRIS),
            celda('Aparecen 2 solicitudes por importación: OV evaluación final + OV importación', GRIS),
            celda('Ambas OV quedan asociadas al partner del cliente y el portal las muestra sin distinción de origen', GRIS),
          ]}),
          new TableRow({ children: [
            celda('4'),
            celda('Proveedor'),
            celda('Widget Solicitudes / /my/orders'),
            celda('La OC del proveedor nunca aparece: contador 0 y lista vacía'),
            celda('La OC pasa a "sent" al enviarse (ya no es draft). La lista muestra sale.order, no purchase.order'),
          ]}),
          new TableRow({ children: [
            celda('5', GRIS),
            celda('Cliente', GRIS),
            celda('Widget Facturas', GRIS),
            celda('Contador siempre 0 aunque existan facturas confirmadas visibles en la lista', GRIS),
            celda('El contador filtra state="draft" pero los borradores no son visibles en la lista. Las confirmadas no se cuentan.', GRIS),
          ]}),
        ]
      }),

    ]
  }]
});

Packer.toBuffer(doc).then(buffer => {
  fs.writeFileSync('D:\\trabajo\\Pyxel\\IA\\incidencias_portal_v2.docx', buffer);
  console.log('Documento creado: D:\\trabajo\\Pyxel\\IA\\incidencias_portal_v2.docx');
});
