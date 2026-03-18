import base64
from datetime import datetime

import pandas as pd
import unicodedata
from odoo import models, fields
from io import StringIO
import logging

_logger = logging.getLogger(__name__)


class ImportWizard(models.TransientModel):
    _name = 'import.wizard'
    _description = 'Import Wizard'

    file = fields.Binary('Archivo Excel', required=True)
    filename = fields.Char()

    def clean_text(self, text):
        if pd.isna(text):
            return ''
        if not isinstance(text, str):
            text = str(text)
        text = unicodedata.normalize("NFKC", text)
        return text.strip()

    def normalize_compare_text(self, text):
        text = self.clean_text(text or '')
        return ' '.join(text.lower().split())

    def _parse_date(self, value):
        if pd.isna(value):
            return False
        return pd.to_datetime(value, dayfirst=True, errors='coerce')

    def _get_company_importadora_name(self):
        return self.normalize_compare_text(
            self.env.company.importadora_name or ''
        )

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
            # Si el archivo NO trae encabezados, cambia a header=None
            df = pd.read_csv(StringIO(decoded_file), sep=";")
            # df = pd.read_csv(StringIO(decoded_file), sep=";", header=None)
        except Exception as e:
            _logger.error("[IMPORT] Error al leer el archivo: %s", e)
            return

        config_importadora = self._get_company_importadora_name()

        for row_idx, row in df.iterrows():
            container = None
            vals_update = {}
            error_columns = {}
            container_number = ''
            bl = ''
            importadora_name = ''

            try:
                container_number = self.clean_text(row.iloc[0])
                bl = self.clean_text(row.iloc[2])

                # Columna H en Excel = índice 7 en pandas
                if len(row) > 7 and pd.notna(row.iloc[7]):
                    importadora_name = self.clean_text(row.iloc[7])

                _logger.info(
                    "[IMPORT] Procesando fila %s: Contenedor=%s, BL=%s, Importadora(H)=%s, Empresa=%s",
                    row_idx + 1,
                    container_number,
                    bl,
                    importadora_name,
                    self.env.company.display_name,
                )

                # Si la empresa activa tiene importadora configurada, filtra por ella
                # Si no tiene valor, procesa todo
                if config_importadora:
                    row_importadora = self.normalize_compare_text(importadora_name)
                    if row_importadora != config_importadora:
                        _logger.info(
                            "[IMPORT] Fila %s omitida. Importadora archivo='%s' != configurada empresa='%s'",
                            row_idx + 1,
                            importadora_name,
                            self.env.company.importadora_name,
                        )
                        continue

                container = self.env['importation.load'].with_context(lang='es_419').search([
                    ('name', '=', container_number),
                    ('importation_id.purchase_condition_number', '=', bl)
                ], limit=1)

                if not container:
                    _logger.warning(
                        "[IMPORT] Contenedor no encontrado: %s con BL %s",
                        container_number, bl
                    )
                    self.env['import.error.line'].create({
                        'log_id': log.id,
                        'line_number': row_idx + 1,
                        'error_message': f"Contenedor '{container_number}' con BL '{bl}' no encontrado.",
                        'data': str(row),
                        'container_number': container_number,
                        'bl_number': bl,
                    })
                    continue

                # Índices pandas (0-based)
                mapeo_columnas = {
                    3: ('transit_agency', lambda v: self.clean_text(v)),
                    4: ('cargo_type', lambda v: 'reefer' if self.normalize_compare_text(v) == 'si' else 'dry'),
                    5: ('arrival_date', self._parse_date),
                    10: ('release_date', self._parse_date),
                    11: ('pre_appointment_date', self._parse_date),
                    12: ('appointment_date', self._parse_date),
                    13: ('extraction_date', self._parse_date),
                    14: ('transport_company', lambda v: self.clean_text(v)),
                    15: ('truck_plate', lambda v: self.clean_text(v)),
                    16: ('province', lambda v: self.clean_text(v)),
                    17: ('return_date', self._parse_date),
                }

                for col_idx, (field_name, transform) in mapeo_columnas.items():
                    try:
                        if len(row) <= col_idx:
                            error_columns[field_name] = f"Columna {col_idx + 1} no existe en el archivo"
                            continue

                        raw_value = row.iloc[col_idx]
                        if pd.isna(raw_value):
                            continue

                        value = transform(raw_value)

                        if pd.isna(value):
                            error_columns[field_name] = f"Columna {col_idx + 1} inválida"
                            continue

                        if value not in (False, '', None):
                            vals_update[field_name] = value

                    except Exception:
                        error_columns[field_name] = f"Columna {col_idx + 1} inválida"

                if vals_update:
                    _logger.info(
                        "[IMPORT] Actualizando contenedor %s con %s",
                        container_number, vals_update
                    )
                    container.with_context(skip_date_check=True).write(vals_update)

                if error_columns:
                    _logger.warning(
                        "[IMPORT] Campos no procesados para contenedor %s: %s",
                        container_number, list(error_columns.keys())
                    )
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