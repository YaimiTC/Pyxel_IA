import base64
from datetime import datetime, timedelta

import openpyxl as openpyxl
import pandas as pd
import unicodedata
from odoo import models, fields, api, _
import xlrd
from io import BytesIO, StringIO
import logging

from requests.compat import chardet

_logger = logging.getLogger(__name__)


class ImportWizard(models.TransientModel):
    _name = 'import.wizard'
    _description = 'Import Wizard'

    file = fields.Binary('Archivo Excel', required=True)
    filename = fields.Char()

    def clean_text(self, text):
        if not isinstance(text, str):
            text = str(text)
        text = unicodedata.normalize("NFKC", text)
        return text.strip()

    def import_data_from_excel(self):
        self.ensure_one()
        if not self.file:
            return

        log = self.env['import.error.log'].create({
            'name': self.filename,
            'import_date': datetime.now()
        })

        try:
            decoded_file = base64.b64decode(self.file).decode("utf-8")
            df = pd.read_csv(StringIO(decoded_file), sep=";")
        except Exception as e:
            _logger.error("[IMPORT] Error al leer el archivo: %s", e)
            return

        for row_idx, row in df.iterrows():
            container = None
            vals_update = {}
            error_columns = {}
            container_number = ''
            bl = ''

            try:
                container_number = self.clean_text(row.iloc[0])
                bl = self.clean_text(row.iloc[2])

                _logger.info("[IMPORT] Procesando fila %s: Contenedor=%s, BL=%s", row_idx + 1, container_number, bl)

                container = self.env['importation.load'].search([
                    ('name', '=', container_number),
                    ('importation_id.purchase_condition_number', '=', bl)
                ], limit=1)

                if not container:
                    _logger.warning("[IMPORT] Contenedor no encontrado: %s con BL %s", container_number, bl)
                    self.env['import.error.line'].create({
                        'log_id': log.id,
                        'line_number': row_idx + 1,
                        'error_message': f"Contenedor '{container_number}' con BL '{bl}' no encontrado.",
                        'data': str(row),
                        'container_number': container_number,
                        'bl_number': bl,
                    })
                    continue

                # Mapeo: índice de columna → campo real en el modelo
                mapeo_columnas = {
                    3: ('transit_agency', str),
                    4: ('cargo_type', lambda v: 'reefer' if str(v).strip().lower() == 'si' else 'dry'),
                    5: ('arrival_date', pd.to_datetime),
                    10: ('release_date', pd.to_datetime),
                    11: ('pre_appointment_date', pd.to_datetime),
                    12: ('appointment_date', pd.to_datetime),
                    13: ('extraction_date', pd.to_datetime),
                    14: ('transport_company', str),
                    15: ('truck_plate', str),
                    16: ('province', str),
                    17: ('return_date', pd.to_datetime),
                }

                for col_idx, (field, transform) in mapeo_columnas.items():
                    try:
                        val = row.iloc[col_idx]
                        if pd.isna(val):
                            continue
                        val = transform(val)
                        vals_update[field] = val
                    except Exception:
                        error_columns[field] = f"Columna {col_idx} inválida"

                # Si hay datos válidos, se actualiza
                if vals_update:
                    _logger.info("[IMPORT] Actualizando contenedor %s con %s", container_number, vals_update)
                    container.write(vals_update)

                # Si hay columnas con error, se registra
                if error_columns:
                    _logger.warning("[IMPORT] Campos no procesados para contenedor %s: %s", container_number,
                                    list(error_columns.keys()))
                    self.env['import.error.line'].create({
                        'log_id': log.id,
                        'line_number': row_idx + 1,
                        'error_message': str(error_columns),
                        'data': str(row),
                        'container_number': container_number,
                        'bl_number': bl,
                        'arrival_date': vals_update.get('arrival_date'),
                        'release_date': vals_update.get('release_date'),
                        'extraction_date': vals_update.get('extraction_date'),
                        'return_date': vals_update.get('return_date'),
                        'date_prior_to_appointment': vals_update.get('pre_appointment_date'),
                        'appointment_date': vals_update.get('appointment_date'),
                    })

            except Exception as e:
                _logger.exception("[IMPORT] Error inesperado en fila %s: %s", row_idx + 1, e)
                self.env['import.error.line'].create({
                    'log_id': log.id,
                    'line_number': row_idx + 1,
                    'error_message': str(e),
                    'data': str(row),
                    'container_number': container_number,
                    'bl_number': bl,
                })

        return {'type': 'ir.actions.act_window_close'}



