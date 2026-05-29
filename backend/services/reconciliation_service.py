from collections import defaultdict
from datetime import datetime
from decimal import Decimal
from sqlalchemy.orm import Session

try:
    from backend.models import AuditoriaDocumento, AuditoriaDocumentoLinea, AuditoriaProveedor
except ModuleNotFoundError:
    from models import AuditoriaDocumento, AuditoriaDocumentoLinea, AuditoriaProveedor

ORIGEN_PROPUESTA = "PROPUESTA"
ORIGEN_RECEPCION = "RECEPCION"

class ReconciliationService:
    def __init__(self, session: Session):
        self.session = session

    def resumen_ejecutivo(self):
        items = self.plan_vs_recepcion(limit=10000)
        total = len(items)
        completos = sum(1 for item in items if item["estado"] in ("OK_COMPLETO", "DEMORADO_COMPLETO"))
        pendientes = sum(max(item["cantidad_pedida"] - item["cantidad_recibida"], 0) for item in items)
        desfasajes = [
            ingreso.get("dias_desvio", ingreso.get("desvio_meses", 0))
            for item in items
            for ingreso in item.get("historial_detalle", [])
            if ingreso.get("dias_desvio", ingreso.get("desvio_meses", 0)) > 0
        ]
        return {
            "otif_general": round((completos / total * 100), 2) if total else 0,
            "monto_en_riesgo": 0,
            "promedio_retraso": round(sum(desfasajes) / len(desfasajes), 2) if desfasajes else 0,
            "documentos_analizados": total,
            "unidades_pendientes": round(pendientes, 4),
        }

    def explorador_cumplimiento(self, proveedor=None, estado=None, marca=None, mes=None, souche=None, limit=200):
        items = self.plan_vs_recepcion(
            proveedor=proveedor,
            marca=marca,
            mes=mes,
            souche=souche,
            limit=limit,
        )
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

        return {
            "documento": {
                "id": documento.id,
                "origen": documento.origen,
                "codigo_documento": documento.codigo_documento,
                "cegid_souche": documento.cegid_souche,
                "cegid_numero": documento.cegid_numero,
                "fecha_documento": documento.fecha_documento.isoformat() if documento.fecha_documento else None,
                "fecha_entrega_prevista": documento.fecha_entrega_prevista.isoformat() if documento.fecha_entrega_prevista else None,
                "estado": documento.estado,
            },
            "lineas": [
                {
                    "ean": linea.ean,
                    "codigo_articulo": linea.codigo_articulo,
                    "descripcion": linea.descripcion,
                    "talle": linea.talle,
                    "marca": linea.marca,
                    "genero": linea.genero,
                    "deposito": linea.deposito,
                    "cantidad": float(linea.cantidad or 0),
                }
                for linea in documento.lineas
            ],
        }

    def _get_quarter_bounds(self, year: int, quarter_num: int):
        """Retorna las fechas límites de inicio y fin para un trimestre (Q)."""
        mapping = {
            1: (datetime(year, 1, 1), datetime(year, 3, 31, 23, 59, 59)),
            2: (datetime(year, 4, 1), datetime(year, 6, 30, 23, 59, 59)),
            3: (datetime(year, 7, 1), datetime(year, 9, 30, 23, 59, 59)),
            4: (datetime(year, 10, 1), datetime(year, 12, 31, 23, 59, 59))
        }
        return mapping.get(quarter_num)

    def _calcular_desfase_meses(self, fecha_real: datetime, fecha_limite: datetime) -> int:
        """Calcula la demora en meses calendario si la entrega superó el límite de tolerancia."""
        if fecha_real <= fecha_limite:
            return 0
        return (fecha_real.year - fecha_limite.year) * 12 + (fecha_real.month - fecha_limite.month)

    def plan_vs_recepcion(self, proveedor=None, marca=None, mes=None, souche=None, limit=500, recepcion_souche="__same__"):
        """
        Engine V2: Asignación por casilleros dinámicos con soporte para ventanas macro Q.
        """
        # 1. Recuperar todas las demandas (DEF)
        query_def = (
            self.session.query(AuditoriaDocumentoLinea, AuditoriaDocumento, AuditoriaProveedor)
            .join(AuditoriaDocumento, AuditoriaDocumentoLinea.documento_id == AuditoriaDocumento.id)
            .outerjoin(AuditoriaProveedor, AuditoriaDocumento.proveedor_id == AuditoriaProveedor.id)
            .filter(AuditoriaDocumento.origen == ORIGEN_PROPUESTA)
        )
        
        if proveedor:
            query_def = query_def.filter(AuditoriaProveedor.cod_prov == proveedor)
        if souche:
            query_def = query_def.filter(AuditoriaDocumento.cegid_souche == souche)
        if marca:
            query_def = query_def.filter(AuditoriaDocumentoLinea.marca == marca)

        lineas_def = query_def.all()
        if not lineas_def:
            return []

        casilleros_demanda = defaultdict(list)
        eans_solicitados = set()

        # Parsear e inicializar horizontes temporales
        for linea, doc, prov in lineas_def:
            if not linea.ean:
                continue
            
            ref_int = str(doc.ref_interna or "").upper()
            fecha_promesa_base = doc.fecha_entrega_prevista or doc.fecha_documento
            
            # Identificación de Ventana de Tolerancia Abierta (Q)
            es_quarter = False
            fecha_limite_tolerancia = fecha_promesa_base
            etiqueta_horizonte = fecha_promesa_base.strftime("%Y-%m")

            for q_idx in ["Q1", "Q2", "Q3", "Q4"]:
                if q_idx in ref_int:
                    es_quarter = True
                    q_num = int(q_idx[1])
                    year_target = fecha_promesa_base.year
                    inicio_q, fin_q = self._get_quarter_bounds(year_target, q_num)
                    fecha_limite_tolerancia = fin_q
                    etiqueta_horizonte = f"{q_idx}/{year_target}"
                    break

            # Si el usuario filtró por un mes específico, validamos si la fila pertenece a ese mes o a su Q
            if mes:
                filtro_target = datetime.strptime(f"{mes}-01", "%Y-%m-%d")
                if es_quarter:
                    # Si es un Q, entra si el mes filtrado pertenece al mismo rango del Q
                    if not (inicio_q <= filtro_target <= fin_q):
                        continue
                else:
                    if fecha_promesa_base.strftime("%Y-%m") != mes:
                        continue

            eans_solicitados.add(linea.ean)
            casilleros_demanda[linea.ean].append({
                "linea_id": linea.id,
                "proveedor": prov.cod_prov if prov else "",
                "marca": linea.marca or "",
                "ean": linea.ean,
                "codigo_articulo": linea.codigo_articulo,
                "descripcion": linea.descripcion,
                "talle": linea.talle or "",
                "genero": linea.genero or "",
                "horizonte": etiqueta_horizonte,
                "es_quarter": es_quarter,
                "fecha_limite": fecha_limite_tolerancia,
                "cantidad_pedida": linea.cantidad,
                "cantidad_recibida": Decimal("0.0000"),
                "historial_ingresos": []
            })

        if not eans_solicitados:
            return []

        # Ordenar casilleros por fecha límite para mantener la prioridad FIFO
        for ean in casilleros_demanda:
            casilleros_demanda[ean].sort(key=lambda x: x["fecha_limite"])

        # 2. Extraer Recepciones (BLF) con un margen seguro hacia atrás (Look-back de 60 días)
        query_blf = (
            self.session.query(AuditoriaDocumentoLinea, AuditoriaDocumento)
            .join(AuditoriaDocumento, AuditoriaDocumentoLinea.documento_id == AuditoriaDocumento.id)
            .filter(
                AuditoriaDocumento.origen == ORIGEN_RECEPCION,
                AuditoriaDocumentoLinea.ean.in_(list(eans_solicitados))
            )
        )
        if recepcion_souche == "__same__":
            recepcion_souche = souche
        if recepcion_souche:
            query_blf = query_blf.filter(AuditoriaDocumento.cegid_souche == recepcion_souche)
        query_blf = query_blf.order_by(AuditoriaDocumento.fecha_documento.asc())
        
        # 3. Distribución FIFO Dinámica
        for linea_blf, doc_blf in query_blf.all():
            ean_blf = linea_blf.ean
            cantidad_disponible = linea_blf.cantidad

            if ean_blf not in casilleros_demanda:
                continue

            for casillero in casilleros_demanda[ean_blf]:
                if cantidad_disponible <= 0:
                    break

                deuda = casillero["cantidad_pedida"] - casillero["cantidad_recibida"]
                if deuda <= 0:
                    continue

                cantidad_a_asignar = min(cantidad_disponible, deuda)
                casillero["cantidad_recibida"] += cantidad_a_asignar
                cantidad_disponible -= cantidad_a_asignar

                # Cálculo de desvío basado en mes calendario
                desfase_meses = self._calcular_desfase_meses(doc_blf.fecha_documento, casillero["fecha_limite"])
                
                if desfase_meses == 0:
                    sla_status = "A tiempo" if doc_blf.fecha_documento >= casillero["fecha_limite"].replace(day=1) else "Adelantado"
                else:
                    sla_status = f"Demorado (+{desfase_meses} mes/es)"

                casillero["historial_ingresos"].append({
                    "comprobante": doc_blf.codigo_documento.split("|")[2] if doc_blf.codigo_documento else "S/D",
                    "fecha_ingreso": doc_blf.fecha_documento.strftime("%Y-%m-%d"),
                    "cantidad_ingresada": float(cantidad_a_asignar),
                    "dias_desvio": desfase_meses,
                    "desvio_meses": desfase_meses,
                    "etiqueta_tiempo": sla_status
                })

        # 4. Formatear reporte consolidado para la UI
        resultados = []
        for ean, lista_casilleros in casilleros_demanda.items():
            for c in lista_casilleros:
                pedida = c["cantidad_pedida"]
                recibida = c["cantidad_recibida"]
                
                if recibida == 0:
                    estado_final = "NO_RECIBIDO"
                elif recibida < pedida:
                    estado_final = "PARCIAL"
                else:
                    tuvo_demoras = any(ing.get("dias_desvio", ing.get("desvio_meses", 0)) > 0 for ing in c["historial_ingresos"])
                    estado_final = "DEMORADO_COMPLETO" if tuvo_demoras else "OK_COMPLETO"

                resultados.append({
                    "id": c["linea_id"],
                    "proveedor": c["proveedor"],
                    "marca": c["marca"],
                    "ean": c["ean"],
                    "codigo_articulo": c["codigo_articulo"],
                    "descripcion": c["descripcion"],
                    "talle": c["talle"],
                    "genero": c["genero"],
                    "mes_planificado": c["horizonte"],
                    "cantidad_pedida": float(pedida),
                    "cantidad_recibida": float(recibida),
                    "diferencia": float(recibida - pedida),
                    "cumplimiento": round(float((recibida / pedida) * 100), 2) if pedida > 0 else 0.0,
                    "estado": estado_final,
                    "historial_detalle": c["historial_ingresos"]
                })

        return sorted(resultados, key=lambda x: (x["estado"], x["codigo_articulo"], x["talle"]))[:limit]
