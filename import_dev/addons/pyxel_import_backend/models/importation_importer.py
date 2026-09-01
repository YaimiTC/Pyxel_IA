from datetime import date

from odoo import api, models, fields

# Semilla de tcm_match_name / tcm_sync_start_date para las importadoras
# que ya existian antes de este campo (data/importation_importer_data.xml
# es noupdate="1", asi que un <field> nuevo en esos <record> no se les
# aplica solo). None en la fecha = ENETEC, sin restriccion (comportamiento
# de siempre). Las demas arrancan el 1-jul-2026 porque su historial
# anterior nunca se proceso por este sistema. COREYDAN y TRADECEN se
# dejan sin tcm_match_name: nunca se confirmo como las escribe la
# Terminal, hace falta verlas en un reporte real antes de adivinar.
SEMILLA_TCM = {
    'importation_importer_enetec': ('ENETEC S.A', None),
    'importation_importer_einarbo': ('EINARBO S.A', date(2026, 7, 1)),
    'importation_importer_promax': ('PROMAX S.A', date(2026, 7, 1)),
    'importation_importer_enersa': ('ENERSA. EMPRESA DE ENERGIA  SA', date(2026, 7, 1)),
    'importation_importer_emserpet': ('EMSERPET', date(2026, 7, 1)),
}


class ImportationImporter(models.Model):
    _name = 'importation.importer'
    _description = 'Empresa importadora que gestiona la operacion'
    _order = 'name'

    name = fields.Char(string='Name', required=True)
    active = fields.Boolean(string='Active', default=True)
    logo = fields.Image(string='Logo', max_width=1024, max_height=1024)

    vat = fields.Char(string='NIT')
    registro_comercial = fields.Char(string='No. Inscripción Registro Comercial')
    registro_mercantil = fields.Char(string='No. Inscripción Registro Mercantil')
    street = fields.Char(string='Dirección')
    phone = fields.Char(string='Teléfono')
    email = fields.Char(string='Email')
    bank_account_usd = fields.Char(string='Cuenta Bancaria USD')
    bank_account_cup = fields.Char(string='Cuenta Bancaria CUP')

    tcm_match_name = fields.Char(
        string='Nombre en el TCM',
        help='Texto a buscar (contiene, no exacto) en las columnas H y J '
             'del reporte del TCM para reconocer contenedores de esta '
             'importadora. El TCM no siempre escribe el nombre igual que '
             'aqui (mayusculas, puntuacion, abreviaturas), por eso es un '
             'campo aparte y no se usa "name" directamente.')
    tcm_sync_start_date = fields.Date(
        string='Sincronizar contenedores nuevos desde',
        help='Solo se CREAN contenedores nuevos de esta importadora si su '
             'fecha de llegada (arrival_date) es igual o posterior a esta '
             'fecha -- para no volcar de golpe todo el historial viejo de '
             'una importadora que se acaba de incorporar al sistema. Vacio '
             '= sin restriccion (crea desde cualquier fecha). Un '
             'contenedor que YA existe en el sistema se sigue '
             'actualizando siempre, sin importar esta fecha.')

    _sql_constraints = [
        ('name_uniq', 'unique(name)', 'Esta importadora ya existe.'),
    ]

    @api.model
    def _seed_tcm_match_names(self):
        """Se llama desde un <function> de datos (corre en cada -u, a
        diferencia de post_init_hook que solo dispara en instalacion
        nueva). Solo rellena lo que este vacio, para no pisar un ajuste
        manual posterior."""
        for xmlid, (patron, desde) in SEMILLA_TCM.items():
            importer = self.env.ref('pyxel_import_backend.%s' % xmlid, raise_if_not_found=False)
            if not importer:
                continue
            if not importer.tcm_match_name:
                importer.tcm_match_name = patron
            if not importer.tcm_sync_start_date and desde:
                importer.tcm_sync_start_date = desde
