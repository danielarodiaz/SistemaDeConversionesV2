try:
    from backend.services.auditoria_repository import AuditoriaRepository
    from backend.services.cegid_auditoria_source import CegidAuditoriaSource
    from backend.services.reconciliation_service import ReconciliationService
    from backend.services.unit_of_work import UnitOfWork
except ModuleNotFoundError:
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

    def registrar_documento(self, proveedor_data, documento_data, lineas):
        with self.uow_factory() as uow:
            repo = AuditoriaRepository(uow.session)
            proveedor = repo.get_or_create_proveedor(**proveedor_data)
            documento_data["proveedor_id"] = proveedor.id
            documento = repo.upsert_documento(documento_data, lineas=lineas)
            return {"id": documento.id, "codigo_documento": documento.codigo_documento}

    def sincronizar_circuito_cegid(self, desde=None, hasta=None, tipos=None, souche=None, incluir_def=False):
        rows_cf = self.cegid_source.obtener_documentos(
            ["CF"],
            desde=desde,
            hasta=hasta,
            souche=souche,
        )

        cf_docs = [self.cegid_source.normalizar_piece(row) for row in rows_cf]
        alf_keys = [doc.get("ref_siguiente") for doc in cf_docs if doc.get("ref_siguiente")]
        rows_alf = self.cegid_source.obtener_documentos_por_claves(alf_keys)

        alf_docs = [self.cegid_source.normalizar_piece(row) for row in rows_alf]
        blf_keys = [doc.get("ref_siguiente") for doc in alf_docs if doc.get("ref_siguiente")]
        rows_blf = self.cegid_source.obtener_documentos_por_claves(blf_keys)

        rows_def = []
        if incluir_def:
            rows_def = self.cegid_source.obtener_documentos(
                ["DEF"],
                desde=desde,
                hasta=hasta,
                souche=souche,
            )

        rows_piece = rows_def + rows_cf + rows_alf + rows_blf
        documentos_normalizados = [self.cegid_source.normalizar_piece(row) for row in rows_piece]
        documento_keys = [doc["codigo_documento"] for doc in documentos_normalizados]
        rows_ligne = self.cegid_source.obtener_lineas_por_claves(documento_keys)

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
                hasta=hasta,
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
            "tipos": ["CF", "ALF", "BLF"],
        }

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
