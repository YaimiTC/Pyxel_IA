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
    otro_valor_lines = fields.One2many(
        'import.error.line', 'log_id', string='Otro valor, ya en el sistema',
        domain=[('line_type', '=', 'otro_valor')])
    sin_dato_lines = fields.One2many(
        'import.error.line', 'log_id', string='Sin dato, ya en el sistema',
        domain=[('line_type', '=', 'sin_dato')])
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
        help="Filas donde H o J tienen otra empresa (no la nuestra), el "
             "contenedor+BL ya existe en nuestro sistema, y ya venía así de "
             "corridas anteriores (la marca 'nuestro' ya estaba apagada).")
    cambio_importadora_count = fields.Integer(
        string='Cambió a otra importadora',
        help="Contenedores que en corridas anteriores venían como nuestros y "
             "en ESTA corrida aparecen por primera vez asignados a otra "
             "importadora. Es el evento del cambio — revisando el log se ve "
             "el día exacto en que dejó de salir como nuestro. Ver la lista.")
    no_en_fichero_count = fields.Integer(
        string='En el sistema, no en el fichero',
        help="Contenedores que están en nuestro sistema pero cuyo "
             "contenedor+BL no aparece en el fichero de esta corrida: o aún "
             "no arribó, o hay un error en el BL/número que impidió el match. "
             "Ver la lista.")
    sin_dato_count = fields.Integer(
        string='Sin dato, ya en el sistema',
        help="Filas donde H y J vienen vacías, pero el contenedor+BL ya "
             "existe en nuestro sistema.")
    nuevos_count = fields.Integer(
        string='Contenedores no procesados (nuevos)',
        help="Contenedores nuestros (nativo/consignado) que venían en el "
             "fichero y NO existían en el sistema: la corrida los creó. Se "
             "listan para revisarlos/completarlos. Es un subconjunto de "
             "nativos+consignados (no suma aparte).")
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
                 'otro_valor_count', 'sin_dato_count', 'no_en_fichero_count')
    def _compute_totales(self):
        for r in self:
            r.estado_total = (r.estado_por_llegar + r.estado_arribado
                              + r.estado_habilitado + r.estado_extraido
                              + r.estado_retornado)
            r.clasificacion_total = (r.nativos_count + r.consignados_count
                                     + r.cambio_importadora_count + r.otro_valor_count
                                     + r.sin_dato_count + r.no_en_fichero_count)

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
        ('otro_valor', 'Otro valor, ya en el sistema'),
        ('sin_dato', 'Sin dato, ya en el sistema'),
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
