import csv
from typing import List, Dict, Tuple

import pandas as pd

from backend.utils.cegid_utils import obtener_costos_por_codigos_barras


def _formatear_fecha_ddmmaa(fecha_str: str) -> str:
    try:
        fecha = pd.to_datetime(fecha_str, dayfirst=True, errors="coerce")
        if pd.isna(fecha):
            return ""
        return fecha.strftime("%d%m%y")
    except Exception:
        return ""


def process_leuru_pedido_proveedor(input_path: str, output_path: str) -> None:
    """
    Lee un .txt separado por comas con filas como:
      E,0300,00043709,14/10/25,000001,852290052030,     4,04807429

    Y exporta un .csv delimitado por '|' con columnas:
      CAB|REFERENCIA INTERNA|FECHA|COD PROVEEDOR|CODIGO BARRAS|CANTIDAD|PRECIO|ALMACEN|ESTABLECIMIENTO|DESCUENTO

    Reglas:
      - CAB: "ZCOC1_"
      - REFERENCIA INTERNA: col2 + '-' + col3 (p.ej. 0300-00043709)
      - FECHA: col4 en formato ddmmyy (p.ej. 141025)
      - COD PROVEEDOR: "LEURU"
      - CODIGO BARRAS: col6
      - CANTIDAD: col7 (entero)
      - PRECIO: desde CEGID por código de barras (precio de compra). Si no se encuentra, 0.0
      - ALMACEN: "240001"
      - ESTABLECIMIENTO: por defecto "002"
      - DESCUENTO: 0
    """

    CAB = "ZCOC1_"
    COD_PROVEEDOR = "LEURU"
    ALMACEN = "240001"
    ESTABLECIMIENTO_DEF = "002"
    DESCUENTO = 0

    registros: List[Dict[str, object]] = []
    codigos_barras: List[str] = []

    with open(input_path, "r", encoding="utf-8") as f:
        reader = csv.reader(f, delimiter=",")
        for cols in reader:
            if not cols or len(cols) < 8:
                continue

            try:
                col2 = str(cols[1]).strip()
                col3 = str(cols[2]).strip()
                col4 = str(cols[3]).strip()
                codigo_barra = str(cols[5]).strip()
                cantidad_raw = str(cols[6]).strip()

                if not col2 or not col3 or not col4 or not codigo_barra:
                    continue

                referencia_interna = f"{col2}-{col3}"
                fecha = _formatear_fecha_ddmmaa(col4)

                try:
                    cantidad = int(cantidad_raw.replace(" ", ""))
                except Exception:
                    try:
                        cantidad = int(float(cantidad_raw.replace(",", ".")))
                    except Exception:
                        continue

                codigos_barras.append(codigo_barra)

                registros.append(
                    {
                        "CAB": CAB,
                        "REFERENCIA INTERNA": referencia_interna,
                        "FECHA": fecha,
                        "COD PROVEEDOR": COD_PROVEEDOR,
                        "CODIGO BARRAS": codigo_barra,
                        "CANTIDAD": cantidad,
                        "PRECIO": None,
                        "ALMACEN": ALMACEN,
                        "ESTABLECIMIENTO": ESTABLECIMIENTO_DEF,
                        "DESCUENTO": DESCUENTO,
                    }
                )
            except Exception:
                continue

    precios_por_cb: Dict[str, Tuple[str, float, str]] = obtener_costos_por_codigos_barras(
        codigos_barras
    )
    for reg in registros:
        cb = reg["CODIGO BARRAS"]
        precio = 0.0
        if cb in precios_por_cb:
            try:
                precio_compra = precios_por_cb[cb][1]
                if precio_compra is not None:
                    precio = float(precio_compra)
            except Exception:
                precio = 0.0
        reg["PRECIO"] = precio

    if registros:
        df = pd.DataFrame(registros, columns=[
            "CAB",
            "REFERENCIA INTERNA",
            "FECHA",
            "COD PROVEEDOR",
            "CODIGO BARRAS",
            "CANTIDAD",
            "PRECIO",
            "ALMACEN",
            "ESTABLECIMIENTO",
            "DESCUENTO",
        ])
        df.to_csv(output_path, sep="|", index=False, header=True)
    else:
        with open(output_path, "w", encoding="utf-8", newline="") as f_out:
            writer = csv.writer(f_out, delimiter='|')
            writer.writerow([
                "CAB",
                "REFERENCIA INTERNA",
                "FECHA",
                "COD PROVEEDOR",
                "CODIGO BARRAS",
                "CANTIDAD",
                "PRECIO",
                "ALMACEN",
                "ESTABLECIMIENTO",
                "DESCUENTO",
            ])

