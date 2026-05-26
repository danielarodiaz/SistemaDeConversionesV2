try:
    from datetime import datetime, timedelta

    from backend.services.auditoria_repository import AuditoriaRepository
    from backend.services.cegid_auditoria_source import CegidAuditoriaSource
    from backend.services.reconciliation_service import ReconciliationService
    from backend.services.unit_of_work import UnitOfWork
except ModuleNotFoundError:
    from datetime import datetime, timedelta

    from services.auditoria_repository import AuditoriaRepository
    from services.cegid_auditoria_source import CegidAuditoriaSource
    from services.reconciliation_service import ReconciliationService
    from services.unit_of_work import UnitOfWork


class AuditoriaService:
    def __init__(self, uow_factory=UnitOfWork, cegid_source=None):
        self.uow_factory = uow_factory
        self.cegid_source = cegid_source or CegidAuditoriaSource()

    def resumen(self):
        with self.uow_factory() as uow:
            return ReconciliationService(uow.session).resumen_ejecutivo()

    def explorador(self, proveedor=None, estado=None, marca=None, mes=None, souche=None, limit=200):
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
        with self.uow_factory() as uow:
            return ReconciliationService(uow.session).detalle_documento(documento_id)

    def plan_vs_recepcion(self, proveedor=None, marca=None, mes=None, souche=None, limit=500):
        with self.uow_factory() as uow:
            return ReconciliationService(uow.session).plan_vs_recepcion(
                proveedor=proveedor,
                marca=marca,
                mes=mes,
                souche=souche,
                limit=limit,
            )

    def recepciones_posteriores_def(self, proveedor=None, marca=None, mes=None, souche=None):
        with self.uow_factory() as uow:
            propuestas = ReconciliationService(uow.session).lineas_def(
                proveedor=proveedor,
                marca=marca,
                mes=mes,
                souche=souche,
            )

        codigos = [item["codigo_articulo"] for item in propuestas if item.get("codigo_articulo")]
        desde = f"{mes}-01" if mes else None
        hasta = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")
        rows = self.cegid_source.obtener_recepciones_articulos(codigos, desde=desde, hasta=hasta)
        rows = self.cegid_source.aplicar_talles_por_ean(rows)

        pedidos_por_articulo = {}
        for item in propuestas:
            codigo = item.get("codigo_articulo")
            if not codigo:
                continue
            pedidos_por_articulo.setdefault(codigo, 0)
            pedidos_por_articulo[codigo] += item.get("cantidad_pedida", 0)

        recepciones = {}
        for row in rows:
            codigo = str(row.get("GL_CODEARTICLE", "")).strip()
            normalizada = self.cegid_source.normalizar_ligne(row)
            key = (codigo, normalizada.get("ean"), row.get("GL_SOUCHE"), str(row.get("GL_DATEPIECE"))[:10])
            item = recepciones.setdefault(key, {
                "codigo_articulo": codigo,
                "ean": normalizada.get("ean"),
                "descripcion": normalizada.get("descripcion"),
                "marca": normalizada.get("marca"),
                "genero": normalizada.get("genero"),
                "talle": normalizada.get("talle"),
                "souche": row.get("GL_SOUCHE"),
                "fecha_recepcion": str(row.get("GL_DATEPIECE"))[:10],
                "cantidad_pedida_def": pedidos_por_articulo.get(codigo, 0),
                "cantidad_recibida_blf": 0,
            })
            item["cantidad_recibida_blf"] += float(normalizada.get("cantidad") or 0)

        return sorted(
            recepciones.values(),
            key=lambda item: (item["codigo_articulo"], item["fecha_recepcion"], item["souche"]),
        )

    def registrar_documento(self, proveedor_data, documento_data, lineas):
        with self.uow_factory() as uow:
            repo = AuditoriaRepository(uow.session)
            proveedor = repo.get_or_create_proveedor(**proveedor_data)
            documento_data["proveedor_id"] = proveedor.id
            documento = repo.upsert_documento(documento_data, lineas=lineas)
            return {"id": documento.id, "codigo_documento": documento.codigo_documento}

    def sincronizar_circuito_cegid(self, desde=None, hasta=None, tipos=None, souche=None, incluir_def=False):
        hasta_exclusive = self._hasta_exclusive(hasta)
        tipos_sync = ["CF", "ALF", "BLF"]
        if incluir_def:
            tipos_sync.insert(0, "DEF")

        rows_piece = self.cegid_source.obtener_documentos(
            tipos_sync,
            desde=desde,
            hasta=hasta_exclusive,
            souche=souche,
        )
        rows_ligne = self.cegid_source.obtener_lineas(
            tipos_sync,
            desde=desde,
            hasta=hasta_exclusive,
            souche=souche,
        )
        rows_ligne = self.cegid_source.aplicar_talles_por_ean(rows_ligne)
        documentos_normalizados = [self.cegid_source.normalizar_piece(row) for row in rows_piece]

        lineas_por_documento = {}
        for row in rows_ligne:
            documento_key = self._document_key_from_ligne(row)
            lineas_por_documento.setdefault(documento_key, []).append(row)

        documentos_guardados = 0
        lineas_guardadas = 0

        with self.uow_factory() as uow:
            repo = AuditoriaRepository(uow.session)
            origenes = ["PEDIDO", "NOTIFICACION", "RECEPCION"]
            if incluir_def:
                origenes.append("PROPUESTA")
            eliminados = repo.eliminar_documentos_por_ventana(
                desde=desde,
                hasta=hasta_exclusive,
                souche=souche,
                origenes=origenes,
            )
            for row_piece, documento_data in zip(rows_piece, documentos_normalizados):
                proveedor = repo.get_or_create_proveedor(
                    cod_prov=row_piece.get("GP_TIERS"),
                    marca=None,
                )
                documento_data["proveedor_id"] = proveedor.id

                rows_ligne = lineas_por_documento.get(documento_data["codigo_documento"], [])
                lineas = [
                    self.cegid_source.normalizar_ligne(row)
                    for row in rows_ligne
                    if str(row.get("GL_TYPELIGNE", "")).strip() == "ART"
                ]

                repo.upsert_documento(documento_data, lineas=lineas)
                documentos_guardados += 1
                lineas_guardadas += len(lineas)

        return {
            "documentos": documentos_guardados,
            "lineas": lineas_guardadas,
            "documentos_reemplazados": eliminados,
            "tipos": tipos_sync,
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
