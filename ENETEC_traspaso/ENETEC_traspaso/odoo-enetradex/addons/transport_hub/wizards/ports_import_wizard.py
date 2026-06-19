from odoo import models, fields, api, _
from odoo.exceptions import UserError
import csv
import logging
import base64

_logger = logging.getLogger(__name__)


class TransportHubImportWizard(models.TransientModel):
    _name = 'transport.hub.import.wizard'
    _description = 'Import Ports from CSV'

    csv_file = fields.Binary(string='CSV File', required=True)
    filename = fields.Char(string='File Name')

    def _get_country_by_value(self, value):
        """Busca país por código ISO o nombre (ignorando idioma activo)."""
        if not value:
            return None

        # Búsqueda por código (ej. 'US', 'FR', etc.)
        country = self.env['res.country'].search([('code', '=', value.upper())], limit=1)
        if country:
            return country

        # Búsqueda por nombre (forzando contexto en inglés)
        country = self.env['res.country'].with_context(lang='en_US').search([('name', '=', value)], limit=1)
        return country

    def action_process_csv(self):
        self.ensure_one()
        if not self.csv_file:
            raise UserError(_("Please upload a CSV file."))

        content = base64.b64decode(self.csv_file)
        decoded = content.decode('utf-8').splitlines()
        reader = csv.DictReader(decoded)

        for row in reader:
            raw_country = row.get('Country Code')
            country = self._get_country_by_value(raw_country)

            if not country:
                _logger.info(f"País no encontrado: {raw_country}")
                continue

            code = row.get('World Port Index Number')
            name = row.get('Main Port Name')

            if not code or not name:
                _logger.warning(f"Fila incompleta: {row}")
                continue

            domain = [('code', '=', code), ('country_id', '=', country.id)]
            existing = self.env['transport.hub'].search(domain, limit=1)

            vals = {
                'name': name,
                'code': code,
                'un_locode': row.get('UN/LOCODE') or False,
                'latitude': float(row.get('Latitude', '0.0')),
                'longitude': float(row.get('Longitude', '0.0')),
                'hub_type': 'Port',
                'country_id': country.id,
            }

            if existing:
                existing.write(vals)
            else:
                self.env['transport.hub'].create(vals)
