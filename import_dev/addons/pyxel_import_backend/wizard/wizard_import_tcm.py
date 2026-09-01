import base64
import re
from collections import defaultdict
from datetime import datetime

import pandas as pd
import unicodedata
from odoo import models, fields
from io import StringIO
import logging

_logger = logging.getLogger(__name__)

# Un mismo BL se escribe distinto en cada fuente: '045926' aquí y '45926'
# allá, 'SXERMAR-43' con guion y 'SXERMAR43' sin él. Para emparejar hay que
# comparar una forma canónica, no la cadena literal.
BL_SEPARADOR = re.compile(r"[^0-9A-Z]+")
BL_CEROS = re.compile(r"^([A-Z]*)0+(\d)")
BL_HIJO = re.compile(r"([0-9])[A-Z]$")

# Longitud a partir de la cual una clave canónica de BL se considera DÉBIL.
#
# El separador parte el BL en vez de borrarlo, así que 'SXERMAR-391' se reduce a
# '391' y pierde el prefijo que lo distinguía (D-30). 193 claves del TCM del
# 12-ago quedan con 3 caracteres o menos: '1', '10', '100'. Emparejar por una
# de ellas es casi emparejar por el contenedor solo, y eso es justo lo que la
# guía prohíbe.
LLAVE_BL_DEBIL = 3


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

    def bl_keys(self, *values):
        """Formas canónicas de un BL, una por cada BL que traiga la celda.

        Mayúsculas, sin separadores y sin ceros a la izquierda, para que
        '045926' y '45926' o 'SXERMAR-43' y 'SXERMAR43' emparejen. Una celda
        puede traer más de un BL ('CWPS26176579, CWPS26188235'): se devuelven
        todos, porque quedarse con el primero pierde el segundo embarque.
        """
        keys = set()
        for value in values:
            for piece in BL_SEPARADOR.split(self.clean_text(value).upper()):
                if piece and any(c.isdigit() for c in piece):
                    keys.add(BL_CEROS.sub(r"\1\2", piece))
        return keys

    def bl_root(self, key):
        """El BL padre de una partida hija: ADSNMAR11876A -> ADSNMAR11876.

        La Terminal no parte el BL en hijos; nosotros sí. Es el ÚLTIMO
        recurso del emparejamiento: varios hijos comparten padre, así que
        solo vale cuando no hay coincidencia exacta ni canónica.
        """
        return BL_HIJO.sub(r"\1", key)

    def container_key(self, value):
        return self.clean_text(value).upper().replace(" ", "").replace("-", "")

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

    def _get_importadora_config(self):
        """Una entrada por cada importadora del catalogo que tenga su
        patron de TCM configurado (tcm_match_name): el texto normalizado
        a buscar, si es "la nuestra" (coincide con
        res.company.importadora_name) y desde que fecha de llegada se
        le permite crear contenedores nuevos (None = sin restriccion).
        Las importadoras sin tcm_match_name puesto (todavia no
        confirmado como aparecen en el TCM) no participan en nada."""
        company_pattern = self._get_company_importadora_name()
        config = []
        for imp in self.env['importation.importer'].search([('tcm_match_name', '!=', False)]):
            pattern = self.normalize_compare_text(imp.tcm_match_name)
            if not pattern:
                continue
            config.append({
                'pattern': pattern,
                'is_ours': bool(company_pattern) and pattern == company_pattern,
                'sync_from': imp.tcm_sync_start_date,
            })
        return config

    def _match_importadora(self, norm_h, norm_j, importadora_config):
        """Duena de la fila, o None si ninguna del catalogo matchea.

        Prioridad: la nuestra (ENETEC) gana si aparece en H o en J, sin
        importar que otra tambien matchee -- en la practica H suele
        traer solo el tramitador del MBL (EMSERPET, PROMAX...) mientras
        J trae quien libera el contenedor de verdad. Si no es la
        nuestra, gana quien matchee en J antes que quien matchee en H,
        por la misma razon."""
        candidatos_h = [c for c in importadora_config if c['pattern'] in norm_h]
        candidatos_j = [c for c in importadora_config if c['pattern'] in norm_j]
        nuestra = next((c for c in candidatos_h + candidatos_j if c['is_ours']), None)
        if nuestra:
            return nuestra
        if candidatos_j:
            return candidatos_j[0]
        if candidatos_h:
            return candidatos_h[0]
        return None

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
        importadora_config = self._get_importadora_config()
        hoy = fields.Date.context_today(self)

        # Contenedores ya existentes en el sistema, precargados una sola vez
        # (no dentro del bucle) para no lanzar una consulta por cada una de las
        # miles de filas de otros importadores que comparten este mismo reporte
        # de la Terminal.
        #
        # Se indexan por tres claves, de más a menos estricta, porque el BL no
        # se escribe igual en el sistema y en la Terminal:
        #   1. (contenedor, BL) literal — el emparejamiento de siempre;
        #   2. (contenedor, BL canónico) — ignora ceros, guiones y espacios;
        #   3. (contenedor, BL padre) — para nuestras partidas hijas A/B/C,
        #      que la Terminal no parte.
        # Siempre contenedor Y BL juntos, nunca el contenedor solo: el mismo
        # número se reutiliza en embarques distintos.
        #
        # Se leen TODOS, también los que no tienen BL: sin BL nunca podrán
        # emparejar con la Terminal, pero son contenedores del sistema y tienen
        # que aparecer en la clasificación. Si se descartaran aquí, la suma de
        # la clasificación quedaría por debajo del total de contenedores y el
        # cuadre del reporte no cerraría.
        existing_records = self.env['importation.load'].search_read(
            [], ['name', 'bl_number', 'master_bl_number', 'belongs_to_us',
                 'arrival_date', 'terminal_last_seen',
                 'created_by_terminal_report'])
        existing_info = {
            (r['name'], r['bl_number']): {'id': r['id'], 'ours': r['belongs_to_us']}
            for r in existing_records if r['bl_number']
        }

        existing_bl = {r['id']: r['bl_number'] for r in existing_records}
        by_bl_key = defaultdict(list)
        by_bl_root = defaultdict(list)
        for r in existing_records:
            if not r['bl_number']:
                continue
            cont = self.container_key(r['name'])
            for key in self.bl_keys(r['bl_number'], r['master_bl_number']):
                by_bl_key[(cont, key)].append(r['id'])
                by_bl_root[(cont, self.bl_root(key))].append(r['id'])

        # Contenedores nuestros que ESTA corrida ha reconocido en el fichero,
        # por id (no por cadena): así "no está en el fichero" deja de contar
        # como ausentes los que sí están pero con el BL escrito de otra forma.
        seen_ids = set()
        # Contenedores (solo el número) presentes en el fichero, para poder
        # distinguir "no está" de "está, pero ese viaje no".
        file_containers = set()

        # Cuántos embarques DISTINTOS trae el fichero para cada caja. Es la
        # mitad que faltaba de la cuarentena de D-30: una clave de BL corta solo
        # es peligrosa si además ese mismo contenedor aparece en más de un
        # embarque. Si la caja viene una sola vez, no hay con qué confundirla.
        embarques_por_caja = defaultdict(set)
        for _, fila in df.iterrows():
            caja = self.container_key(fila.iloc[0]) if len(fila) else ''
            if not caja:
                continue
            claves = self.bl_keys(
                fila.iloc[1] if len(fila) > 1 else '',
                fila.iloc[2] if len(fila) > 2 else '',
            )
            if claves:
                embarques_por_caja[caja].add(frozenset(claves))

        contadores = {
            'arribados_count': 0,
            'habilitados_count': 0,
            'liberados_count': 0,
            'extraidos_count': 0,
            'devueltos_count': 0,
            'nativos_count': 0,
            'consignados_count': 0,
            'cambio_importadora_count': 0,
            'otras_importadoras_count': 0,
            'otro_valor_count': 0,
            'no_en_fichero_count': 0,
            'otro_viaje_count': 0,
            'duplicado_count': 0,
            'sin_dato_count': 0,
            'nuevos_count': 0,
            'cuarentena_count': 0,
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
            en_cuarentena = False

            try:
                container_number = self.clean_text(row.iloc[0])
                bl = self.clean_text(row.iloc[2])
                if len(row) > 1 and pd.notna(row.iloc[1]):
                    master_bl = self.clean_text(row.iloc[1])

                cont_key = self.container_key(container_number)
                if cont_key:
                    file_containers.add(cont_key)

                # Columna H (idx 7, Nativo/Master BL) y columna J (idx 9,
                # Consignado/traspaso) en pandas.
                if len(row) > 7 and pd.notna(row.iloc[7]):
                    importadora_name = self.clean_text(row.iloc[7])
                consignado_name = self.clean_text(row.iloc[9]) if len(row) > 9 and pd.notna(row.iloc[9]) else ''

                # ¿Está ya este embarque en nuestro sistema? Se busca por
                # contenedor Y BL, en tres pasadas de menos a más tolerante.
                # Esto se resuelve ANTES de mirar H/J porque un contenedor que
                # ya es nuestro sigue siéndolo aunque la Terminal lo tenga
                # atribuido a otra empresa.
                container = self.env['importation.load']
                if bl:
                    keys = self.bl_keys(bl, master_bl)
                    canonicos = {i for k in keys
                                 for i in by_bl_key.get((cont_key, k), [])}
                    info = existing_info.get((container_number, bl))
                    if info:
                        candidatos = {info['id']}
                    else:
                        candidatos = set(canonicos)
                        if not candidatos:
                            # Último recurso: nuestras partidas hijas (A/B/C)
                            # contra el BL padre que trae la Terminal.
                            candidatos = {i for k in keys
                                          for i in by_bl_root.get(
                                              (cont_key, self.bl_root(k)), [])}

                        # --- Cuarentena (D-30) ---
                        # Si el emparejamiento se sostiene SOLO sobre una clave
                        # débil y además esta caja aparece en el fichero con más
                        # de un embarque, es el caso que avisa la guía: la misma
                        # caja en viajes distintos. No se adivina cuál es (D-09):
                        # se deja sin tocar y se manda a revisión.
                        #
                        # No entra aquí el emparejamiento literal (contenedor +
                        # BL exacto, la rama `info` de arriba): ese compara la
                        # cadena completa, no una clave recortada, y es seguro.
                        #
                        # Medidos 63 casos el 14-ago sobre 2.906 emparejamientos
                        # (2,2%). Se prefirió la cuarentena a rehacer la clave
                        # porque rehacerla pierde 7 emparejamientos buenos y no
                        # gana ninguno.
                        if candidatos and len(embarques_por_caja.get(cont_key, ())) > 1:
                            fuertes = {k for k in keys if len(k) > LLAVE_BL_DEBIL}
                            solidos = {i for k in fuertes
                                       for i in by_bl_key.get((cont_key, k), [])}
                            if not solidos:
                                solidos = {i for k in fuertes
                                           for i in by_bl_root.get(
                                               (cont_key, self.bl_root(k)), [])}
                            en_cuarentena = not solidos

                    # Un mismo embarque cargado dos veces con el BL escrito de
                    # dos formas ('046638' y '46638') se veía como dos
                    # contenedores: uno casaba con la Terminal y el otro se
                    # quedaba huérfano para siempre, atascado en su último
                    # estado. Con la clave canónica salen a la luz.
                    if len(canonicos) > 1:
                        contadores['duplicado_count'] += 1
                        seen_ids.update(canonicos)
                        repetidos = ", ".join(sorted(
                            "%s (id %s)" % (existing_bl.get(i, '?'), i)
                            for i in canonicos))
                        self.env['import.error.line'].create({
                            'log_id': log.id,
                            'line_number': row_idx + 1,
                            'line_type': 'duplicado',
                            'container_number': container_number,
                            'bl_number': bl,
                            'error_message': (
                                f"El sistema tiene {len(canonicos)} contenedores "
                                f"para este mismo embarque, con el BL escrito de "
                                f"formas distintas: {repetidos}. Unificar."),
                        })

                    if len(candidatos) == 1:
                        container = self.env['importation.load'].with_context(
                            lang='es_419').browse(candidatos.pop())
                        seen_ids.add(container.id)
                    elif len(candidatos) > 1:
                        # Varios contenedores nuestros encajan con esta fila:
                        # no se adivina, se avisa y se deja sin tocar.
                        seen_ids.update(candidatos)
                        self.env['import.error.line'].create({
                            'log_id': log.id,
                            'line_number': row_idx + 1,
                            'line_type': 'error',
                            'container_number': container_number,
                            'bl_number': bl,
                            'error_message': (
                                f"La fila encaja con {len(candidatos)} contenedores "
                                f"del sistema (BL parecidos). No se actualiza "
                                f"ninguno: revisar el BL."),
                        })
                        continue

                # Clasificación de la fila para el resumen de la corrida.
                # Nativo (H = nuestra empresa) y Consignado (J = nuestra
                # empresa) se cuentan sobre TODAS las filas leídas. Las otras
                # dos solo cuentan cuando el contenedor YA existe en nuestro
                # sistema; el resto de filas son de otros importadores que
                # comparten este mismo reporte de la Terminal.
                #
                # "Otro valor, ya en el sistema" significa que el contenedor es
                # NUESTRO y la Terminal lo tiene a nombre de un tercero: pasa
                # con todo lo que se tramita por EMSERPET, PALCO o EXPEDIMAR.
                # No es motivo para dejar de actualizarlo ni para dejar de
                # considerarlo nuestro — solo se anota quién figura en H/J.
                # "Contiene", no exacto, en los dos casos -- ENETEC incluido:
                # el TCM a veces mezcla el nombre con el de otra empresa en
                # la misma celda, y comparar exacto perdía esas filas (se
                # descubrió al ver que el total de la clasificación no
                # cuadraba con el total de contenedores: filas que sí eran
                # nuestras caían fuera de todos los casilleros). nuestra_pattern
                # sale del catálogo (importation.importer, is_ours=True); si
                # por lo que sea no está sembrado ahí, se cae a
                # res.company.importadora_name como red de seguridad.
                norm_h = self.normalize_compare_text(importadora_name)
                norm_j = self.normalize_compare_text(consignado_name)
                nuestra_pattern = next(
                    (c['pattern'] for c in importadora_config if c['is_ours']),
                    config_importadora,
                )
                es_nativo_row = nuestra_pattern in norm_h if nuestra_pattern else bool(importadora_name)
                es_consignado_row = nuestra_pattern in norm_j if nuestra_pattern else bool(consignado_name)
                dueno_fila = self._match_importadora(norm_h, norm_j, importadora_config)

                # Si dueno_fila no es la nuestra y el contenedor NO existe
                # todavía, hace falta saber YA (antes de clasificar) si esta
                # fila va a poder crearlo o si el corte de fecha
                # (tcm_sync_start_date) la va a saltar más abajo -- si no,
                # se cuenta como "otra importadora" una fila que en realidad
                # no toca ningún contenedor real, y el total de la
                # clasificación deja de cuadrar con el total de contenedores
                # (pasó: 100 filas de EINARBO/ENERSA, todas antes del corte
                # y sin contenedor propio, se contaban igual).
                fecha_llegada = self._parse_date(row.iloc[5]) if len(row) > 5 and pd.notna(row.iloc[5]) else False
                dueno_fila_creara_o_actualizara = bool(dueno_fila) and (
                    bool(container)
                    or dueno_fila['is_ours']
                    or not dueno_fila['sync_from']
                    or (fecha_llegada and not pd.isna(fecha_llegada)
                        and fecha_llegada.date() >= dueno_fila['sync_from'])
                )

                if es_nativo_row:
                    contadores['nativos_count'] += 1
                elif es_consignado_row:
                    contadores['consignados_count'] += 1
                elif dueno_fila_creara_o_actualizara:
                    # Matchea una importadora del catálogo que no es la
                    # nuestra (PROMAX, EMSERPET...) -- se cuenta aparte,
                    # exista ya el contenedor o lo cree esta corrida, para
                    # que el total de la clasificación siga cuadrando con
                    # el total de contenedores del sistema.
                    contadores['otras_importadoras_count'] += 1
                    self.env['import.error.line'].create({
                        'log_id': log.id,
                        'line_number': row_idx + 1,
                        'line_type': 'otra_importadora',
                        'container_number': container_number,
                        'bl_number': bl,
                        'error_message': (
                            f"Matchea {dueno_fila['pattern']} (no es la nuestra): "
                            f"H='{importadora_name}' / J='{consignado_name}'."),
                    })
                elif container:
                    if importadora_name or consignado_name:
                        contadores['otro_valor_count'] += 1
                        self.env['import.error.line'].create({
                            'log_id': log.id,
                            'line_number': row_idx + 1,
                            'line_type': 'otro_valor',
                            'container_number': container_number,
                            'bl_number': bl,
                            'error_message': (
                                f"Nuestro, tramitado por un tercero: "
                                f"H='{importadora_name}' / J='{consignado_name}'. "
                                f"Se le vuelcan igualmente los datos de la Terminal."),
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
                                "En el sistema, pero el fichero trae H y J vacías. "
                                "Se le vuelcan igualmente los datos de la Terminal."),
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

                # Quién figura en H/J decide si podemos CREAR un contenedor
                # nuevo, no si podemos actualizar uno que ya es nuestro. Un
                # contenedor que ya está en el sistema se sincroniza siempre,
                # sea de la importadora que sea (ENETEC tramita por EMSERPET,
                # PALCO o EXPEDIMAR con normalidad, y si el nombre mandara
                # sobre la actualización perderíamos su rastro en el puerto
                # justo en los embarques que más nos importan).
                #
                # Para CREAR uno nuevo hace falta que matchee alguna
                # importadora del catálogo (dueno_fila); y si no es la
                # nuestra, además tiene que haber llegado en o después de su
                # tcm_sync_start_date -- para no volcar de golpe el historial
                # viejo de una importadora que recién se incorpora.
                if not container:
                    if not dueno_fila:
                        _logger.info(
                            "[IMPORT] Fila %s omitida: no está en el sistema y "
                            "ninguna importadora del catálogo matchea. "
                            "H='%s' / J='%s'",
                            row_idx + 1, importadora_name, consignado_name,
                        )
                        continue
                    if not dueno_fila_creara_o_actualizara:
                        _logger.info(
                            "[IMPORT] Fila %s omitida: no está en el sistema, "
                            "matchea una importadora nueva pero llegó antes de "
                            "su fecha de arranque (%s). H='%s' / J='%s'",
                            row_idx + 1, dueno_fila['sync_from'],
                            importadora_name, consignado_name,
                        )
                        continue
                elif not (es_nativo_row or es_consignado_row):
                    _logger.info(
                        "[IMPORT] Fila %s: contenedor nuestro tramitado por un "
                        "tercero (H='%s' / J='%s'). Se actualiza igualmente.",
                        row_idx + 1, importadora_name, consignado_name,
                    )

                # Cuarentena: se sale AQUÍ, no antes, a propósito. La fila ya se
                # ha clasificado arriba (nativo / consignado / otra importadora /
                # otro valor / sin dato), así que sigue contando en el cuadre del
                # reporte; lo único que no ocurre es la escritura. Salir antes
                # descuadraría la clasificación contra el total de contenedores.
                if en_cuarentena:
                    contadores['cuarentena_count'] += 1
                    self.env['import.error.line'].create({
                        'log_id': log.id,
                        'line_number': row_idx + 1,
                        'line_type': 'cuarentena',
                        'container_number': container_number,
                        'bl_number': bl,
                        'error_message': (
                            f"No se actualiza: el BL '{bl}' solo empareja por una "
                            f"clave demasiado corta (≤{LLAVE_BL_DEBIL} caracteres) y "
                            f"esta caja aparece en el fichero con "
                            f"{len(embarques_por_caja.get(cont_key, ()))} embarques "
                            f"distintos. Podría ser el mismo contenedor en otro "
                            f"viaje. Escribir el BL completo en el sistema lo "
                            f"desambigua."),
                    })
                    _logger.info(
                        "[IMPORT] Fila %s en cuarentena: contenedor %s, BL %r, "
                        "clave débil y %s embarques para esa caja",
                        row_idx + 1, container_number, bl,
                        len(embarques_por_caja.get(cont_key, ())),
                    )
                    continue

                # Sigue siendo nuestro: la marca no se apaga porque la Terminal
                # lo ponga a nombre de un tercero. Quién figura en H se guarda
                # aparte (J ya cae en container_release_partner).
                vals_update['belongs_to_us'] = True
                vals_update['terminal_last_seen'] = hoy
                vals_update['handled_by_third_party'] = not (es_nativo_row or es_consignado_row)
                if importadora_name:
                    vals_update['mbl_release_partner'] = importadora_name

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
                        create_vals['created_by_terminal_report'] = True
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
                        # Las marcas booleanas se exceptúan: un False suyo es un
                        # dato ("ya no lo tramita un tercero"), no un hueco, y
                        # si se filtrara nunca podrían volver a apagarse.
                        vals_update = {
                            k: v for k, v in vals_update.items()
                            if v not in (False, '', None)
                            or k in ('belongs_to_us', 'handled_by_third_party')
                        }
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

        # Contenedores nuestros que ninguna fila del fichero ha reconocido.
        # Antes eran una bolsa única que no decía qué hacer con ellos; ahora se
        # parten en dos casos, que piden cosas distintas:
        #   - el número de contenedor SÍ está en el fichero, pero con otro BL:
        #     o ese viaje no está, o el BL/el número están mal tecleados. Es
        #     revisable de inmediato, con el fichero delante.
        #   - el número no está en absoluto: o aún no ha arribado, o el número
        #     es erróneo.
        faltantes = [r for r in existing_records if r['id'] not in seen_ids]
        sin_bl, por_llegar, purgados, otro_viaje, ausentes = [], [], [], [], []
        for r in faltantes:
            if not r['bl_number']:
                sin_bl.append(r)
            elif not r['arrival_date']:
                # Todavía no ha arribado: que la Terminal no lo traiga es lo
                # normal, no un desajuste. Antes se mezclaban con las erratas
                # y eran la mayor parte del ruido del reporte.
                por_llegar.append(r)
            elif r['created_by_terminal_report'] or r['terminal_last_seen']:
                # Entró por la sincronización (o el reporte lo trajo alguna
                # vez) y ahora no viene: entonces es la Terminal la que lo ha
                # quitado, porque su número y su BL salieron de ahí. No hay
                # nada que corregir de nuestro lado.
                #
                # El contrapunto es el caso de abajo: si el contenedor entró
                # por la carga de importaciones y nunca ha casado, el número o
                # el BL los tecleamos nosotros y ahí es donde hay que mirar.
                purgados.append(r)
            elif self.container_key(r['name']) in file_containers:
                otro_viaje.append(r)
            else:
                ausentes.append(r)
        contadores['por_llegar_no_en_fichero_count'] = len(por_llegar)
        contadores['purgado_count'] = len(purgados)
        contadores['otro_viaje_count'] = len(otro_viaje)
        contadores['no_en_fichero_count'] = len(ausentes) + len(sin_bl)
        lineas = [
            {
                'log_id': log.id,
                'line_type': 'por_llegar',
                'container_number': r['name'],
                'bl_number': r['bl_number'],
                'error_message': (
                    "Todavía sin fecha de arribo: es normal que la Terminal no "
                    "lo traiga. No hay nada que corregir hasta que llegue."),
            }
            for r in por_llegar
        ] + [
            {
                'log_id': log.id,
                'line_type': 'purgado',
                'container_number': r['name'],
                'bl_number': r['bl_number'],
                'error_message': (
                    "Entró en el sistema desde el propio reporte de la Terminal "
                    "(visto por última vez el %s) y ahora ya no viene: lo ha "
                    "quitado la Terminal, no es un error de nuestros datos."
                    % (r['terminal_last_seen'] or 'una corrida anterior')),
            }
            for r in purgados
        ] + [
            {
                'log_id': log.id,
                'line_type': 'otro_viaje',
                'container_number': r['name'],
                'bl_number': r['bl_number'],
                'error_message': (
                    "Entró por la carga de importaciones y nunca ha casado con "
                    "la Terminal: el número del contenedor está en el fichero, "
                    "pero con otro BL. Revisar el BL y el número tal como se "
                    "cargaron."),
            }
            for r in otro_viaje
        ] + [
            {
                'log_id': log.id,
                'line_type': 'no_fichero',
                'container_number': r['name'],
                'bl_number': r['bl_number'],
                'error_message': (
                    "Entró por la carga de importaciones y su número no aparece "
                    "en ninguna fila del fichero. Revisar el número del "
                    "contenedor tal como se cargó."),
            }
            for r in ausentes
        ] + [
            {
                'log_id': log.id,
                'line_type': 'no_fichero',
                'container_number': r['name'],
                'bl_number': '',
                'error_message': (
                    "En el sistema SIN BL: no se puede emparejar con la "
                    "Terminal por mucho que el contenedor esté en el fichero. "
                    "Hay que ponerle el BL de su embarque."),
            }
            for r in sin_bl
        ]
        if lineas:
            self.env['import.error.line'].create(lineas)

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