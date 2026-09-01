# -*- coding: utf-8 -*-
from odoo import models, fields


class DepositSyncLog(models.Model):
    _name = 'deposit.sync.log'
    _description = 'Log de Sincronización de Depósito'
    _order = 'import_date desc, id desc'

    name = fields.Char(string='Nombre del Archivo', required=True)
    import_date = fields.Datetime(string='Fecha de Sincronización', default=fields.Datetime.now)
    filename = fields.Char(string='Fichero')
    import_file = fields.Binary(string='Archivo')

    total_filas_count = fields.Integer(string='Filas con datos de retorno')
    actualizados_count = fields.Integer(string='Actualizados')
    sin_datos_count = fields.Integer(string='Sin columnas de retorno llenas')
    no_encontrados_count = fields.Integer(string='No emparejados')
    atrasados_count = fields.Integer(
        string='Extraídos hace +3 días sin sincronizar',
        help="Contenedores que ya salieron del puerto hace mas de 3 dias y "
             "todavia no tienen codigo de deposito -- deberian haber "
             "sincronizado y no lo hicieron.")

    line_ids = fields.One2many('deposit.sync.line', 'log_id', string='Líneas')
    actualizado_lines = fields.One2many(
        'deposit.sync.line', 'log_id', string='Actualizados',
        domain=[('line_type', '=', 'actualizado')])
    no_encontrado_lines = fields.One2many(
        'deposit.sync.line', 'log_id', string='No emparejados',
        domain=[('line_type', '=', 'no_encontrado')])
    atrasado_lines = fields.One2many(
        'deposit.sync.line', 'log_id', string='Atrasados (+3 días sin sincronizar)',
        domain=[('line_type', '=', 'atrasado')])


class DepositSyncLine(models.Model):
    _name = 'deposit.sync.line'
    _description = 'Línea del Log de Sincronización de Depósito'

    log_id = fields.Many2one('deposit.sync.log', string='Log', required=True, ondelete='cascade')
    container_number = fields.Char(string='Contenedor')
    bl_number = fields.Char(string='BL')
    line_type = fields.Selection([
        ('actualizado', 'Actualizado'),
        ('no_encontrado', 'No emparejado'),
        ('atrasado', 'Atrasado (+3 días sin sincronizar)'),
    ], string='Tipo', required=True)
    message = fields.Char(string='Detalle')
