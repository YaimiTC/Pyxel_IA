from odoo import models, fields


class ImportationDestination(models.Model):
    _name = 'importation.destination'
    _description = 'Destino del contenedor'
    _order = 'name'

    name = fields.Char(string='Name', required=True)
    active = fields.Boolean(string='Active', default=True)
    is_own_destination = fields.Boolean(
        string='Es "Propio"',
        help="Marca la opción especial 'Propio': al elegirla en el "
             "contenedor se habilita un texto libre para que comercial "
             "describa el destino propio del cliente.")
    province = fields.Char(
        string='Provincia (para autocompletar)',
        help="Nombre de provincia normalizado (mayúsculas, sin acentos) tal "
             "como llega en el campo 'Province' del contenedor. Se usa para "
             "sugerir este destino automáticamente. Si dos destinos tienen "
             "la misma provincia, no se autoselecciona ninguno.")
    external_id = fields.Char(
        string='Código externo (SIOC)',
        help="idUnidadFuncional del nomenclador oficial SIOC. Sirve para "
             "reconciliar contra ese documento sin depender del nombre.")
    email = fields.Char(
        string='Correo',
        help="Correo de contacto de este destino, para el envío automático "
             "de reportes.")

    _sql_constraints = [
        ('name_uniq', 'unique(name)', 'Este destino ya existe.'),
        ('external_id_uniq', 'unique(external_id)', 'Este código externo ya existe.'),
    ]
