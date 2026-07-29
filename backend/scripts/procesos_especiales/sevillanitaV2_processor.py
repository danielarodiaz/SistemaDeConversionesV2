import os
import re
import zipfile
import traceback
from decimal import Decimal, InvalidOperation

import pandas as pd


ESTADOS_VALIDOS = {
    "recibido",
    "recibido con observaciones",
    "recibido con acuse",
    "recibido sin acuse",
}
DEFAULT_OCR = "240001"


def extraer_info_del_nombre_archivo(file_path):
    """
    Extrae el numero de factura y la fecha del nombre del archivo.
    Formato esperado: 0053-00010127 MAR 20260105 o 0053-00010127_MAR_20260105
    Retorna: (prefijo, folio, fecha_yyyymmdd, texto_intermedio)
    """
    nombre_archivo = os.path.basename(file_path)
    nombre_sin_ext = os.path.splitext(nombre_archivo)[0]

    match = re.search(r'(\d+)-(\d+)[\s_]+(\w+)[\s_]+(\d{8})', nombre_sin_ext)
    if match:
        prefijo = match.group(1)
        folio = match.group(2)
        texto_intermedio = match.group(3)
        fecha = match.group(4)
        return prefijo, folio, fecha, texto_intermedio
    raise ValueError(f"No se pudo extraer informacion del nombre del archivo: {nombre_archivo}")


def _detectar_archivos(input_paths):
    if isinstance(input_paths, (str, os.PathLike)):
        raise ValueError("Sevillanita V2 requiere dos archivos .xlsx: despachos y facturacion.")

    paths = [str(path) for path in input_paths]
    if len(paths) != 2:
        raise ValueError("Sevillanita V2 requiere exactamente dos archivos .xlsx.")

    despachos_path = None
    sevillanita_path = None
    for path in paths:
        nombre = os.path.basename(path).lower().strip()
        if nombre.startswith("despachos"):
            despachos_path = path
        else:
            sevillanita_path = path

    if not despachos_path or not sevillanita_path:
        raise ValueError("No se pudo identificar archivos. Uno debe comenzar con 'despachos'.")

    return despachos_path, sevillanita_path


def _limpiar_columnas(df):
    df.columns = [str(col).strip() for col in df.columns]
    return df[[col for col in df.columns if col and not col.startswith("Unnamed")]]


def _is_blank(value):
    if value is None or pd.isna(value):
        return True
    return str(value).strip().lower() in {"", "nan", "none", "null"}


def _leer_excel_con_header_detectado(file_path, columnas_requeridas):
    preview = pd.read_excel(file_path, header=None, dtype=str)
    required = {col.upper() for col in columnas_requeridas}

    for idx, row in preview.iterrows():
        values = {str(value).strip().upper() for value in row.tolist() if not pd.isna(value)}
        if required.issubset(values):
            return _limpiar_columnas(pd.read_excel(file_path, header=idx, dtype=str))

    return _limpiar_columnas(pd.read_excel(file_path, dtype=str))


def _digits(value):
    if _is_blank(value):
        return ""
    return re.sub(r"\D", "", str(value))


def _normalizar_remito(value):
    digits = _digits(value)
    if not digits:
        return "0"
    normalized = digits.lstrip("0")
    return normalized or "0"


def _normalizar_factura_desde_partes(prefijo, guia):
    pref = _digits(prefijo)
    nro = _digits(guia)
    if not pref or not nro:
        return ""
    return f"{pref.zfill(4)}-{nro.zfill(8)}"


def _normalizar_factura_app(value):
    text = "" if _is_blank(value) else str(value)
    parts = re.findall(r"\d+", text)
    if len(parts) >= 2:
        return _normalizar_factura_desde_partes(parts[0], parts[1])
    digits = _digits(text)
    if len(digits) > 8:
        return f"{digits[:-8].zfill(4)}-{digits[-8:].zfill(8)}"
    return ""


def _parse_decimal(value):
    if _is_blank(value):
        return None

    text = str(value).strip()
    if not text:
        return None

    text = text.replace("$", "").replace(" ", "").replace("\xa0", "")
    text = re.sub(r"[^0-9,.\-]", "", text)
    if not text:
        return None

    if "," in text and "." in text:
        text = text.replace(".", "").replace(",", ".")
    elif "," in text:
        text = text.replace(",", ".")

    try:
        return float(Decimal(text))
    except (InvalidOperation, ValueError):
        return None


def _format_importe(value):
    if value is None:
        return ""
    return round(float(value), 2)


def _son_importes_iguales(a, b):
    if a is None or b is None:
        return False
    return round(float(a), 2) == round(float(b), 2)


def _extraer_ocr_desde_texto(value):
    if _is_blank(value):
        return None
    match = re.match(r"^\s*(\d{6})", str(value).strip())
    return match.group(1) if match else None


def _obtener_ocr_code(row_despacho):
    if row_despacho is not None:
        destino = _extraer_ocr_desde_texto(row_despacho.get("Destino"))
        if destino:
            return f"{destino}-1", f"{destino}-2"

        sucursal_acuse = _extraer_ocr_desde_texto(row_despacho.get("Sucursal acuse"))
        if sucursal_acuse:
            return f"{sucursal_acuse}-1", f"{sucursal_acuse}-2"

    return f"{DEFAULT_OCR}-1", f"{DEFAULT_OCR}-2"


def _build_despachos_index(df_despachos):
    index = {}
    duplicados = set()

    for _, row in df_despachos.iterrows():
        remito_key = _normalizar_remito(row.get("Nro remito"))
        factura_key = _normalizar_factura_app(row.get("Nro factura"))
        key = (remito_key, factura_key)
        if key in index:
            duplicados.add(key)
        index.setdefault(key, row)

    return index, duplicados


def _cruzar_archivos(df_sevillanita, df_despachos, nro_factura, fecha_fac):
    despachos_index, duplicados = _build_despachos_index(df_despachos)
    filas_reporte = []
    filas_detalle_base = []
    resumen = {
        "sin_match": 0,
        "mas_1000kg": 0,
        "sin_valor_declarado": 0,
        "diferencias_importe": 0,
        "estado_anomalo": 0,
    }

    for idx, row in df_sevillanita.iterrows():
        try:
            if _is_blank(row.get("F PREF")) and _is_blank(row.get("NRO.GUIA")):
                continue

            remito_key = _normalizar_remito(row.get("REMITO"))
            factura_key = _normalizar_factura_desde_partes(row.get("F PREF"), row.get("NRO.GUIA"))
            despacho = despachos_index.get((remito_key, factura_key))

            flete = _parse_decimal(row.get("FLETE")) or 0.0
            seguro = _parse_decimal(row.get("SEGURO")) or 0.0
            kilos = _parse_decimal(row.get("KILOS")) or 0.0
            tarifa_app = _parse_decimal(despacho.get("Tarifa")) if despacho is not None else None
            seguro_app = _parse_decimal(despacho.get("Seguro")) if despacho is not None else None
            valor_declarado = _parse_decimal(despacho.get("Valor declarado")) if despacho is not None else None
            estado_app = str(despacho.get("Estado", "")).strip() if despacho is not None else "sin match"

            alertas = []
            if despacho is None:
                alertas.append("sin match")
                resumen["sin_match"] += 1

            if kilos > 1000:
                alertas.append("+1000kg")
                resumen["mas_1000kg"] += 1

            diferencia = ""
            if despacho is not None:
                if valor_declarado is None:
                    alertas.append("Filas sin valor declarado. No se pudo ver la diferencia")
                    resumen["sin_valor_declarado"] += 1
                else:
                    diferencia = round(flete - (tarifa_app or 0.0), 2)
                    if not _son_importes_iguales(flete, tarifa_app) or not _son_importes_iguales(seguro, seguro_app):
                        alertas.append("Diferencia de importes")
                        resumen["diferencias_importe"] += 1

                if estado_app and estado_app.lower() not in ESTADOS_VALIDOS:
                    alertas.append(f"Estado anomalo: {estado_app}")
                    resumen["estado_anomalo"] += 1

            estado_reporte = "sin match" if despacho is None else estado_app
            if kilos > 1000:
                estado_reporte = "sin match. +1000kg"

            reporte_row = {col: row.get(col, "") for col in [
                "F PREF", "NRO.GUIA", "REMITO", "FECHA", "BULTOS", "KILOS", "TC", "CC", "UN",
                "REMITENTE", "DESTINATARIO", "DESTINO", "FLETE", "SEGURO", "TOTAL",
            ]}
            reporte_row.update({
                "Valor declarado (app interna)": _format_importe(valor_declarado),
                "DIFERENCIA": diferencia,
                "ESTADO (app interna)": estado_reporte,
                "Nº de Factura": nro_factura,
                "Fecha de fac": fecha_fac,
                "ALERTA/MOTIVO": ", ".join(alertas),
            })
            filas_reporte.append(reporte_row)

            ocr_code, ocr_code2 = _obtener_ocr_code(despacho)
            filas_detalle_base.append({
                "ocr_code": ocr_code,
                "ocr_code2": ocr_code2,
                "flete": flete,
                "seguro": seguro,
            })

            if (remito_key, factura_key) in duplicados:
                reporte_row["ALERTA/MOTIVO"] = (reporte_row["ALERTA/MOTIVO"] + ", " if reporte_row["ALERTA/MOTIVO"] else "") + "Match duplicado en despachos"

        except Exception as e:
            print(f"Error procesando fila Sevillanita indice={idx}: {e}")
            traceback.print_exc()
            continue

    return filas_reporte, filas_detalle_base, resumen


def _crear_cabecera(prefijo, folio, fecha_emision):
    pti_code = prefijo.zfill(5)
    fol_num_from = folio.zfill(8)
    num_at_card = f"A{pti_code}{fol_num_from}"
    docnum = 1

    return [{
        "DocNum": docnum,
        "DocEntry": docnum,
        "DocType": "dDocument_Items",
        "DocDate": fecha_emision,
        "TaxDate": fecha_emision,
        "DocDueDate": "",
        "CardCode": "SEVIL",
        "NumAtCard": num_at_card,
        "DocCur": "ARS",
        "JournalMemo": "Fact.proveedores - SEVIL",
        "Comments": "",
        "PTICode": pti_code,
        "Letter": "A",
        "FolNumFrom": fol_num_from,
        "FolNumTo": fol_num_from,
        "Series": "14",
    }]


def _crear_detalle(filas_detalle_base):
    ocr_groups = {}

    for fila in filas_detalle_base:
        ocr_code = fila["ocr_code"]
        if ocr_code not in ocr_groups:
            ocr_groups[ocr_code] = {
                "ocr_code": ocr_code,
                "ocr_code2": fila["ocr_code2"],
                "flete_total": 0.0,
                "seguro_total": 0.0,
            }
        ocr_groups[ocr_code]["flete_total"] += fila["flete"]
        ocr_groups[ocr_code]["seguro_total"] += fila["seguro"]

    detalle = []
    line_num = 0
    docnum = 1
    for _, ocr_data in ocr_groups.items():
        detalle.append({
            "DocNum": docnum,
            "LineNum": line_num,
            "ItemCode": "100",
            "Dscription": "FLETES DE TERCEROS",
            "Quantity": 1,
            "Price": round(ocr_data["flete_total"], 2),
            "TaxCode": "IVA_21",
            "TaxOnly": "N",
            "WhsCode": "01",
            "AcctCode": "5.2.020.05.001",
            "OcrCode": ocr_data["ocr_code"],
            "OcrCode2": ocr_data["ocr_code2"],
        })
        line_num += 1

        detalle.append({
            "DocNum": docnum,
            "LineNum": line_num,
            "ItemCode": "101",
            "Dscription": "FLETES - SEGURO",
            "Quantity": 1,
            "Price": round(ocr_data["seguro_total"], 2),
            "TaxCode": "IVA_21",
            "TaxOnly": "N",
            "WhsCode": "01",
            "AcctCode": "5.2.020.05.001",
            "OcrCode": ocr_data["ocr_code"],
            "OcrCode2": ocr_data["ocr_code2"],
        })
        line_num += 1

    return detalle


def _save_csv(file_path, data_list, header1, header2):
    """Guarda un archivo CSV con dos lineas de encabezado."""
    if data_list:
        df = pd.DataFrame(data_list)
        with open(file_path, "w", encoding="utf-8", newline="") as f:
            f.write(";".join(header1) + "\n")
            f.write(";".join(header2) + "\n")
            df.to_csv(f, index=False, sep=";", header=False)
        os.chmod(file_path, 0o777)
        print(f"Archivo generado: {file_path}")


def _guardar_reporte_excel(file_path, filas_reporte):
    df_reporte = pd.DataFrame(filas_reporte)
    df_reporte.to_excel(file_path, index=False)
    os.chmod(file_path, 0o777)
    print(f"Reporte generado: {file_path}")


def process_sevillanitaV2_procesos_especiales(input_path, output_path):
    """
    Procesa dos .xlsx de Sevillanita: despachos de logistica y facturacion del proveedor.
    Genera CABECERA/DETALLE SAP y un reporte de diferencias para auditoria manual.
    """
    try:
        despachos_path, sevillanita_path = _detectar_archivos(input_path)

        data_sevillanita = _leer_excel_con_header_detectado(
            sevillanita_path,
            ["F PREF", "NRO.GUIA", "REMITO", "FLETE", "SEGURO"],
        )
        data_despachos = _leer_excel_con_header_detectado(
            despachos_path,
            ["Nro remito", "Nro factura", "Tarifa", "Valor declarado", "Seguro"],
        )

        prefijo, folio, fecha_emision, texto_intermedio = extraer_info_del_nombre_archivo(sevillanita_path)
        nro_factura = f"{prefijo.zfill(4)}-{folio.zfill(8)}"
        fecha_fac = fecha_emision

        filas_reporte, filas_detalle_base, resumen = _cruzar_archivos(
            data_sevillanita,
            data_despachos,
            nro_factura,
            fecha_fac,
        )

        cabecera = _crear_cabecera(prefijo, folio, fecha_emision)
        detalle = _crear_detalle(filas_detalle_base)

        header_line_1_cab = ["DocNum", "DocEntry", "DocType", "DocDate", "TaxDate", "DocDueDate",
                             "CardCode", "NumAtCard", "DocCurrency", "JournalMemo", "Comments",
                             "PointOfIssueCode", "Letter", "FolioNumberFrom", "FolioNumberTo", "Series"]
        header_line_2_cab = ["DocNum", "DocEntry", "DocType", "DocDate", "TaxDate", "DocDueDate",
                             "CardCode", "NumAtCard", "DocCur", "JournalMemo", "Comments",
                             "PTICode", "Letter", "FolNumFrom", "FolNumTo", "Series"]

        header_line_1_det = ["ParentKey", "LineNum", "ItemCode", "ItemDescription", "Quantity", "Price",
                             "TaxCode", "TaxOnly", "WarehouseCode", "AccountCode", "CostingCode", "CostingCode2"]
        header_line_2_det = ["DocNum", "LineNum", "ItemCode", "Dscription", "Quantity", "Price",
                             "TaxCode", "TaxOnly", "WhsCode", "AcctCode", "OcrCode", "OcrCode2"]

        base_name = os.path.splitext(output_path)[0]
        cab_path = f"{base_name}_{texto_intermedio}_CABECERA.csv"
        det_path = f"{base_name}_{texto_intermedio}_DETALLE.csv"
        reporte_path = f"{base_name}_{texto_intermedio}_REPORTE_DIFERENCIAS.xlsx"

        print(f"Registros: cabecera={len(cabecera)}, detalle={len(detalle)}, reporte={len(filas_reporte)}")

        _save_csv(cab_path, cabecera, header_line_1_cab, header_line_2_cab)
        _save_csv(det_path, detalle, header_line_1_det, header_line_2_det)
        _guardar_reporte_excel(reporte_path, filas_reporte)

        zip_path = output_path if output_path.lower().endswith(".zip") else output_path.replace(".csv", ".zip")
        with zipfile.ZipFile(zip_path, 'w') as zipf:
            for path in [cab_path, det_path, reporte_path]:
                if os.path.exists(path):
                    zipf.write(path, os.path.basename(path))

        alertas_preview = [fila for fila in filas_reporte if fila.get("ALERTA/MOTIVO")]
        return {
            "output_path": zip_path,
            "sevillanita": {
                "resumen": resumen,
                "filas_total": len(filas_reporte),
                "alertas_total": len(alertas_preview),
                "filas": filas_reporte,
                "alertas": alertas_preview,
            },
        }

    except Exception as e:
        print("Error general procesando archivo.")
        traceback.print_exc()
        raise RuntimeError(f"Error al procesar el archivo: {e}")
