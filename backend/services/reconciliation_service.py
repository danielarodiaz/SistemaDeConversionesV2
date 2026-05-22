from collections import defaultdict
from datetime import datetime

try:
    from backend.models import AuditoriaDocumento, AuditoriaDocumentoLinea, AuditoriaProveedor
    from backend.services.auditoria_repository import decimal_to_float
except ModuleNotFoundError:
    from models import AuditoriaDocumento, AuditoriaDocumentoLinea, AuditoriaProveedor
    from services.auditoria_repository import decimal_to_float


ORIGEN_PROPUESTA = "PROPUESTA"
ORIGEN_PEDIDO = "PEDIDO"
ORIGEN_NOTIFICACION = "NOTIFICACION"
ORIGEN_RECEPCION = "RECEPCION"


class ReconciliationService:
    def __init__(self, session):
        self.session = session

    def resumen_ejecutivo(self):
        lineas = self._query_lineas().all()
        resumen = self._agrupar_por_documento(lineas)

        total = len(resumen)
        perfectos = sum(1 for item in resumen if item["estado"] == "OK")
        pendiente_recibir = sum(
            max(item["cantidad_pedida"] - item["cantidad_recibida"], 0) * item["precio_promedio"]
            for item in resumen
        )
        retrasos = [item["dias_retraso"] for item in resumen if item["dias_retraso"] is not None]

        return {
            "otif_general": round((perfectos / total * 100), 2) if total else 0,
            "monto_en_riesgo": round(pendiente_recibir, 2),
            "promedio_retraso": round(sum(retrasos) / len(retrasos), 2) if retrasos else 0,
            "documentos_analizados": total,
        }

    def explorador_cumplimiento(self, proveedor=None, estado=None, marca=None, mes=None, souche=None, limit=200):
        lineas = self._query_lineas(proveedor=proveedor, marca=marca, mes=mes, souche=souche).all()
        items = self._agrupar_por_documento(lineas)
        if estado:
            items = [item for item in items if item["estado"] == estado]
        return items[:limit]

    def detalle_documento(self, documento_id):
        documento = (
            self.session.query(AuditoriaDocumento)
            .filter(AuditoriaDocumento.id == documento_id)
            .first()
        )
        if not documento:
            return None

        detalle = defaultdict(lambda: {
            "ean": "",
            "codigo_articulo": "",
            "descripcion": "",
            "talle": "",
            "marca": "",
            "genero": "",
            "deposito": "",
            "cantidad_pedida": 0.0,
            "cantidad_facturada": 0.0,
            "cantidad_notificada": 0.0,
            "cantidad_recibida": 0.0,
        })

        circuito_key = self._documento_circuito_key(documento)
        lineas = self._query_lineas().filter(
            (AuditoriaDocumento.codigo_documento == circuito_key)
            | (AuditoriaDocumentoLinea.pieza_origen == circuito_key)
        ).all()

        for linea, doc, _proveedor in lineas:
            key = linea.ean or linea.codigo_articulo or f"linea-{linea.id}"
            item = detalle[key]
            item["ean"] = linea.ean or ""
            item["codigo_articulo"] = linea.codigo_articulo or ""
            item["descripcion"] = linea.descripcion or ""
            item["talle"] = linea.talle or ""
            item["marca"] = linea.marca or ""
            item["genero"] = linea.genero or ""
            item["deposito"] = linea.deposito or ""
            cantidad = decimal_to_float(linea.cantidad)
            if doc.origen == ORIGEN_PROPUESTA:
                item["cantidad_pedida"] += cantidad
            elif doc.origen == ORIGEN_PEDIDO:
                item["cantidad_facturada"] += cantidad
            elif doc.origen == ORIGEN_NOTIFICACION:
                item["cantidad_notificada"] += cantidad
            elif doc.origen == ORIGEN_RECEPCION:
                item["cantidad_recibida"] += cantidad

        return {
            "documento": self._documento_to_dict(documento),
            "lineas": [self._estado_linea(item) for item in detalle.values()],
        }

    def plan_vs_recepcion(self, proveedor=None, marca=None, mes=None, souche=None, limit=500):
        query = self._query_lineas(proveedor=proveedor, marca=marca, souche=souche)
        if mes:
            desde, hasta = self._month_bounds(mes)
            query = query.filter(
                (
                    (AuditoriaDocumento.origen == ORIGEN_PROPUESTA)
                    & (AuditoriaDocumento.fecha_entrega_prevista >= desde)
                    & (AuditoriaDocumento.fecha_entrega_prevista < hasta)
                )
                | (
                    (AuditoriaDocumento.origen == ORIGEN_RECEPCION)
                    & (AuditoriaDocumento.fecha_documento >= desde)
                    & (AuditoriaDocumento.fecha_documento < hasta)
                )
            )

        grupos = defaultdict(lambda: {
            "proveedor": "",
            "marca": "",
            "ean": "",
            "codigo_articulo": "",
            "descripcion": "",
            "talle": "",
            "genero": "",
            "cantidad_pedida": 0.0,
            "cantidad_recibida": 0.0,
        })

        for linea, doc, prov in query.all():
            if doc.origen not in (ORIGEN_PROPUESTA, ORIGEN_RECEPCION):
                continue
            key = linea.ean or f"{linea.codigo_articulo}|{linea.talle}"
            item = grupos[key]
            item["proveedor"] = prov.cod_prov if prov else ""
            item["marca"] = linea.marca or item["marca"]
            item["ean"] = linea.ean or ""
            item["codigo_articulo"] = linea.codigo_articulo or ""
            item["descripcion"] = linea.descripcion or ""
            item["talle"] = linea.talle or ""
            item["genero"] = linea.genero or ""
            cantidad = decimal_to_float(linea.cantidad)
            if doc.origen == ORIGEN_PROPUESTA:
                item["cantidad_pedida"] += cantidad
            elif doc.origen == ORIGEN_RECEPCION:
                item["cantidad_recibida"] += cantidad

        salida = []
        for item in grupos.values():
            pedido = item["cantidad_pedida"]
            recibido = item["cantidad_recibida"]
            item["diferencia"] = recibido - pedido
            item["cumplimiento"] = round((recibido / pedido * 100), 2) if pedido else None
            if not pedido and recibido:
                item["estado"] = "SIN_PROPUESTA_EN_MES"
            elif pedido and not recibido:
                item["estado"] = "NO_RECIBIDO"
            elif recibido < pedido:
                item["estado"] = "PARCIAL"
            elif recibido > pedido:
                item["estado"] = "SOBRE_RECIBIDO"
            else:
                item["estado"] = "OK"
            salida.append(item)

        return sorted(salida, key=lambda x: (x["estado"], x["codigo_articulo"], x["talle"]))[:limit]

    def _query_lineas(self, proveedor=None, marca=None, mes=None, souche=None):
        query = (
            self.session.query(AuditoriaDocumentoLinea, AuditoriaDocumento, AuditoriaProveedor)
            .join(AuditoriaDocumento, AuditoriaDocumentoLinea.documento_id == AuditoriaDocumento.id)
            .outerjoin(AuditoriaProveedor, AuditoriaDocumento.proveedor_id == AuditoriaProveedor.id)
        )
        if proveedor:
            query = query.filter(AuditoriaProveedor.cod_prov == proveedor)
        if souche:
            query = query.filter(AuditoriaDocumento.cegid_souche == souche)
        if marca:
            query = query.filter(AuditoriaDocumentoLinea.marca == marca)
        if mes:
            desde, hasta = self._month_bounds(mes)
            query = query.filter(
                AuditoriaDocumento.fecha_entrega_prevista >= desde,
                AuditoriaDocumento.fecha_entrega_prevista < hasta,
            )
        return query

    def _agrupar_por_documento(self, lineas):
        grupos = {}
        for linea, doc, proveedor in lineas:
            key = self._grupo_circuito_key(linea, doc)
            if key not in grupos:
                grupos[key] = {
                    "documento_id": doc.id,
                    "codigo_documento": key,
                    "proveedor": proveedor.cod_prov if proveedor else "",
                    "cegid_souche": doc.cegid_souche,
                    "marca": proveedor.marca if proveedor else "",
                    "fecha_documento": doc.fecha_documento.isoformat() if doc.fecha_documento else None,
                    "fecha_entrega_prevista": doc.fecha_entrega_prevista.isoformat() if doc.fecha_entrega_prevista else None,
                    "cantidad_pedida": 0.0,
                    "cantidad_facturada": 0.0,
                    "cantidad_notificada": 0.0,
                    "cantidad_recibida": 0.0,
                    "importe_facturado": 0.0,
                    "dias_retraso": None,
                    "articulos": 0,
                    "_eans": set(),
                    "_marcas": set(),
                }

            item = grupos[key]
            if linea.ean:
                item["_eans"].add(linea.ean)
            if linea.marca:
                item["_marcas"].add(linea.marca)
            cantidad = decimal_to_float(linea.cantidad)
            importe = decimal_to_float(linea.importe)
            precio = decimal_to_float(linea.precio_unitario)
            if doc.origen == ORIGEN_PROPUESTA:
                item["cantidad_pedida"] += cantidad
            elif doc.origen == ORIGEN_PEDIDO:
                item["cantidad_facturada"] += cantidad
            elif doc.origen == ORIGEN_NOTIFICACION:
                item["cantidad_notificada"] += cantidad
            elif doc.origen == ORIGEN_RECEPCION:
                item["cantidad_recibida"] += cantidad

        salida = []
        for item in grupos.values():
            item["articulos"] = len(item["_eans"])
            if item["_marcas"]:
                item["marca"] = ", ".join(sorted(item["_marcas"]))
            del item["_eans"]
            del item["_marcas"]
            salida.append(self._estado_documento(item))
        return salida

    def _estado_documento(self, item):
        facturado = item["cantidad_facturada"]
        notificado = item["cantidad_notificada"]
        recibido = item["cantidad_recibida"]
        pedido = item["cantidad_pedida"]

        item["precio_promedio"] = item["importe_facturado"] / facturado if facturado else 0
        item["cumplimiento"] = round((recibido / pedido * 100), 2) if pedido else None

        if not pedido:
            item["estado"] = "PROPUESTA_NO_CARGADA"
        elif pedido and recibido < pedido:
            item["estado"] = "PENDIENTE_RECEPCION"
        elif pedido and recibido > pedido:
            item["estado"] = "SOBRE_ENTREGA"
        elif pedido and notificado < pedido:
            item["estado"] = "NOTIFICACION_PARCIAL"
        elif pedido and recibido >= pedido:
            item["estado"] = "OK"
        else:
            item["estado"] = "PENDIENTE"
        return item

    def _estado_linea(self, item):
        if not item["cantidad_pedida"]:
            item["estado"] = "PROPUESTA_NO_CARGADA"
        elif item["cantidad_pedida"] and item["cantidad_recibida"] < item["cantidad_pedida"]:
            item["estado"] = "FALTANTE_FISICO"
        elif item["cantidad_pedida"] and item["cantidad_recibida"] > item["cantidad_pedida"]:
            item["estado"] = "SOBRE_ENTREGA"
        else:
            item["estado"] = "OK"
        return item

    def _documento_to_dict(self, documento):
        return {
            "id": documento.id,
            "origen": documento.origen,
            "codigo_documento": documento.codigo_documento,
            "documento_relacionado": documento.documento_relacionado,
            "estado": documento.estado,
        }

    def _documento_circuito_key(self, documento):
        if documento.origen == ORIGEN_PEDIDO:
            return documento.codigo_documento

        linea = (
            self.session.query(AuditoriaDocumentoLinea)
            .filter(
                AuditoriaDocumentoLinea.documento_id == documento.id,
                AuditoriaDocumentoLinea.pieza_origen.isnot(None),
            )
            .first()
        )
        return linea.pieza_origen if linea else documento.codigo_documento

    def _grupo_circuito_key(self, linea, doc):
        if doc.origen in (ORIGEN_NOTIFICACION, ORIGEN_RECEPCION) and linea.pieza_origen:
            return linea.pieza_origen
        return doc.documento_relacionado or doc.codigo_documento

    def _month_bounds(self, mes):
        inicio = datetime.strptime(f"{mes}-01", "%Y-%m-%d")
        if inicio.month == 12:
            fin = inicio.replace(year=inicio.year + 1, month=1)
        else:
            fin = inicio.replace(month=inicio.month + 1)
        return inicio, fin
