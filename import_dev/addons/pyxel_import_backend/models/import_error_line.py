import base64
import os
import tempfile
import xlwt
from datetime import datetime
from odoo import models, fields, api
from odoo.exceptions import UserError
import logging

_logger = logging.getLogger(__name__)


class ImportErrorLog(models.Model):
    _name = 'import.error.log'
    _description = 'Log de Errores de Importación'
    _order = 'import_date desc, id desc'

    name = fields.Char(string='Nombre del Archivo', required=True)
    import_date = fields.Datetime(string='Fecha de Importación', default=fields.Datetime.now())
    # Se filtran por tipo para separar errores reales de las otras dos listas
    # informativas (cambio de importadora / no está en el fichero). Las líneas
    # viejas (sin tipo) se tratan como error.
    error_lines = fields.One2many(
        'import.error.line', 'log_id', string='Líneas con Error',
        domain=['|', ('line_type', '=', 'error'), ('line_type', '=', False)])
    nuevos_lines = fields.One2many(
        'import.error.line', 'log_id', string='Contenedores no procesados (nuevos)',
        domain=[('line_type', '=', 'nuevo')])
    cambio_lines = fields.One2many(
        'import.error.line', 'log_id', string='Cambiaron de importadora',
        domain=[('line_type', '=', 'cambio')])
    no_fichero_lines = fields.One2many(
        'import.error.line', 'log_id', string='En el sistema, no en el fichero',
        domain=[('line_type', '=', 'no_fichero')])
    otro_viaje_lines = fields.One2many(
        'import.error.line', 'log_id', string='El contenedor sí, ese viaje no',
        domain=[('line_type', '=', 'otro_viaje')])
    por_llegar_lines = fields.One2many(
        'import.error.line', 'log_id', string='Todavía por llegar',
        domain=[('line_type', '=', 'por_llegar')])
    purgado_lines = fields.One2many(
        'import.error.line', 'log_id', string='Dejaron de venir en el reporte',
        domain=[('line_type', '=', 'purgado')])
    duplicado_lines = fields.One2many(
        'import.error.line', 'log_id', string='Duplicados a unificar',
        domain=[('line_type', '=', 'duplicado')])
    otro_valor_lines = fields.One2many(
        'import.error.line', 'log_id', string='Otro valor, ya en el sistema',
        domain=[('line_type', '=', 'otro_valor')])
    sin_dato_lines = fields.One2many(
        'import.error.line', 'log_id', string='Sin dato, ya en el sistema',
        domain=[('line_type', '=', 'sin_dato')])
    cuarentena_lines = fields.One2many(
        'import.error.line', 'log_id', string='En cuarentena (BL corto)',
        domain=[('line_type', '=', 'cuarentena')])
    otras_importadoras_lines = fields.One2many(
        'import.error.line', 'log_id', string='Otra importadora del catálogo',
        domain=[('line_type', '=', 'otra_importadora')])
    import_file = fields.Binary(string="Archivo de Importación")
    filename = fields.Char(string="Nombre del Archivo")

    # ---- Resumen de la corrida: qué cambió (no la foto actual, eso es el
    # Tablero — esto es el delta de esta corrida puntual). ----
    arribados_count = fields.Integer(string='Arribados en esta corrida')
    habilitados_count = fields.Integer(
        string='Habilitados en esta corrida',
        help="Tienen fecha de liberación naviera (Master BL) y/o de liberación "
             "del consignatario/importador, pero todavía sin DM — no cuenta si "
             "ya pasó a Liberado en esta misma corrida.")
    liberados_count = fields.Integer(
        string='Liberados en esta corrida',
        help="Ya tienen DM además de la(s) liberación(es) — el contenedor está "
             "completo para poder extraerse.")
    extraidos_count = fields.Integer(string='Extraídos en esta corrida')
    devueltos_count = fields.Integer(string='Devueltos en esta corrida')

    nativos_count = fields.Integer(string='Nativos (H = empresa)')
    consignados_count = fields.Integer(string='Consignados (J = empresa)')
    otro_valor_count = fields.Integer(
        string='Otro valor, ya en el sistema',
        help="Filas cuyo contenedor YA existe en nuestro sistema y que el "
             "reporte trae con una empresa en H o J que NO está en el "
             "catálogo de importadoras (si estuviera, cae en 'Otra "
             "importadora del catálogo'). Es nuestro, tramitado por un "
             "tercero sin identificar (PALCO, EXPEDIMAR...): se sincroniza "
             "igual y sigue contando como nuestro. Ver la lista.")
    cambio_importadora_count = fields.Integer(
        string='Cambió a otra importadora',
        help="EN DESUSO desde que un cambio de nombre en H/J dejó de quitarle "
             "la pertenencia al contenedor. Se conserva para los reportes "
             "antiguos; en las corridas nuevas es siempre cero y su caso se "
             "cuenta en 'Otro valor, ya en el sistema'.")
    otras_importadoras_count = fields.Integer(
        string='Otra importadora del catálogo',
        help="Filas cuyo H o J matchea una importadora del catálogo que no "
             "es la nuestra (PROMAX, EMSERPET...), sea porque el contenedor "
             "ya existía o porque esta corrida lo creó. Ver la lista.")
    no_en_fichero_count = fields.Integer(
        string='En el sistema, no en el fichero',
        help="Contenedores del sistema cuyo NÚMERO no aparece en ninguna fila "
             "del fichero de esta corrida: o aún no arribó, o el número está "
             "mal. Ver la lista.")
    duplicado_count = fields.Integer(
        string='Duplicados a unificar',
        help="Embarques que el sistema tiene cargados dos veces con el BL "
             "escrito de formas distintas ('046638' y '46638', o la partida "
             "hija y la madre). Solo uno casa con la Terminal; el otro se "
             "queda sin sincronizar y atascado en su último estado. No entra "
             "en la suma de la clasificación: es un aviso sobre nuestros "
             "datos, no un tipo de fila del fichero. Ver la lista.")
    por_llegar_no_en_fichero_count = fields.Integer(
        string='Todavía por llegar',
        help="Contenedores del sistema sin fecha de arribo. Que el reporte de "
             "la Terminal no los traiga es lo normal — aún no han llegado. Se "
             "separan para que no ensucien las listas que sí piden revisión.")
    purgado_count = fields.Integer(
        string='Dejaron de venir en el reporte',
        help="Venían en corridas anteriores y esta ya no los trae. El reporte "
             "de la Terminal es una ventana, no un censo: purga filas cuando "
             "se anula o corrige un manifiesto. Conviene confirmarlos.")
    otro_viaje_count = fields.Integer(
        string='El contenedor sí, ese viaje no',
        help="Contenedores del sistema cuyo número sí viene en el fichero, "
             "pero siempre con otro BL. O la Terminal no trae ese viaje, o hay "
             "una errata en el BL o en el número. Se separan de los ausentes "
             "porque se revisan con el fichero delante. Ver la lista.")
    sin_dato_count = fields.Integer(
        string='Sin dato, ya en el sistema',
        help="Filas donde H y J vienen vacías, pero el contenedor+BL ya "
             "existe en nuestro sistema.")
    nuevos_count = fields.Integer(
        string='Contenedores no procesados (nuevos)',
        help="Contenedores de alguna importadora del catálogo (nativo, "
             "consignado u otra importadora reconocida) que venían en el "
             "fichero y NO existían en el sistema: la corrida los creó. Se "
             "listan para revisarlos/completarlos. Es un subconjunto de "
             "nativos+consignados+otras importadoras (no suma aparte).")
    cuarentena_count = fields.Integer(
        string='En cuarentena (BL corto)',
        help="Filas que NO se actualizaron porque su BL solo emparejaba por una "
             "clave demasiado corta ('391' en vez de 'SXERMAR-391') y ese mismo "
             "contenedor aparece en el fichero con varios embarques: podría ser "
             "la misma caja en otro viaje. Se desatascan escribiendo el BL "
             "completo en el sistema. No suma aparte en la clasificación — la "
             "fila ya se contó por su H/J; esto es un aviso sobre la calidad de "
             "nuestros BL, como los duplicados.")
    total_filas_count = fields.Integer(string='Total de filas en el archivo')

    # ---- Foto del estado de TODOS los contenedores al cerrar la corrida ----
    # Cada contenedor está en exactamente un estado (cadena if/elif), así que
    # la suma de los cinco = total de contenedores del sistema. Sirve de cuadre
    # a la vista. Se llena al terminar cada corrida; los reportes viejos
    # (anteriores a esta versión) quedan en 0.
    estado_por_llegar = fields.Integer(string='Por llegar')
    estado_arribado = fields.Integer(string='Arribado')
    estado_habilitado = fields.Integer(string='Habilitado / Liberado')
    estado_extraido = fields.Integer(string='Extraído')
    estado_retornado = fields.Integer(string='Retornado')
    estado_total = fields.Integer(
        string='Total de contenedores', compute='_compute_totales',
        help="Suma de la foto de estados = total de contenedores del sistema.")
    clasificacion_total = fields.Integer(
        string='Total (clasificación)', compute='_compute_totales',
        help="Suma de la clasificación. Debe coincidir con el total de "
             "contenedores; si difiere, hay pares (contenedor+BL) repetidos "
             "como nuestros en el fichero.")

    @api.depends('estado_por_llegar', 'estado_arribado', 'estado_habilitado',
                 'estado_extraido', 'estado_retornado', 'nativos_count',
                 'consignados_count', 'cambio_importadora_count',
                 'otras_importadoras_count',
                 'otro_valor_count', 'sin_dato_count', 'no_en_fichero_count',
                 'otro_viaje_count', 'por_llegar_no_en_fichero_count',
                 'purgado_count')
    def _compute_totales(self):
        # cambio_importadora_count entra en la suma solo por los reportes
        # antiguos: en las corridas nuevas vale cero, igual que otro_viaje_count
        # vale cero en las viejas. Así ambos cuadran sin ramificar.
        for r in self:
            r.estado_total = (r.estado_por_llegar + r.estado_arribado
                              + r.estado_habilitado + r.estado_extraido
                              + r.estado_retornado)
            r.clasificacion_total = (r.nativos_count + r.consignados_count
                                     + r.cambio_importadora_count + r.otras_importadoras_count
                                     + r.otro_valor_count
                                     + r.sin_dato_count + r.no_en_fichero_count
                                     + r.otro_viaje_count
                                     + r.por_llegar_no_en_fichero_count
                                     + r.purgado_count)

    def action_generate_error_report(self, data=None):
        """Genera el reporte en Excel de líneas con error y devuelve la URL de descarga."""
        _logger.info("action_generate_error_report!!!!!!: %s", data)

        # Definir los campos que deseas incluir en el reporte
        columns = [
            ('No', 'index'),
            ('BL', 'bl_number'),
            ('Contenedor', 'container_number'),
            ('Fecha de Arribo', 'arrival_date'),
            ('Fecha DM', 'dm_date'),
            ('Fecha de Liberación', 'release_date'),
            ('Fecha Cita Previa', 'date_prior_to_appointment'),
            ('Fecha de Cita', 'appointment_date'),
            ('Fecha de Extracción', 'extraction_date'),
            ('Fecha de Devolución', 'return_date'),
        ]

        # Exporta los contenedores "no procesados" (nuevos: no estaban en el
        # sistema y se crearon desde el fichero), que es lo que interesa
        # revisar/completar. Las demás listas (errores, cambio, etc.) se ven
        # en las pestañas del formulario.
        lines = self.env['import.error.line'].search([
            ('log_id', '=', self.id),
            ('line_type', '=', 'nuevo'),
        ])

        if not lines:
            raise UserError("No hay contenedores nuevos (no procesados) en este reporte.")

        # Crear archivo temporal
        fd_worked_time, path_worked_time = tempfile.mkstemp()
        with os.fdopen(fd_worked_time, 'w', newline='') as tmp:
            workbook = xlwt.Workbook(tmp, {'in_memory': True})
            sheet = workbook.add_sheet('Reporte de Errores')

            # Definir estilos
            header_style = xlwt.easyxf("font: bold on; align: horiz center;")
            date_style = xlwt.easyxf("align: horiz center;")

            # Encabezado
            sheet.write(0, 0, "Reporte de Líneas con Error", header_style)
            sheet.write(1, 0, f"Log de Errores: {self.name}", date_style)

            # Escribir encabezados en negrita
            style_bold = xlwt.easyxf('font: bold 1; align: horiz center; borders: bottom thin;')
            for col_num, (header, _) in enumerate(columns):
                sheet.write(3, col_num, header, style_bold)

            # Escribir los datos de las líneas de error
            row = 4
            for row_num, line in enumerate(lines, start=1):
                for col_num, (_, field_name) in enumerate(columns):
                    value = getattr(line, field_name, '')

                    # Validar si el valor es una fecha y formatearla
                    if isinstance(value, datetime):
                        value = value.strftime('%Y-%m-%d')  # Formatear fecha
                    elif not value:
                        value = ''  # Si no hay valor, asignar cadena vacía

                    # Si el campo es el índice, agregarlo como número de fila
                    if field_name == 'index':
                        sheet.write(row_num + row, col_num, row_num)  # Número de fila como índice
                    else:
                        sheet.write(row_num + row, col_num, value)

            # Guardar el archivo
            workbook.save(path_worked_time)

        # Leer el archivo y convertirlo a base64
        with open(path_worked_time, 'rb') as file:
            file_data = base64.b64encode(file.read())

        # Nombre del archivo
        file_name = f"reporte_errores_{self.name}.xls"

        # Crear el adjunto
        attachment = self.env['ir.attachment'].create({
            'name': file_name,
            'mimetype': 'application/vnd.ms-excel',
            'datas': file_data,
            'res_model': 'import.error.log',
            'res_id': self.id,
        })
        _logger.info("Se generó el attachment: %s", attachment.name)

        # Devolver la URL de descarga
        return {
            'type': 'ir.actions.act_url',
            'url': f'/web/content/{attachment.id}?download=true',
            'target': 'new',
        }


class ImportErrorLine(models.Model):
    _name = 'import.error.line'
    _description = 'Línea con Error en la Importación'

    log_id = fields.Many2one('import.error.log', string='Log de Errores')
    line_number = fields.Integer(string='Número de Línea')
    line_type = fields.Selection([
        ('error', 'Con error de proceso'),
        ('nuevo', 'No procesado (nuevo, creado desde el fichero)'),
        ('cambio', 'Cambió a otra importadora'),
        ('no_fichero', 'En el sistema, no en el fichero'),
        ('otro_viaje', 'El contenedor sí, ese viaje no'),
        ('por_llegar', 'Todavía por llegar'),
        ('purgado', 'Dejó de venir en el reporte'),
        ('duplicado', 'Duplicado a unificar'),
        ('otro_valor', 'Otro valor, ya en el sistema'),
        ('sin_dato', 'Sin dato, ya en el sistema'),
        ('cuarentena', 'En cuarentena: BL demasiado corto para desempatar'),
        ('otra_importadora', 'Otra importadora del catálogo'),
    ], string='Tipo', default='error')
    error_message = fields.Text(string='Mensaje de Error')
    data = fields.Text(string='Datos de la Línea')

    container_number = fields.Char(string='Número de Contenedor')
    bl_number = fields.Char(string='Número de BL')

    arrival_date = fields.Datetime(string='Fecha de Llegada')
    release_date = fields.Datetime(string='Fecha de Liberación')
    extraction_date = fields.Datetime(string='Fecha de Extracción')
    return_date = fields.Datetime(string='Fecha de Retorno')
    date_prior_to_appointment = fields.Datetime(string='Fecha de Pre-Cita')
    appointment_date = fields.Datetime(string='Fecha de Cita')
    dm_date = fields.Datetime(string='Fecha DM')
