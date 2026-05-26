try:
    from backend.services.cegid_reference import (
        build_document_key,
        parse_cegid_date,
        parse_cegid_decimal,
        parse_document_ref,
    )
except ModuleNotFoundError:
    from services.cegid_reference import (
        build_document_key,
        parse_cegid_date,
        parse_cegid_decimal,
        parse_document_ref,
    )


def _default_connection_factory():
    try:
        from backend.services.cegid_connector import conectar_cegid
    except ModuleNotFoundError:
        from services.cegid_connector import conectar_cegid
    return conectar_cegid()


class CegidAuditoriaSource:
    """
    Fuente de datos para documentos CEGID.

    PIECE guarda cabeceras y LIGNE guarda lineas, pero los nombres de campos y
    codigos de documento se parametrizan cuando definamos las consultas reales.
    """

    def __init__(self, connection_factory=_default_connection_factory):
        self.connection_factory = connection_factory

    def obtener_documentos(self, tipo_documento, desde=None, hasta=None, souche=None):
        tipos = self._normalizar_tipos(tipo_documento)
        if not tipos:
            tipos = ["CF", "ALF", "BLF"]

        placeholders = ",".join(["?"] * len(tipos))
        params = list(tipos)
        filtros_fecha = ""
        if desde:
            filtros_fecha += " AND GP_DATEPIECE >= ?"
            params.append(desde)
        if hasta:
            filtros_fecha += " AND GP_DATEPIECE < ?"
            params.append(hasta)
        if souche:
            filtros_fecha += " AND LTRIM(RTRIM(CAST(GP_SOUCHE AS VARCHAR(20)))) = ?"
            params.append(souche)

        query = f"""
            SELECT
                GP_DATEPIECE,
                GP_NATUREPIECEG,
                GP_NUMERO,
                GP_SOUCHE,
                GP_INDICEG,
                GP_NUMPIECE,
                GP_DATELIVRAISON,
                GP_REFINTERNE,
                GP_REFEXTERNE,
                GP_DEVENIRPIECE,
                GP_TIERS,
                GP_DEPOT,
                GP_DEVISE,
                GP_TOTALQTEFACT,
                GP_TOTALHT,
                GP_STATUTRECEPTION,
                GP_STATUTPIECE
            FROM PIECE
            WHERE LTRIM(RTRIM(CAST(GP_NATUREPIECEG AS VARCHAR(20)))) IN ({placeholders})
            {filtros_fecha}
        """
        return self._fetch_dicts(query, params)

    def obtener_lineas_documento(self, codigo_documento):
        naturaleza, souche, numero, indice = codigo_documento.split("|")
        query = """
            SELECT
                l.GL_DATEPIECE,
                l.GL_NATUREPIECEG,
                l.GL_NUMERO,
                l.GL_SOUCHE,
                l.GL_INDICEG,
                l.GL_NUMLIGNE,
                l.GL_NUMORDRE,
                l.GL_TIERS,
                l.GL_DEPOT,
                l.GL_TYPELIGNE,
                l.GL_ARTICLE,
                l.GL_LIBELLE,
                l.GL_CODEARTICLE,
                l.GL_REFARTSAISIE,
                l.GL_REFARTBARRE,
                l.GL_PIECEPRECEDENTE,
                l.GL_PIECEORIGINE,
                l.GL_QTESTOCK,
                l.GL_QTEFACT,
                l.GL_QTERESTE,
                l.GL_QTEINIT,
                l.GL_LIBREART2,
                l.GL_LIBREART3,
                NULL AS TALLE_CEGID
            FROM LIGNE l
            WHERE LTRIM(RTRIM(CAST(l.GL_NATUREPIECEG AS VARCHAR(20)))) = ?
              AND LTRIM(RTRIM(CAST(l.GL_SOUCHE AS VARCHAR(20)))) = ?
              AND LTRIM(RTRIM(CAST(l.GL_NUMERO AS VARCHAR(50)))) = ?
              AND LTRIM(RTRIM(CAST(l.GL_INDICEG AS VARCHAR(20)))) = ?
              AND LTRIM(RTRIM(CAST(l.GL_TYPELIGNE AS VARCHAR(20)))) = 'ART'
        """
        return self._fetch_dicts(query, [naturaleza, souche, numero, indice])

    def obtener_lineas(self, tipo_documento, desde=None, hasta=None, souche=None):
        tipos = self._normalizar_tipos(tipo_documento)
        if not tipos:
            tipos = ["CF", "ALF", "BLF"]

        placeholders = ",".join(["?"] * len(tipos))
        params = list(tipos)
        filtros = ""
        if desde:
            filtros += " AND l.GL_DATEPIECE >= ?"
            params.append(desde)
        if hasta:
            filtros += " AND l.GL_DATEPIECE < ?"
            params.append(hasta)
        if souche:
            filtros += " AND LTRIM(RTRIM(CAST(l.GL_SOUCHE AS VARCHAR(20)))) = ?"
            params.append(souche)

        query = f"""
            SELECT
                l.GL_DATEPIECE,
                l.GL_NATUREPIECEG,
                l.GL_NUMERO,
                l.GL_SOUCHE,
                l.GL_INDICEG,
                l.GL_NUMLIGNE,
                l.GL_NUMORDRE,
                l.GL_TIERS,
                l.GL_DEPOT,
                l.GL_TYPELIGNE,
                l.GL_ARTICLE,
                l.GL_LIBELLE,
                l.GL_CODEARTICLE,
                l.GL_REFARTSAISIE,
                l.GL_REFARTBARRE,
                l.GL_PIECEPRECEDENTE,
                l.GL_PIECEORIGINE,
                l.GL_QTESTOCK,
                l.GL_QTEFACT,
                l.GL_QTERESTE,
                l.GL_QTEINIT,
                l.GL_LIBREART2,
                l.GL_LIBREART3,
                NULL AS TALLE_CEGID
            FROM LIGNE l
            WHERE LTRIM(RTRIM(CAST(l.GL_NATUREPIECEG AS VARCHAR(20)))) IN ({placeholders})
              AND LTRIM(RTRIM(CAST(l.GL_TYPELIGNE AS VARCHAR(20)))) = 'ART'
            {filtros}
        """
        return self._fetch_dicts(query, params)

    def obtener_documentos_por_claves(self, claves_documento):
        claves = self._normalizar_claves(claves_documento)
        if not claves:
            return []

        rows = []
        for chunk in self._chunks(claves, 40):
            conditions, params = self._build_key_conditions("GP", chunk)
            query = f"""
                SELECT
                    GP_DATEPIECE,
                    GP_NATUREPIECEG,
                    GP_NUMERO,
                    GP_SOUCHE,
                    GP_INDICEG,
                    GP_NUMPIECE,
                    GP_DATELIVRAISON,
                    GP_REFINTERNE,
                    GP_REFEXTERNE,
                    GP_DEVENIRPIECE,
                    GP_TIERS,
                    GP_DEPOT,
                    GP_DEVISE,
                    GP_TOTALQTEFACT,
                    GP_TOTALHT,
                    GP_STATUTRECEPTION,
                    GP_STATUTPIECE
                FROM PIECE
                WHERE {conditions}
            """
            rows.extend(self._fetch_dicts(query, params))
        return rows

    def obtener_lineas_por_claves(self, claves_documento):
        claves = self._normalizar_claves(claves_documento)
        if not claves:
            return []

        rows = []
        for chunk in self._chunks(claves, 25):
            conditions, params = self._build_key_conditions("GL", chunk)
            query = f"""
                SELECT
                    l.GL_DATEPIECE,
                    l.GL_NATUREPIECEG,
                    l.GL_NUMERO,
                    l.GL_SOUCHE,
                    l.GL_INDICEG,
                    l.GL_NUMLIGNE,
                    l.GL_NUMORDRE,
                    l.GL_TIERS,
                    l.GL_DEPOT,
                    l.GL_TYPELIGNE,
                    l.GL_ARTICLE,
                    l.GL_LIBELLE,
                    l.GL_CODEARTICLE,
                    l.GL_REFARTSAISIE,
                    l.GL_REFARTBARRE,
                    l.GL_PIECEPRECEDENTE,
                    l.GL_PIECEORIGINE,
                    l.GL_QTESTOCK,
                    l.GL_QTEFACT,
                    l.GL_QTERESTE,
                    l.GL_QTEINIT,
                    l.GL_LIBREART2,
                    l.GL_LIBREART3,
                    NULL AS TALLE_CEGID
                FROM LIGNE l
                WHERE ({conditions})
                  AND LTRIM(RTRIM(CAST(l.GL_TYPELIGNE AS VARCHAR(20)))) = 'ART'
            """
            rows.extend(self._fetch_dicts(query, params))
        return rows

    def obtener_recepciones_articulos(self, codigos_articulo, desde=None, hasta=None):
        codigos = [self._clean_value(codigo) for codigo in codigos_articulo]
        codigos = [codigo for codigo in dict.fromkeys(codigos) if codigo]
        if not codigos:
            return []

        rows = []
        for chunk in self._chunks(codigos, 200):
            placeholders = ",".join(["?"] * len(chunk))
            params = list(chunk)
            filtros = ""
            if desde:
                filtros += " AND l.GL_DATEPIECE >= ?"
                params.append(desde)
            if hasta:
                filtros += " AND l.GL_DATEPIECE < ?"
                params.append(hasta)

            query = f"""
                SELECT
                    l.GL_DATEPIECE,
                    l.GL_NATUREPIECEG,
                    l.GL_NUMERO,
                    l.GL_SOUCHE,
                    l.GL_INDICEG,
                    l.GL_NUMLIGNE,
                    l.GL_TIERS,
                    l.GL_DEPOT,
                    l.GL_ARTICLE,
                    l.GL_LIBELLE,
                    l.GL_CODEARTICLE,
                    l.GL_REFARTBARRE,
                    l.GL_QTESTOCK,
                    l.GL_LIBREART2,
                    l.GL_LIBREART3,
                    NULL AS TALLE_CEGID
                FROM LIGNE l
                WHERE LTRIM(RTRIM(CAST(l.GL_NATUREPIECEG AS VARCHAR(20)))) = 'BLF'
                  AND LTRIM(RTRIM(CAST(l.GL_TYPELIGNE AS VARCHAR(20)))) = 'ART'
                  AND LTRIM(RTRIM(CAST(l.GL_CODEARTICLE AS VARCHAR(100)))) IN ({placeholders})
                {filtros}
            """
            rows.extend(self._fetch_dicts(query, params))
        return rows

    def obtener_talles_por_eans(self, eans):
        valores = [self._clean_value(ean) for ean in eans]
        valores = [ean for ean in dict.fromkeys(valores) if ean]
        if not valores:
            return {}

        talles = {}
        for chunk in self._chunks(valores, 600):
            placeholders = ",".join(["?"] * len(chunk))
            query = f"""
                SELECT
                    a.GA_CODEBARRE,
                    d.GDI_DIMORLI
                FROM ARTICLE a
                INNER JOIN DIMENSION d ON a.GA_CODEDIM1 = d.GDI_CODEDIM
                    AND a.GA_GRILLEDIM1 = d.GDI_GRILLEDIM
                WHERE a.GA_CODEBARRE IN ({placeholders})
            """
            for row in self._fetch_dicts(query, chunk):
                ean = self._clean_value(row.get("GA_CODEBARRE"))
                talle = self._clean_value(row.get("GDI_DIMORLI"))
                if ean and talle:
                    talles[ean] = talle
        return talles

    def aplicar_talles_por_ean(self, rows_ligne):
        talles = self.obtener_talles_por_eans(row.get("GL_REFARTBARRE") for row in rows_ligne)
        for row in rows_ligne:
            row["TALLE_CEGID"] = talles.get(self._clean_value(row.get("GL_REFARTBARRE")))
        return rows_ligne

    def normalizar_piece(self, row):
        naturaleza = str(row.get("GP_NATUREPIECEG", "")).strip()
        souche = str(row.get("GP_SOUCHE", "")).strip()
        numero = str(row.get("GP_NUMERO", "")).strip()
        indice = str(row.get("GP_INDICEG", "0")).strip() or "0"
        siguiente = parse_document_ref(row.get("GP_DEVENIRPIECE"))

        return {
            "origen": self._origen_desde_naturaleza(naturaleza),
            "codigo_documento": build_document_key(naturaleza, souche, numero, indice),
            "documento_relacionado": None,
            "cegid_naturaleza": naturaleza,
            "cegid_souche": souche,
            "cegid_numero": numero,
            "cegid_indice": indice,
            "ref_interna": self._clean_value(row.get("GP_REFINTERNE")),
            "ref_externa": self._clean_value(row.get("GP_REFEXTERNE")),
            "ref_siguiente": siguiente.document_key if siguiente else None,
            "deposito": self._clean_value(row.get("GP_DEPOT")),
            "fecha_documento": parse_cegid_date(row.get("GP_DATEPIECE")),
            "fecha_entrega_prevista": parse_cegid_date(row.get("GP_DATELIVRAISON")),
            "estado": row.get("GP_STATUTRECEPTION") or row.get("GP_STATUTPIECE") or "PENDIENTE",
            "moneda": self._clean_value(row.get("GP_DEVISE")),
            "total_cantidad": parse_cegid_decimal(row.get("GP_TOTALQTEFACT")),
            "total_importe": parse_cegid_decimal(row.get("GP_TOTALHT")),
        }

    def normalizar_ligne(self, row):
        precedente = parse_document_ref(row.get("GL_PIECEPRECEDENTE"))
        origen = parse_document_ref(row.get("GL_PIECEORIGINE"))
        numero_linea = row.get("GL_NUMLIGNE")

        return {
            "numero_linea": self._clean_value(numero_linea),
            "numero_orden": self._clean_value(row.get("GL_NUMORDRE")),
            "ean": self._clean_value(row.get("GL_REFARTBARRE")),
            "codigo_articulo": self._clean_value(row.get("GL_CODEARTICLE") or row.get("GL_REFARTSAISIE")),
            "descripcion": self._clean_value(row.get("GL_LIBELLE")),
            "talle": self._clean_value(row.get("TALLE_CEGID")),
            "deposito": self._clean_value(row.get("GL_DEPOT")),
            "marca": self._clean_value(row.get("GL_LIBREART2")),
            "genero": self._clean_value(row.get("GL_LIBREART3")),
            "cantidad": parse_cegid_decimal(row.get("GL_QTESTOCK")),
            "precio_unitario": parse_cegid_decimal(row.get("GL_PUHT")),
            "importe": parse_cegid_decimal(row.get("GL_TOTALHT")),
            "estado": "PENDIENTE",
            "pieza_precedente": precedente.document_key if precedente else None,
            "pieza_origen": origen.document_key if origen else None,
            "linea_precedente_key": precedente.line_key if precedente else None,
            "linea_origen_key": origen.line_key if origen else None,
        }

    def _origen_desde_naturaleza(self, naturaleza):
        mapping = {
            "CF": "PEDIDO",
            "DEF": "PROPUESTA",
            "ALF": "NOTIFICACION",
            "BLF": "RECEPCION",
        }
        return mapping.get(str(naturaleza).strip().upper(), "DESCONOCIDO")

    def _normalizar_tipos(self, tipo_documento):
        if tipo_documento is None:
            return []
        if isinstance(tipo_documento, str):
            tipo_documento = [tipo_documento]
        return [str(tipo).strip().upper() for tipo in tipo_documento if str(tipo).strip()]

    def _fetch_dicts(self, query, params):
        conexion = self.connection_factory()
        if not conexion:
            return []
        try:
            cursor = conexion.cursor()
            cursor.execute(query, params)
            columns = [col[0] for col in cursor.description]
            return [dict(zip(columns, row)) for row in cursor.fetchall()]
        finally:
            conexion.close()

    def _normalizar_claves(self, claves_documento):
        claves = []
        for clave in claves_documento:
            if not clave:
                continue
            parts = str(clave).split("|")
            if len(parts) != 4:
                continue
            claves.append(tuple(part.strip() for part in parts))
        return list(dict.fromkeys(claves))

    def _chunks(self, values, size):
        for i in range(0, len(values), size):
            yield values[i:i + size]

    def _build_key_conditions(self, prefix, claves):
        params = []
        clauses = []
        for naturaleza, souche, numero, indice in claves:
            alias = "l" if prefix == "GL" else None
            col = lambda name: f"{alias}.{prefix}_{name}" if alias else f"{prefix}_{name}"
            clauses.append(
                "("
                f"LTRIM(RTRIM(CAST({col('NATUREPIECEG')} AS VARCHAR(20)))) = ? AND "
                f"LTRIM(RTRIM(CAST({col('SOUCHE')} AS VARCHAR(20)))) = ? AND "
                f"LTRIM(RTRIM(CAST({col('NUMERO')} AS VARCHAR(50)))) = ? AND "
                f"LTRIM(RTRIM(CAST({col('INDICEG')} AS VARCHAR(20)))) = ?"
                ")"
            )
            params.extend([naturaleza, souche, numero, indice])
        return " OR ".join(clauses), params

    def _clean_value(self, value):
        if value is None:
            return None
        raw = str(value).strip()
        if not raw or raw.lower() == "nan":
            return None
        return raw
