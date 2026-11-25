from datetime import datetime, timedelta

try:
    from backend.services.cegid_auditoria_source import CegidAuditoriaSource
    from backend.services.reconciliation_service import ReconciliationService
    from backend.services.unit_of_work import UnitOfWork
except ModuleNotFoundError:
    from services.cegid_auditoria_source import CegidAuditoriaSource
    from services.reconciliation_service import ReconciliationService
    from services.unit_of_work import UnitOfWork


class AuditoriaService:
    def __init__(self, uow_factory=UnitOfWork, cegid_source=None):
        self.uow_factory = uow_factory
        self.cegid_source = cegid_source or CegidAuditoriaSource()

    def resumen(self):
        """Retorna los KPIs macro para las tarjetas informativas superiores."""
        with self.uow_factory() as uow:
            return ReconciliationService(uow.session).resumen_ejecutivo()

    def explorador(self, proveedor=None, estado=None, marca=None, mes=None, souche=None, limit=200):
        """Alimenta la grilla principal de documentos analizados."""
        with self.uow_factory() as uow:
            return ReconciliationService(uow.session).explorador_cumplimiento(
                proveedor=proveedor,
                estado=estado,
                marca=marca,
                mes=mes,
                souche=souche,
                limit=limit,
            )

    def detalle_documento(self, documento_id):
        """Muestra el desglose por EAN cuando se consulta un documento específico."""
        with self.uow_factory() as uow:
            return ReconciliationService(uow.session).detalle_documento(documento_id)

    def plan_vs_recepcion(self, proveedor=None, marca=None, mes=None, souche=None, limit=500):
        """Llama al motor de casilleros para la grilla comparativa principal."""
        with self.uow_factory() as uow:
            return ReconciliationService(uow.session).plan_vs_recepcion(
                proveedor=proveedor,
                marca=marca,
                mes=mes,
                souche=souche,
                limit=limit,
            )

    def recepciones_posteriores_def(self, proveedor=None, marca=None, mes=None, souche=None):
        """
        Optimización de Data Engineering: Aclana el historial de ingresos calculados
        por el algoritmo de casilleros. Evita consultas pesadas redundantes a CEGID
        y asegura consistencia simétrica entre las vistas del reporte.
        """
        # Solicitamos el cálculo al motor transaccional (con un límite alto para no cortar datos)
        with self.uow_factory() as uow:
            items_conciliados = ReconciliationService(uow.session).plan_vs_recepcion(
                proveedor=proveedor,
                marca=marca,
                mes=mes,
                souche=souche,
                recepcion_souche=None,
                limit=10000, 
            )

        registros_posteriores = []
        
        # Recorremos cada casillero y extraemos sus ingresos cronológicos asociados
        for item in items_conciliados:
            historial = item.get("historial_detalle", [])
            
            for ingreso in historial:
                meses_desvio = ingreso.get("dias_desvio", ingreso.get("desvio_meses", ingreso.get("desvío_meses", 0)))
                if meses_desvio <= 0:
                    continue

                # Filtrar si llego en meses posteriores es directo gracias al desvio calculado.
                registros_posteriores.append({
                    "codigo_articulo": item["codigo_articulo"],
                    "ean": item["ean"],
                    "descripcion": item["descripcion"],
                    "marca": item["marca"],
                    "talle": item["talle"],
                    "genero": item["genero"],
                    "mes_planificado": item["mes_planificado"],
                    "cantidad_pedida_def": item["cantidad_pedida"],
                    "comprobante_blf": ingreso["comprobante"],
                    "fecha_recepcion_real": ingreso["fecha_ingreso"],
                    "cantidad_recibida_blf": ingreso["cantidad_ingresada"],
                    "meses_desvio": meses_desvio,
                    "estado_entrega": ingreso["etiqueta_tiempo"]
                })

        # Retornamos la lista ordenada por artículo y fecha de recepción real
        return sorted(
            registros_posteriores,
            key=lambda x: (x["codigo_articulo"], x["fecha_recepcion_real"])
        )

    def registrar_documento(self, proveedor_data, documento_data, lineas):
        """Persiste documentos procesados manualmente por la API."""
        with self.uow_factory() as uow:
            from backend.services.auditoria_repository import AuditoriaRepository
            repo = AuditoriaRepository(uow.session)
            proveedor = repo.get_or_create_proveedor(**proveedor_data)
            documento_data["proveedor_id"] = proveedor.id
            documento = repo.upsert_documento(documento_data, lineas=lineas)
            return {"id": documento.id, "codigo_documento": documento.codigo_documento}

    def sincronizar_circuito_cegid(self, mes_target: str, souche=None):
        """
        Sincronización Inteligente Automatizada.
        Calcula las ventanas de extracción óptimas para mitigar Table Scans en el ERP.
        """
        if not mes_target or "-" not in mes_target:
            raise ValueError("Se requiere un mes de control válido en formato YYYY-MM")

        # 1. Definir la ventana estricta para la demanda (DEF)
        # Traemos las propuestas cuya fecha de entrega prometida corresponda al mes de auditoría
        year, month = map(int, mes_target.split("-"))
        desde_def = f"{mes_target}-01"
        
        if month == 12:
            hasta_def = f"{year + 1}-01-01"
        else:
            hasta_def = f"{year}-{month + 1:02d}-01"

        # 2. Definir la ventana extendida para las recepciones físicas (BLF)
        # Aplicamos un Look-back de 60 días antes del inicio del mes para capturar adelantos de stock
        fecha_inicio_blf = datetime(year, month, 1) - timedelta(days=60)
        desde_blf = fecha_inicio_blf.strftime("%Y-%m-%d")
        
        # El límite superior de ingresos siempre es el día de hoy (tiempo real)
        hasta_blf = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")

        # --- Bloque A: Ingesta de Demandas (DEF) ---
        rows_piece_def = self.cegid_source.obtener_documentos(["DEF"], desde=desde_def, hasta=hasta_def, souche=souche)
        rows_ligne_def = self.cegid_source.obtener_lineas(["DEF"], desde=desde_def, hasta=hasta_def, souche=souche)
        
        # --- Bloque B: Ingesta de Recepciones (BLF) ---
        eans_def = [
            self.cegid_source._clean_value(row.get("GL_REFARTBARRE"))
            for row in rows_ligne_def
        ]
        eans_def = [ean for ean in dict.fromkeys(eans_def) if ean]
        rows_ligne_blf = []
        for chunk in self._chunks(eans_def, 500):
            rows_ligne_blf.extend(
                self.cegid_source.obtener_lineas(
                    ["BLF"],
                    desde=desde_blf,
                    hasta=hasta_blf,
                    souche=None,
                    eans=chunk,
                )
            )
        claves_blf = [self._document_key_from_ligne(row) for row in rows_ligne_blf]
        rows_piece_blf = self.cegid_source.obtener_documentos_por_claves(claves_blf)

        # Unificar colecciones crudas para el procesamiento del repositorio
        rows_piece = rows_piece_def + rows_piece_blf
        rows_ligne = rows_ligne_def + rows_ligne_blf

        # Procesar talles y normalizar estructuras hacia Docker
        rows_ligne = self.cegid_source.aplicar_talles_por_ean(rows_ligne)
        documentos_normalizados = [self.cegid_source.normalizar_piece(row) for row in rows_piece]

        lineas_por_documento = {}
        for row in rows_ligne:
            documento_key = self._document_key_from_ligne(row)
            lineas_por_documento.setdefault(documento_key, []).append(row)

        documentos_guardados = 0
        lineas_guardadas = 0

        with self.uow_factory() as uow:
            from backend.services.auditoria_repository import AuditoriaRepository
            repo = AuditoriaRepository(uow.session)
            
            # Limpieza idempotente dirigida únicamente al mes en evaluación
            eliminados = repo.eliminar_documentos_por_ventana(
                desde=desde_def,
                hasta=hasta_def,
                souche=souche,
                origenes=["PROPUESTA", "RECEPCION"],
            )
            
            for row_piece, documento_data in zip(rows_piece, documentos_normalizados):
                proveedor = repo.get_or_create_proveedor(cod_prov=row_piece.get("GP_TIERS"), marca=None)
                documento_data["proveedor_id"] = proveedor.id

                rows_ligne_doc = lineas_por_documento.get(documento_data["codigo_documento"], [])
                lineas = [
                    self.cegid_source.normalizar_ligne(row)
                    for row in rows_ligne_doc
                    if str(row.get("GL_TYPELIGNE", "")).strip() == "ART"
                ]

                repo.upsert_documento(documento_data, lineas=lineas)
                documentos_guardados += 1
                lineas_guardadas += len(lineas)

        return {
            "documentos": documentos_guardados,
            "lineas": lineas_guardadas,
            "documentos_reemplazados": eliminados,
            "tipos": ["DEF", "BLF"],
        }

    def _hasta_exclusive(self, hasta):
        if not hasta:
            return None
        if isinstance(hasta, str):
            try:
                return (datetime.strptime(hasta[:10], "%Y-%m-%d") + timedelta(days=1)).strftime("%Y-%m-%d")
            except ValueError:
                return hasta
        if isinstance(hasta, datetime):
            return hasta + timedelta(days=1)
        return hasta

    def _document_key_from_ligne(self, row):
        try:
            from backend.services.cegid_reference import build_document_key
        except ModuleNotFoundError:
            from services.cegid_reference import build_document_key

        return build_document_key(
            row.get("GL_NATUREPIECEG"),
            row.get("GL_SOUCHE"),
            row.get("GL_NUMERO"),
            row.get("GL_INDICEG") or 0,
        )

    def _chunks(self, values, size):
        for i in range(0, len(values), size):
            yield values[i:i + size]
