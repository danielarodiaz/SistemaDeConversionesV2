import os
import re
from datetime import datetime

import pandas as pd

from backend.database import SessionLocal
from backend.models import Sucursal
from backend.utils.pedido_helpers import (
    detectar_conflictos_suc,
    formatear_precio,
    resolver_establecimiento,
    armar_item_auditoria,
    ejecutar_auditoria_y_exportar,
)

_COLUMNAS_REPORTE = [
    "Suc",
    "EAN",
    "SKU",
    "Descripcion",
    "Talle",
    "Color",
    "Comprobante",
    "Remito",
    "Cliente",
    "Cantidad",
    "P. Unitario",
]


def _buscar_columna(columns: list, posibles: list) -> str | None:
    normalizadas = {str(c).strip().lower(): c for c in columns}
    for nombre in posibles:
        key = str(nombre).strip().lower()
        if key in normalizadas:
            return normalizadas[key]
    return None


def _formatear_remito(valor) -> str:
    if valor is None:
        return ""
    try:
        if pd.isna(valor):
            return ""
    except (TypeError, ValueError):
        pass
    digits = "".join(ch for ch in str(valor).strip() if ch.isdigit())
    if not digits:
        return ""
    digits = digits.zfill(12)
    return f"{digits[:4]}-{digits[4:]}"


def _ean_a_str(valor) -> str:
    if valor is None:
        return ""
    try:
        if pd.isna(valor):
            return ""
    except (TypeError, ValueError):
        pass
    if isinstance(valor, float):
        return str(int(round(valor)))
    s = str(valor).strip()
    if re.fullmatch(r"\d+\.0", s):
        s = s[:-2]
    return s


def _parsear_preuni(valor) -> float:
    if valor is None:
        raise ValueError("P. Unitario vacío")
    try:
        if pd.isna(valor):
            raise ValueError("P. Unitario vacío")
    except (TypeError, ValueError):
        pass
    if isinstance(valor, (int, float)) and not isinstance(valor, bool):
        return round(float(valor), 2)
    s = str(valor).strip().replace("$", "").replace(" ", "")
    if not s:
        raise ValueError("P. Unitario vacío")
    if "," in s and "." in s:
        s = s.replace(".", "").replace(",", ".")
    elif "," in s:
        s = s.replace(",", ".")
    return round(float(s), 2)


def _parsear_cantidad(valor) -> int:
    if valor is None:
        raise ValueError("Cantidad vacía")
    try:
        if pd.isna(valor):
            raise ValueError("Cantidad vacía")
    except (TypeError, ValueError):
        pass
    if isinstance(valor, (int, float)) and not isinstance(valor, bool):
        return int(round(float(valor)))
    s = str(valor).strip().replace(" ", "")
    if not s:
        raise ValueError("Cantidad vacía")
    s = s.replace(".", "").replace(",", ".")
    return int(round(float(s)))


def _extraer_establecimiento_y_suc(cliente: str) -> tuple[str, str]:
    texto = str(cliente or "").strip()
    if not texto:
        raise ValueError("Cliente vacío")
    match = re.search(r"\bSUC\b", texto, flags=re.IGNORECASE)
    if match:
        antes = texto[:match.start()].strip()
        despues = texto[match.end():].strip()
        establecimiento = resolver_establecimiento(antes)
        suc_match = re.search(r"\d{5,6}", despues)
    else:
        establecimiento = resolver_establecimiento(texto)
        suc_match = re.search(r"\d{5,6}", texto)
    if not suc_match:
        raise ValueError(f"Sucursal no encontrada en Cliente: {texto!r}")
    suc = suc_match.group(0).zfill(6)
    return establecimiento, suc


def _leer_archivo(input_path: str) -> pd.DataFrame:
    ext = os.path.splitext(input_path)[1].lower()
    if ext in {".txt", ".tsv", ".csv"}:
        data = pd.read_csv(input_path, sep="\t", dtype=str)
    else:
        data = pd.read_excel(input_path, dtype=str)
    data.columns = data.columns.str.strip()
    return data


def _obtener_codigos_sucursales() -> set[str]:
    db = SessionLocal()
    try:
        return {
            str(codigo).strip()
            for (codigo,) in db.query(Sucursal.codigo_sucursal).all()
            if codigo is not None
        }
    finally:
        db.close()


def _extraer_suc_para_conflicto(valor) -> str | None:
    try:
        return _extraer_establecimiento_y_suc(valor)[1]
    except Exception:
        return None


def process_proyec_pedido_proveedor(input_path: str, output_path: str) -> dict | None:
    """
    Procesa un archivo de Proyec.
    Columnas esperadas: SKU, Descripcion, Talle, Color, EAN, Cantidad, P. Unitario,
    Total, Comprobante, Remito, Cliente.
    """
    try:
        data = _leer_archivo(input_path)
        if data.empty:
            return None

        col_sku = _buscar_columna(data.columns, ["SKU"])
        col_desc = _buscar_columna(data.columns, ["Descripcion", "Descripción"])
        col_talle = _buscar_columna(data.columns, ["Talle"])
        col_color = _buscar_columna(data.columns, ["Color"])
        col_ean = _buscar_columna(data.columns, ["EAN"])
        col_cant = _buscar_columna(data.columns, ["Cantidad"])
        col_preuni = _buscar_columna(data.columns, ["P. Unitario", "P.Unitario", "P Unitario"])
        col_total = _buscar_columna(data.columns, ["Total"])
        col_comp = _buscar_columna(data.columns, ["Comprobante"])
        col_remito = _buscar_columna(data.columns, ["Remito"])
        col_cliente = _buscar_columna(data.columns, ["Cliente"])

        columnas_faltantes = [
            nombre for nombre, col in {
                "SKU": col_sku,
                "Descripcion": col_desc,
                "Talle": col_talle,
                "Color": col_color,
                "EAN": col_ean,
                "Cantidad": col_cant,
                "P. Unitario": col_preuni,
                "Comprobante": col_comp,
                "Remito": col_remito,
                "Cliente": col_cliente,
            }.items() if col is None
        ]
        if columnas_faltantes:
            raise RuntimeError(f"Faltan columnas requeridas: {', '.join(columnas_faltantes)}")

        data["Suc"] = data[col_cliente].apply(_extraer_suc_para_conflicto)
        conflictos_suc = detectar_conflictos_suc(data, _COLUMNAS_REPORTE)

        codigos_sucursales = _obtener_codigos_sucursales()
        alertas_sucursales = {}
        avisos_sucursales = {}

        registros_cegid = []
        items_auditoria = []
        fecha_str = datetime.now().strftime("%d%m%y")

        for i, row in data.iterrows():
            try:
                referencia_formateada = _formatear_remito(row[col_remito])
                codigo_barras = _ean_a_str(row[col_ean])
                if not referencia_formateada or not codigo_barras:
                    continue
                cantidad = _parsear_cantidad(row[col_cant])
                precio_float = _parsear_preuni(row[col_preuni])

                cliente_raw = str(row[col_cliente]).strip()
                establecimiento, almacen = _extraer_establecimiento_y_suc(cliente_raw)
                if almacen not in codigos_sucursales:
                    info = {
                        "Suc": almacen,
                        "Cliente": cliente_raw,
                        "Remito": referencia_formateada,
                    }
                    if almacen == "240001":
                        avisos_sucursales.setdefault(almacen, info)
                    else:
                        alertas_sucursales.setdefault(almacen, info)

                codigo_articulo = str(row[col_sku]).strip()
                descripcion = str(row[col_desc]).strip()
                talle = str(row[col_talle]).strip()
                color = str(row[col_color]).strip()
                comprobante = str(row[col_comp]).strip()
                total_raw = str(row[col_total]).strip() if col_total else ""

                registros_cegid.append(
                    {
                        "CAB": "ZCOC1_",
                        "REFERENCIA INTERNA": referencia_formateada,
                        "FECHA": fecha_str,
                        "COD PROVEEDOR": "SPSER",
                        "CODIGO BARRAS": codigo_barras,
                        "CANTIDAD": cantidad,
                        "PRECIO": formatear_precio(precio_float),
                        "ALMACEN": almacen,
                        "ESTABLECIMIENTO": establecimiento,
                        "DESCUENTO": 0,
                    }
                )
                items_auditoria.append(
                    armar_item_auditoria(
                        barras=codigo_barras,
                        articulo=codigo_articulo,
                        precio_float=precio_float,
                        detalles={
                            "Material": codigo_articulo,
                            "Descripción": descripcion,
                            "Size": talle,
                            "Color": color,
                            "Codigo_EAN": codigo_barras,
                            "Comprobante": comprobante,
                            "Cliente": cliente_raw,
                            "Total": total_raw,
                            "Precio": precio_float,
                        },
                    )
                )
            except Exception as e:
                print(f"❌ Error en fila {i}: {e}")
                continue

        if not registros_cegid:
            return None

        informe = ejecutar_auditoria_y_exportar(
            items_auditoria,
            registros_cegid,
            output_path,
            proveedor="PROYEC",
            conflictos_suc=conflictos_suc,
            sort_by="REFERENCIA INTERNA",
        )

        if alertas_sucursales:
            codigos = ", ".join(sorted(alertas_sucursales.keys()))
            print(f"🚨 Sucursales no encontradas en base de datos: {codigos}")
            informe["alertas_sucursales"] = list(alertas_sucursales.values())
        if avisos_sucursales:
            codigos = ", ".join(sorted(avisos_sucursales.keys()))
            print(f"ℹ️ Sucursales con código por defecto: {codigos}")
            informe["avisos_sucursales"] = list(avisos_sucursales.values())

        return informe

    except Exception as e:
        raise RuntimeError(f"Error crítico en procesador PROYEC: {e}")
