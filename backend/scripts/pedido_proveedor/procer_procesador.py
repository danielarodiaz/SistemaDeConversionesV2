import re
import pandas as pd
from backend.utils.pedido_helpers import (
    detectar_conflictos_suc,
    formatear_precio,
    resolver_establecimiento,
    armar_item_auditoria,
    ejecutar_auditoria_y_exportar,
)

_COLUMNAS_REPORTE = [
    "Fecha",
    "Suc",
    "Articulo",
    "Descripcion",
    "Talle",
    "Color",
    "EAN",
    "Comprobante",
    "Remito",
    "Cliente",
    "Cantidad",
    "PreUni",
    "Dto",
]


def _formatear_remito(valor) -> str:
    """Convierte el Remito a formato NNNN-NNNNNNNN (12 dígitos con guion)."""
    if pd.isna(valor):
        return ""
    valor_str = "".join(ch for ch in str(valor).strip() if ch.isdigit())
    if not valor_str:
        return ""
    valor_str = valor_str.zfill(12)
    return f"{valor_str[:4]}-{valor_str[4:]}"


def _parsear_preuni(valor) -> float:
    """
    Acepta número desde Excel o texto tipo ' $ 1.874,00 ' (miles con punto, decimal con coma).
    """
    if valor is None:
        raise ValueError("PreUni vacío")
    try:
        if pd.isna(valor):
            raise ValueError("PreUni vacío")
    except (TypeError, ValueError):
        pass
    if isinstance(valor, (int, float)) and not isinstance(valor, bool):
        return round(float(valor), 2)
    s = str(valor).strip().replace("$", "").replace(" ", "")
    if not s:
        raise ValueError("PreUni vacío")
    if "," in s and "." in s:
        s = s.replace(".", "").replace(",", ".")
    elif "," in s:
        s = s.replace(",", ".")
    return round(float(s), 2)


def _parsear_dto(valor) -> float:
    """'10%' -> 10. Si Excel manda 0.1 (celda con formato %), se convierte a 10."""
    if valor is None:
        return 0.0
    try:
        if pd.isna(valor):
            return 0.0
    except (TypeError, ValueError):
        pass

    texto = str(valor).strip()
    if not texto or texto.lower() == "nan":
        return 0.0

    tenia_signo_pct = "%" in texto
    numero = float(texto.replace("%", "").strip().replace(",", "."))

    if not tenia_signo_pct and 0 < numero < 1:
        numero *= 100

    return numero


def _ean_a_str(valor) -> str:
    if pd.isna(valor):
        return ""
    if isinstance(valor, float):
        return str(int(round(valor)))
    s = str(valor).strip()
    if re.fullmatch(r"\d+\.0", s):
        s = s[:-2]
    return s


def _almacen_desde_suc(valor) -> str:
    if pd.isna(valor):
        raise ValueError("Suc vacío")
    if isinstance(valor, (int, float)) and not isinstance(valor, bool):
        return str(int(round(float(valor)))).zfill(6)
    digits = "".join(c for c in str(valor).strip() if c.isdigit())
    if not digits:
        raise ValueError(f"Suc inválido: {valor!r}")
    return digits.zfill(6)[-6:] if len(digits) > 6 else digits.zfill(6)


def _fecha_a_cegid(valor) -> str | None:
    """
    Convierte Fecha a formato CEGID (ddmmyy).
    Acepta datetime de Excel, texto '18/05/2026' (día primero) y similares.
    Devuelve None si la celda está vacía o no es parseable (evita NaT + strftime).
    """
    if valor is None:
        return None
    try:
        if pd.isna(valor):
            return None
    except (TypeError, ValueError):
        pass
    if isinstance(valor, str) and not valor.strip():
        return None
    ts = pd.to_datetime(valor, dayfirst=True, errors="coerce")
    if pd.isna(ts):
        return None
    return ts.strftime("%d%m%y")


def _fila_tiene_pedido(row) -> bool:
    """True si la fila parece un ítem real (no padding vacío del Excel)."""
    return bool(_ean_a_str(row.get("EAN"))) or bool(_formatear_remito(row.get("Remito")))


def _cargar_excel_procer(input_path: str) -> pd.DataFrame:
    """
    Lee el xlsx y descarta filas totalmente vacías o sin EAN/Remito.
    Excel suele reportar decenas de miles de filas vacías en el rango usado.
    """
    data = pd.read_excel(input_path)
    data.columns = data.columns.str.strip()
    data = data.dropna(how="all")
    if data.empty:
        return data
    mask = data.apply(_fila_tiene_pedido, axis=1)
    filtrado = data.loc[mask].copy().reset_index(drop=True)
    omitidas = len(data) - len(filtrado)
    if omitidas:
        print(f"Procer: se omitieron {omitidas} fila(s) vacías o sin EAN/Remito.")
    return filtrado


def process_procer_pedido_proveedor(input_path, output_path):
    """
    Procesa un .xlsx de Procer.
    Columnas esperadas: Fecha, Suc, Articulo, Descripcion, Talle, Color, EAN,
    Comprobante, Remito, Cliente, Cantidad, PreUni, Dto.
    Genera el CSV para CEGID y retorna el informe de auditoría.
    """
    try:
        data = _cargar_excel_procer(input_path)
        if data.empty:
            return None

        conflictos_suc = detectar_conflictos_suc(data, _COLUMNAS_REPORTE)

        registros_cegid = []
        items_auditoria = []
        omitidas_sin_fecha = 0

        for i, row in data.iterrows():
            try:
                fecha_str = _fecha_a_cegid(row.get("Fecha"))
                referencia_formateada = _formatear_remito(row.get("Remito"))
                codigo_barras = _ean_a_str(row["EAN"])
                if not fecha_str:
                    omitidas_sin_fecha += 1
                    continue
                if not referencia_formateada or not codigo_barras:
                    continue
                cantidad = int(row["Cantidad"])
                precio_float = _parsear_preuni(row["PreUni"])
                establecimiento = resolver_establecimiento(row.get("Cliente", ""))
                almacen = _almacen_desde_suc(row["Suc"])
                dto_raw = row.get("Dto", row.get("DTO"))
                descuento = _parsear_dto(dto_raw)

                articulo_raw = str(row.get("Articulo", "")).strip()
                codigo_articulo = re.sub(r"[/\-]", "", articulo_raw)
                descripcion = str(row.get("Descripcion", "")).strip()
                talle = str(row.get("Talle", "")).strip()
                color = str(row.get("Color", "")).strip()
                comprobante = str(row.get("Comprobante", "")).strip()

                registros_cegid.append(
                    {
                        "CAB": "ZCOC1_",
                        "REFERENCIA INTERNA": referencia_formateada,
                        "FECHA": fecha_str,
                        "COD PROVEEDOR": "PROCE",
                        "CODIGO BARRAS": codigo_barras,
                        "CANTIDAD": cantidad,
                        "PRECIO": formatear_precio(precio_float),
                        "ALMACEN": almacen,
                        "ESTABLECIMIENTO": establecimiento,
                        "DESCUENTO": int(descuento) if descuento == int(descuento) else descuento,
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
                            "Precio": precio_float,
                        },
                    )
                )

            except Exception as e:
                print(f"Error en fila {i}: {e}")
                continue

        if omitidas_sin_fecha:
            print(
                f"Procer: {omitidas_sin_fecha} fila(s) con pedido pero sin fecha válida "
                f"(use formato dd/mm/aaaa, ej. 18/05/2026)."
            )

        if not registros_cegid:
            return None

        return ejecutar_auditoria_y_exportar(
            items_auditoria,
            registros_cegid,
            output_path,
            proveedor="PROCER",
            conflictos_suc=conflictos_suc,
            sort_by=None,
            usar_codigo_cegid_por_barras=True,
        )

    except Exception as e:
        raise RuntimeError(f"Error crítico en procesador Procer: {e}")
