# -*- coding: utf-8 -*-
import base64
import csv
import io
from datetime import timedelta

from odoo import models, fields
from odoo.exceptions import UserError


class ImportDepositWizard(models.TransientModel):
    _name = 'import.deposit.wizard'
    _description = 'Sincronización de Depósito'

    file = fields.Binary('Archivo', required=True)
    filename = fields.Char()

    def import_deposit_from_file(self):
        """Lee el MISMO csv que genera action_export_deposit_package (ver
        importation.load): las primeras 12 columnas las puso Pyxel, las 7
        de retorno (codigo_deposito, cantidad_recibida, fecha_recepcion,
        fecha_inicio_descarga, fecha_fin_descarga, observaciones,
        certificado_calidad) las llena el deposito y nos las devuelve en
        el mismo fichero. Se empareja por (contenedor, bl) -- ya no hace
        falta el cruce BL-canonico de la Terminal porque es el mismo
        fichero que salio, no uno externo con su propio formato.

        Deja un deposit.sync.log persistente (igual que import.error.log
        para la Terminal) con lo que se sincronizo y lo que no, para poder
        revisarlo despues en Reportes de Sincronizacion (Deposito)."""
        self.ensure_one()
        try:
            texto = base64.b64decode(self.file).decode('utf-8-sig')
        except Exception as e:
            raise UserError(f"No se pudo leer el archivo: {e}")

        filas = list(csv.reader(io.StringIO(texto), delimiter=';'))
        if not filas:
            raise UserError("El archivo está vacío.")
        header = filas[0]
        requeridas = ['contenedor', 'bl', 'codigo_deposito', 'cantidad_recibida',
                      'fecha_recepcion', 'fecha_inicio_descarga', 'fecha_fin_descarga',
                      'observaciones', 'certificado_calidad']
        faltan = [c for c in requeridas if c not in header]
        if faltan:
            raise UserError(
                "El archivo no tiene las columnas esperadas (falta: %s). "
                "Debe ser el mismo CSV que se exportó desde 'Exportar para Depósito', "
                "con las columnas de retorno llenas." % ', '.join(faltan)
            )
        idx = {c: header.index(c) for c in requeridas}

        Load = self.env['importation.load']

        def parse_datetime(v):
            v = (v or '').strip()
            if not v:
                return False
            try:
                return fields.Datetime.to_datetime(v)
            except Exception:
                return False

        lineas_log = []
        actualizados = sin_datos_retorno = 0
        for fila in filas[1:]:
            if len(fila) < len(header):
                continue
            contenedor = fila[idx['contenedor']].strip()
            bl = fila[idx['bl']].strip()
            if not contenedor:
                continue
            retorno = {
                'deposit_code': fila[idx['codigo_deposito']].strip(),
                'deposit_quantity_received': fila[idx['cantidad_recibida']].strip(),
                'deposit_reception_datetime': fila[idx['fecha_recepcion']].strip(),
                'deposit_unload_start_datetime': fila[idx['fecha_inicio_descarga']].strip(),
                'deposit_unload_end_datetime': fila[idx['fecha_fin_descarga']].strip(),
                'deposit_observations': fila[idx['observaciones']].strip(),
                'deposit_quality_certificate_number': fila[idx['certificado_calidad']].strip(),
            }
            if not any(retorno.values()):
                sin_datos_retorno += 1
                continue

            load = Load.search([('name', '=', contenedor), ('bl_number', '=', bl)], limit=1)
            if not load:
                lineas_log.append((0, 0, {
                    'container_number': contenedor, 'bl_number': bl,
                    'line_type': 'no_encontrado',
                    'message': 'No existe un contenedor con ese BL en Pyxel.',
                }))
                continue

            vals = {}
            if retorno['deposit_code']:
                vals['deposit_code'] = retorno['deposit_code']
            if retorno['deposit_quantity_received']:
                try:
                    vals['deposit_quantity_received'] = float(retorno['deposit_quantity_received'])
                except ValueError:
                    pass
            for campo in ('deposit_reception_datetime', 'deposit_unload_start_datetime',
                          'deposit_unload_end_datetime'):
                dt = parse_datetime(retorno[campo])
                if dt:
                    vals[campo] = dt
            if retorno['deposit_observations']:
                vals['deposit_observations'] = retorno['deposit_observations']
            if retorno['deposit_quality_certificate_number']:
                vals['deposit_quality_certificate_number'] = retorno['deposit_quality_certificate_number']

            if vals:
                load.write(vals)
                actualizados += 1
                lineas_log.append((0, 0, {
                    'container_number': contenedor, 'bl_number': bl,
                    'line_type': 'actualizado',
                    'message': 'Actualizado con los datos de recepción.',
                }))

        # Lo que se mando hace mas de 3 dias (extraido del puerto) y todavia
        # no tiene codigo de deposito: candidato a "no se sincronizo".
        hace_3_dias = fields.Date.context_today(self) - timedelta(days=3)
        atrasados_recs = Load.search([
            ('extraction_date', '!=', False),
            ('extraction_date', '<', hace_3_dias),
            ('deposit_code', '=', False),
            ('state', 'not in', ['to_return', 'returned']),
        ])
        for rec in atrasados_recs:
            lineas_log.append((0, 0, {
                'container_number': rec.name, 'bl_number': rec.bl_number or '',
                'line_type': 'atrasado',
                'message': f'Extraído el {rec.extraction_date}, todavía sin código de depósito.',
            }))

        no_encontrados_count = sum(1 for l in lineas_log if l[2]['line_type'] == 'no_encontrado')
        log = self.env['deposit.sync.log'].create({
            'name': f'Sincronización {fields.Datetime.now()}',
            'filename': self.filename,
            'import_file': self.file,
            'total_filas_count': actualizados + no_encontrados_count,
            'actualizados_count': actualizados,
            'sin_datos_count': sin_datos_retorno,
            'no_encontrados_count': no_encontrados_count,
            'atrasados_count': len(atrasados_recs),
            'line_ids': lineas_log,
        })

        return {
            'type': 'ir.actions.act_window',
            'res_model': 'deposit.sync.log',
            'res_id': log.id,
            'view_mode': 'form',
            'target': 'current',
        }
