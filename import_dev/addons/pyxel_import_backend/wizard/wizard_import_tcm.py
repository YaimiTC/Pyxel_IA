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

    def _parse_cargo_type(self, value):
        text = self.normalize_compare_text(value)
        return 'reefer' if text in ('si', 'sí', 'yes', 'true') else 'dry'

    def _compute_release_date(self, row):
        """Fecha de liberación del contenedor: hay tres procesos de
        liberación (aduana=DM, naviera=Master BL, importadora=traspaso del
        contenedor). Es condición tenerlos TODOS los que apliquen — si
        falta alguno, el contenedor no está completamente liberado
        todavía y no se pone fecha. Aduana (DM, col 10) y naviera
        (LIB_MBL, col 6) son siempre obligatorios; importadora (LIB_CONT,
        col 8) solo se exige si hubo traspaso (CONSIGN_LIB_CONT, col 9,
        con dato). La fecha final es la MAS RECIENTE entre las que
        aplican, porque la liberación solo se completa cuando termina la
        última de ellas."""
        if len(row) <= 10:
            return False

        dm_date = self._parse_date(row.iloc[10]) if pd.notna(row.iloc[10]) else False
        if not dm_date or pd.isna(dm_date):
            return False  # sin DM (aduana) no hay liberación

        mbl_date = self._parse_date(row.iloc[6]) if len(row) > 6 and pd.notna(row.iloc[6]) else False
        if not mbl_date or pd.isna(mbl_date):
            return False  # sin liberación naviera tampoco está completo

        candidatas = [dm_date, mbl_date]

        hubo_traspaso = len(row) > 9 and pd.notna(row.iloc[9]) and self.clean_text(row.iloc[9])
        if hubo_traspaso:
            cont_date = self._parse_date(row.iloc[8]) if len(row) > 8 and pd.notna(row.iloc[8]) else False
            if not cont_date or pd.isna(cont_date):
                return False  # hubo traspaso pero falta su fecha: incompleto
            candidatas.append(cont_date)

        return max(candidatas)

    def _get_company_importadora_name(self):
        return self.normalize_compare_text(
            self.env.company.importadora_name or ''
        )

    def import_data_from_excel(self):
        self.ensure_one()
        if not self.file:
            return

        log = self.env['import.error.log'].create({
            'name': f"Reporte {datetime.now().strftime('%d-%m-%Y %H:%M')}",
            'import_date': datetime.now()
        })

        try:
            decoded_file = base64.b64decode(self.file).decode("utf-8-sig")
            # Distintas exportaciones de la Terminal usan ';' o ',' como
            # separador — se detecta por la primera línea en vez de asumir uno fijo.
            first_line = decoded_file.split("\n", 1)[0]
            sep = ";" if first_line.count(";") >= first_line.count(",") else ","
            # Si el archivo NO trae encabezados, cambia a header=None
            df = pd.read_csv(StringIO(decoded_file), sep=sep)
            # df = pd.read_csv(StringIO(decoded_file), sep=sep, header=None)
        except Exception as e:
            _logger.error("[IMPORT] Error al leer el archivo: %s", e)
            return

        config_importadora = self._get_company_importadora_name()

        # Contenedores (contenedor, BL) ya existentes en el sistema,
        # precargados una sola vez (no dentro del bucle) para poder clasificar
        # "cambió / otro valor / sin dato" sin lanzar una consulta por cada una
        # de las miles de filas de otros clientes que comparten este mismo
        # reporte de la Terminal. Se guarda id y la marca belongs_to_us de cada
        # uno para distinguir "cambió a otra importadora" (venía como nuestro)
        # de "otro valor" (ya venía de antes con otra).
        existing_info = {
            (r['name'], r['bl_number']): {'id': r['id'], 'ours': r['belongs_to_us']}
            for r in self.env['importation.load'].search_read(
                [], ['name', 'bl_number', 'belongs_to_us'])
            if r['bl_number']
        }
        existing_pairs = set(existing_info.keys())

        # Todos los pares (contenedor, BL) que trae el fichero de esta corrida
        # (de CUALQUIER importadora), para al final detectar cuáles de los
        # nuestros NO aparecieron en el fichero.
        file_pairs = set()

        contadores = {
            'arribados_count': 0,
            'habilitados_count': 0,
            'liberados_count': 0,
            'extraidos_count': 0,
            'devueltos_count': 0,
            'nativos_count': 0,
            'consignados_count': 0,
            'cambio_importadora_count': 0,
            'otro_valor_count': 0,
            'no_en_fichero_count': 0,
            'sin_dato_count': 0,
            'nuevos_count': 0,
            'total_filas_count': len(df),
        }

        for row_idx, row in df.iterrows():
            container = None
            vals_update = {}
            error_columns = {}
            container_number = ''
            bl = ''
            importadora_name = ''
            master_bl = ''

            try:
                container_number = self.clean_text(row.iloc[0])
                bl = self.clean_text(row.iloc[2])
                if len(row) > 1 and pd.notna(row.iloc[1]):
                    master_bl = self.clean_text(row.iloc[1])

                # Registrar el par de esta fila como "presente en el fichero"
                # (aunque luego se omita por ser de otra importadora): así, al
                # final, sabemos cuáles contenedores nuestros NO vinieron.
                if bl:
                    file_pairs.add((container_number, bl))

                # Columna H (idx 7, Nativo/Master BL) y columna J (idx 9,
                # Consignado/traspaso) en pandas.
                if len(row) > 7 and pd.notna(row.iloc[7]):
                    importadora_name = self.clean_text(row.iloc[7])
                consignado_name = self.clean_text(row.iloc[9]) if len(row) > 9 and pd.notna(row.iloc[9]) else ''

                # Clasificación de la fila (Nativo/Consignado/Otro/Sin dato)
                # para el resumen de la corrida — Nativos/Consignados se
                # cuentan sobre TODAS las filas leídas (son el filtro que
                # decide si procesamos la fila). Otro valor/Sin dato en
                # cambio solo cuentan si el contenedor (mismo par
                # contenedor+BL) YA existe en nuestro sistema: el resto son
                # filas de otros clientes que comparten este mismo reporte
                # de la Terminal y no nos interesan. Cuando SÍ existe pero H/J
                # no dice ENETEC, es una alerta real: o la Terminal lo tiene
                # atribuido a otro por error, o todavía no se ha hecho la
                # consignación/traspaso a nuestro nombre.
                es_nativo_row = self.normalize_compare_text(importadora_name) == config_importadora if config_importadora else bool(importadora_name)
                es_consignado_row = self.normalize_compare_text(consignado_name) == config_importadora if config_importadora else bool(consignado_name)
                if es_nativo_row:
                    contadores['nativos_count'] += 1
                elif es_consignado_row:
                    contadores['consignados_count'] += 1
                elif (container_number, bl) in existing_pairs:
                    if importadora_name or consignado_name:
                        # En el sistema pero ahora con otra empresa. Si venía
                        # como nuestro (marca en True) es el CAMBIO de esta
                        # corrida; si no, ya venía así de antes ('otro valor').
                        info = existing_info[(container_number, bl)]
                        if info['ours']:
                            contadores['cambio_importadora_count'] += 1
                            self.env['importation.load'].browse(info['id']).with_context(
                                skip_date_check=True).write({'belongs_to_us': False})
                            info['ours'] = False
                            self.env['import.error.line'].create({
                                'log_id': log.id,
                                'line_number': row_idx + 1,
                                'line_type': 'cambio',
                                'container_number': container_number,
                                'bl_number': bl,
                                'error_message': (
                                    f"Antes venía como nuestro; ahora aparece como "
                                    f"H='{importadora_name}' / J='{consignado_name}'."),
                            })
                        else:
                            contadores['otro_valor_count'] += 1
                            self.env['import.error.line'].create({
                                'log_id': log.id,
                                'line_number': row_idx + 1,
                                'line_type': 'otro_valor',
                                'container_number': container_number,
                                'bl_number': bl,
                                'error_message': (
                                    f"Ya venía con otra empresa de antes. "
                                    f"H='{importadora_name}' / J='{consignado_name}'."),
                            })
                    else:
                        contadores['sin_dato_count'] += 1
                        self.env['import.error.line'].create({
                            'log_id': log.id,
                            'line_number': row_idx + 1,
                            'line_type': 'sin_dato',
                            'container_number': container_number,
                            'bl_number': bl,
                            'error_message': (
                                "En el sistema, pero el fichero trae H y J vacías."),
                        })

                _logger.info(
                    "[IMPORT] Procesando fila %s: Contenedor=%s, BL=%s, Nativo(H)=%s, Consignado(J)=%s, Empresa=%s",
                    row_idx + 1,
                    container_number,
                    bl,
                    importadora_name,
                    consignado_name,
                    self.env.company.display_name,
                )

                # Si la empresa activa tiene importadora configurada, filtra:
                # se procesa la fila si es Nativo (H) O Consignado (J) a esa
                # empresa. Si no tiene valor configurado, procesa todo.
                if config_importadora:
                    es_nativo = self.normalize_compare_text(importadora_name) == config_importadora
                    es_consignado = self.normalize_compare_text(consignado_name) == config_importadora
                    if not es_nativo and not es_consignado:
                        _logger.info(
                            "[IMPORT] Fila %s omitida. H='%s' / J='%s' != empresa configurada '%s'",
                            row_idx + 1,
                            importadora_name,
                            consignado_name,
                            self.env.company.importadora_name,
                        )
                        continue

                    # La fila pasó el filtro: viene a nuestro nombre. Se deja la
                    # marca en True para que, si en una corrida futura aparece
                    # con otra importadora, se detecte como 'cambió'.
                    vals_update['belongs_to_us'] = True

                # La Terminal es la fuente más confiable de este dato: el
                # match es SIEMPRE por (contenedor + BL) juntos, nunca por
                # contenedor solo — el mismo contenedor se reutiliza en
                # embarques distintos con BL distinto.
                container = self.env['importation.load'].with_context(lang='es_419').search([
                    ('name', '=', container_number),
                    ('bl_number', '=', bl),
                ], limit=1) if bl else self.env['importation.load']

                # Estado ANTES de tocar el contenedor (False si es nuevo), para
                # poder contar cuántos PASARON a cada estado en esta corrida.
                # Habilitado = tiene liberación naviera (MBL) y/o del
                # consignatario/importador (CONT), todavía sin DM. Liberado =
                # eso más el DM (misma condición que ya calculaba release_date).
                antes_arribo = bool(container.arrival_date) if container else False
                antes_habilitado = bool(container.mbl_release_date or container.container_release_date) if container else False
                antes_liberado = bool(container.release_date) if container else False
                antes_extraido = bool(container.extraction_date) if container else False
                antes_devuelto = bool(container.return_date) if container else False

                # Índices pandas (0-based). Formato actual del reporte de la
                # Terminal (Frutas Selectas / TCM), 18 columnas:
                # 0 CNTR, 1 MASTER_BILL_NO, 2 BILL_NO, 3 NAVIERA, 4 REFRIG,
                # 5 ENT_FECHA, 6 LIB_MBL, 7 CONSIGN_LIB_MBL, 8 LIB_CONT,
                # 9 CONSIGN_LIB_CONT, 10 FECHA_DM_NO, 11 PRECITA, 12 CITA,
                # 13 SAL_FECHA, 14 SAL_TRANSPORTISTA, 15 SAL_CHAPA, 16 PROV,
                # 17 RETORNO.
                # release_date NO se lee directo de una columna: se calcula
                # abajo (regla de negocio con LIB_MBL / LIB_CONT / FECHA_DM_NO).
                mapeo_columnas = {
                    3: ('shipping_company', lambda v: self.clean_text(v)),
                    4: ('cargo_type', self._parse_cargo_type),
                    5: ('arrival_date', self._parse_date),
                    6: ('mbl_release_date', self._parse_date),
                    9: ('container_release_partner', lambda v: self.clean_text(v)),
                    10: ('declaration_date_probable', self._parse_date),
                    11: ('pre_appointment_date', self._parse_date),
                    12: ('appointment_date', self._parse_date),
                    13: ('extraction_date', self._parse_date),
                    14: ('transport_company', lambda v: self.clean_text(v)),
                    15: ('truck_plate', lambda v: self.clean_text(v)),
                    16: ('province', lambda v: self.clean_text(v)),
                    17: ('return_date', self._parse_date),
                }
                if master_bl:
                    vals_update['master_bl_number'] = master_bl

                # LIB_CONT (col 8) solo es válido si hubo traspaso del
                # contenedor (CONSIGN_LIB_CONT, col 9, con dato) — si no, ese
                # dato de la Terminal no existe todavía.
                if len(row) > 9 and pd.notna(row.iloc[9]) and self.clean_text(row.iloc[9]):
                    if len(row) > 8 and pd.notna(row.iloc[8]):
                        cont_date = self._parse_date(row.iloc[8])
                        if cont_date and not pd.isna(cont_date):
                            vals_update['container_release_date'] = cont_date

                # Sin fecha DM el contenedor simplemente no está liberado
                # todavía (no es un error, es un estado normal en el flujo).
                calculated_release_date = self._compute_release_date(row)
                if calculated_release_date:
                    vals_update['release_date'] = calculated_release_date

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

                if not container:
                    if not bl:
                        _logger.warning(
                            "[IMPORT] Contenedor %s sin BL en el archivo: no se puede identificar el embarque, se omite",
                            container_number
                        )
                        self.env['import.error.line'].create({
                            'log_id': log.id,
                            'line_number': row_idx + 1,
                            'error_message': f"Contenedor '{container_number}' sin BL: no se puede crear/matchear sin identificar el embarque.",
                            'data': str(row),
                            'container_number': container_number,
                            'bl_number': bl,
                        })
                        continue

                    # No existe todavía en Odoo (la operación comercial no se
                    # cargó, o no se va a cargar) — se crea el contenedor de
                    # todos modos, sin proceso/OC vinculado. Se puede enlazar
                    # después manualmente si aparece la OC correspondiente.
                    try:
                        create_vals = dict(vals_update)
                        create_vals['name'] = container_number
                        create_vals['bl_number'] = bl
                        container = self.env['importation.load'].with_context(
                            lang='es_419', skip_date_check=True
                        ).create(create_vals)
                        _logger.info(
                            "[IMPORT] Contenedor creado sin proceso/OC vinculado: %s BL %s",
                            container_number, bl
                        )
                        # Es nuestro y NO estaba en el sistema: la corrida lo
                        # creó. Se lista como "no procesado (nuevo)" para poder
                        # revisarlo/completarlo comercialmente después.
                        contadores['nuevos_count'] += 1
                        self.env['import.error.line'].create({
                            'log_id': log.id,
                            'line_number': row_idx + 1,
                            'line_type': 'nuevo',
                            'container_number': container_number,
                            'bl_number': bl,
                            'arrival_date': vals_update.get('arrival_date'),
                            'release_date': vals_update.get('release_date'),
                            'extraction_date': vals_update.get('extraction_date'),
                            'return_date': vals_update.get('return_date'),
                            'dm_date': vals_update.get('declaration_date_probable'),
                            'error_message': (
                                "Nuevo: no estaba en el sistema, creado desde el "
                                "fichero (sin proceso/OC vinculado)."),
                        })
                    except Exception as e:
                        _logger.exception(
                            "[IMPORT] No se pudo crear el contenedor %s BL %s: %s",
                            container_number, bl, e
                        )
                        self.env['import.error.line'].create({
                            'log_id': log.id,
                            'line_number': row_idx + 1,
                            'error_message': f"No se pudo crear el contenedor '{container_number}' con BL '{bl}': {e}",
                            'data': str(row),
                            'container_number': container_number,
                            'bl_number': bl,
                        })
                        continue
                else:
                    if vals_update:
                        # Nunca pisar un dato ya cargado con un valor vacío: si
                        # la celda del CSV viene en blanco (p.ej. precita/cita
                        # que la Terminal deja de reportar una vez extraído el
                        # contenedor), esa clave nunca llega hasta aquí porque
                        # se filtra arriba (pd.isna(raw_value) -> continue).
                        # Este filtro es un refuerzo defensivo adicional.
                        vals_update = {k: v for k, v in vals_update.items() if v not in (False, '', None)}
                    if vals_update:
                        _logger.info(
                            "[IMPORT] Actualizando contenedor %s con %s",
                            container_number, vals_update
                        )
                        container.with_context(skip_date_check=True).write(vals_update)

                # Cuenta cuántos PASARON a cada estado en esta corrida (no
                # cuántos ya estaban en ese estado). Es una cadena elif —no 4
                # if independientes— porque un contenedor puede traer varias
                # fechas nuevas de golpe en la misma corrida (atraso cargado
                # de una vez, o primera vez que se ve en el sistema): solo
                # debe sumar en la categoría MAS AVANZADA que cambió, igual
                # que _compute_state, para no contarlo en más de un concepto.
                if not antes_devuelto and container.return_date:
                    contadores['devueltos_count'] += 1
                elif not antes_extraido and container.extraction_date:
                    contadores['extraidos_count'] += 1
                elif not antes_liberado and container.release_date:
                    contadores['liberados_count'] += 1
                elif not antes_habilitado and (container.mbl_release_date or container.container_release_date):
                    contadores['habilitados_count'] += 1
                elif not antes_arribo and container.arrival_date:
                    contadores['arribados_count'] += 1

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

        # Contenedores que están en nuestro sistema pero cuyo par
        # (contenedor + BL) no vino en NINGUNA fila del fichero de esta corrida:
        # o aún no arribó, o hay un error de BL/número que rompió el match.
        faltantes = existing_pairs - file_pairs
        contadores['no_en_fichero_count'] = len(faltantes)
        if faltantes:
            self.env['import.error.line'].create([
                {
                    'log_id': log.id,
                    'line_type': 'no_fichero',
                    'container_number': cont_name,
                    'bl_number': cont_bl,
                    'error_message': (
                        "En el sistema pero no aparece en el fichero de esta "
                        "corrida (¿aún no arriba, o error en el BL/número?)."),
                }
                for (cont_name, cont_bl) in faltantes
            ])

        # Foto del estado de TODOS los contenedores al cerrar la corrida. Se
        # asegura primero que los estados recalculados queden escritos en la
        # BD (flush) para que el conteo por estado sea el real de este momento.
        # La suma de los cinco = total de contenedores del sistema.
        self.env.flush_all()
        Load = self.env['importation.load']
        contadores.update({
            'estado_por_llegar': Load.search_count([('state', '=', 'to_arrive')]),
            'estado_arribado': Load.search_count([('state', '=', 'to_extract')]),
            'estado_habilitado': Load.search_count([('state', '=', 'ready_extract')]),
            'estado_extraido': Load.search_count([('state', '=', 'to_return')]),
            'estado_retornado': Load.search_count([('state', '=', 'returned')]),
        })

        log.write(contadores)
        return {'type': 'ir.actions.act_window_close'}