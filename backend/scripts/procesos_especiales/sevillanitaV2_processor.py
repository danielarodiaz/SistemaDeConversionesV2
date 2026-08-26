import os
import re
import zipfile
import traceback
import unicodedata
from decimal import Decimal, InvalidOperation

import pandas as pd


ESTADOS_VALIDOS = {
    "recibido",
    "recibido con observaciones",
    "recibido con acuse",
    "recibido sin acuse",
}
DEFAULT_OCR = "240001"
SEVILLANITA_REQUIRED_COLUMNS = ["NRO.GUIA", "REMITO", "FLETE", "SEGURO"]
COLUMN_ALIASES = {
    "FPREF": "F PREF",
    "PREF": "F PREF",
    "PREFIJO": "F PREF",
    "NROGUIA": "NRO.GUIA",
    "NRODEGUIA": "NRO.GUIA",
    "NUMEROGUIA": "NRO.GUIA",
    "GUIA": "NRO.GUIA",
    "REMITO": "REMITO",
    "REMIT0": "REMITO",
    "NROREMITO": "REMITO",
    "NRODEREMITO": "REMITO",
    "FECHA": "FECHA",
    "BULTOS": "BULTOS",
    "KILOS": "KILOS",
    "KG": "KILOS",
    "TC": "TC",
    "CC": "CC",
    "UN": "UN",
    "REMITENTE": "REMITENTE",
    "DESTINATARIO": "DESTINATARIO",
    "DESTINO": "DESTINO",
    "FLETE": "FLETE",
    "SEGURO": "SEGURO",
    "TOTAL": "TOTAL",
}


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


def _column_key(value):
    text = "" if value is None else str(value).strip()
    text = unicodedata.normalize("NFKD", text)
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    return re.sub(r"[^A-Z0-9]", "", text.upper())


def _canonical_column_name(value):
    text = "" if value is None else str(value).strip()
    return COLUMN_ALIASES.get(_column_key(text), text)


def _limpiar_columnas(df):
    df.columns = [_canonical_column_name(col) for col in df.columns]
    columnas_validas = [col for col in df.columns if col and not str(col).startswith("Unnamed")]
    return df[columnas_validas]


def _is_blank(value):
    if value is None or pd.isna(value):
        return True
    return str(value).strip().lower() in {"", "nan", "none", "null"}


def _row_get(row, *names, default=None):
    for name in names:
        value = row.get(name)
        if not _is_blank(value):
            return value
    return default


def _leer_excel_con_header_detectado(file_path, columnas_requeridas):
    preview = pd.read_excel(file_path, header=None, dtype=str)
    required = {_canonical_column_name(col).upper() for col in columnas_requeridas}

    for idx, row in preview.iterrows():
        values = {
            _canonical_column_name(value).upper()
            for value in row.tolist()
            if not pd.isna(value)
        }
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


def _extraer_partes_guia(row):
    prefijo = row.get("F PREF")
    guia = row.get("NRO.GUIA")

    if not _is_blank(prefijo):
        return _digits(prefijo), _digits(guia)

    parts = re.findall(r"\d+", "" if _is_blank(guia) else str(guia))
    if len(parts) >= 2:
        return parts[0], parts[1]
    return "", _digits(guia)


def _normalizar_factura_sevillanita(row):
    prefijo, guia = _extraer_partes_guia(row)
    if prefijo and guia:
        return _normalizar_factura_desde_partes(prefijo, guia)
    return _normalizar_factura_app(row.get("NRO.GUIA"))


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


def _format_decimal_reporte(value):
    if value is None or value == "":
        return ""
    return f"{round(float(value), 2):.2f}".replace(".", ",")


def _format_fecha_reporte(value):
    if _is_blank(value):
        return ""
    text = str(value).strip()

    iso_match = re.match(r"^(\d{4})-(\d{2})-(\d{2})(?:\s+.*)?$", text)
    if iso_match:
        year, month, day = iso_match.groups()
        return f"{day}-{month}-{year}"

    parsed = pd.to_datetime(value, dayfirst=True, errors="coerce")
    if pd.isna(parsed):
        return text
    return parsed.strftime("%d-%m-%Y")


def _format_fecha_yyyymmdd_reporte(value):
    if _is_blank(value):
        return ""
    text = str(value).strip()
    parsed = pd.to_datetime(text, format="%Y%m%d", errors="coerce")
    if pd.isna(parsed):
        parsed = pd.to_datetime(text, dayfirst=True, errors="coerce")
    if pd.isna(parsed):
        return text
    return parsed.strftime("%d-%m-%Y")


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
        destino = _extraer_ocr_desde_texto(_row_get(row_despacho, "Destino", "DESTINO"))
        if destino:
            return f"{destino}-1", f"{destino}-2"

        sucursal_acuse = _extraer_ocr_desde_texto(_row_get(row_despacho, "Sucursal acuse"))
        if sucursal_acuse:
            return f"{sucursal_acuse}-1", f"{sucursal_acuse}-2"

    return f"{DEFAULT_OCR}-1", f"{DEFAULT_OCR}-2"


def _build_despachos_index(df_despachos):
    index = {}
    duplicados = set()

    for _, row in df_despachos.iterrows():
        remito_key = _normalizar_remito(_row_get(row, "Nro remito", "REMITO"))
        factura_key = _normalizar_factura_app(_row_get(row, "Nro factura", "NRO.GUIA"))
        key = (remito_key, factura_key)
        if key in index:
            duplicados.add(key)
        index.setdefault(key, row)

    return index, duplicados


def _normalizar_guia(value):
    return _normalizar_factura_app(value)


def _cargar_subtotales_novedades():
    try:
        from backend.scripts.procesos_especiales.sync_novedades.config import load_config, validate_config
        from backend.scripts.procesos_especiales.sync_novedades.extractor_novedades import read_novedades_rows
    except Exception as exc:
        print(f"No se pudo importar lector NOVEDADES para SUBTOTAL: {exc}")
        return {}, {}

    try:
        config = load_config()
        validate_config(config, need_app=False, need_sheets=True, need_email=False)
        _, rows, _ = read_novedades_rows(config)
    except Exception as exc:
        print(f"No se pudo leer SUBTOTAL desde NOVEDADES: {exc}")
        traceback.print_exc()
        return {}, {}

    by_remito_guia = {}
    by_remito = {}
    for row in rows:
        remito = _normalizar_remito(row.values.get("REMITO"))
        guia = _normalizar_guia(row.values.get("GUIA"))
        subtotal = _parse_decimal(row.values.get("SUBTOTAL"))
        if subtotal is None:
            continue
        if remito and guia:
            by_remito_guia[(remito, guia)] = subtotal
        if remito:
            by_remito.setdefault(remito, []).append(subtotal)

    return by_remito_guia, by_remito


def _resolver_subtotal_novedades(remito_key, factura_key, subtotales_novedades):
    by_remito_guia, by_remito = subtotales_novedades
    if (remito_key, factura_key) in by_remito_guia:
        return by_remito_guia[(remito_key, factura_key)]

    candidatos = by_remito.get(remito_key, [])
    if len(candidatos) == 1:
        return candidatos[0]
    return None


def _cruzar_archivos(df_sevillanita, df_despachos, nro_factura, fecha_fac, subtotales_novedades):
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
            prefijo_guia, nro_guia = _extraer_partes_guia(row)
            factura_key = _normalizar_factura_sevillanita(row)
            despacho = despachos_index.get((remito_key, factura_key))
            subtotal_novedades = _resolver_subtotal_novedades(remito_key, factura_key, subtotales_novedades)

            flete = _parse_decimal(row.get("FLETE")) or 0.0
            seguro = _parse_decimal(row.get("SEGURO")) or 0.0
            total = _parse_decimal(row.get("TOTAL")) or 0.0
            kilos = _parse_decimal(row.get("KILOS")) or 0.0
            tarifa_app = _parse_decimal(_row_get(despacho, "Tarifa")) if despacho is not None else None
            seguro_app = _parse_decimal(_row_get(despacho, "Seguro", "SEGURO")) if despacho is not None else None
            valor_declarado = _parse_decimal(_row_get(despacho, "Valor declarado")) if despacho is not None else None
            estado_app = str(_row_get(despacho, "Estado", default="")).strip() if despacho is not None else "sin match"

            alertas = []
            if despacho is None:
                alertas.append("sin match")
                resumen["sin_match"] += 1

            if kilos > 1000:
                alertas.append("+1000kg")
                resumen["mas_1000kg"] += 1

            diferencia_tarifa = ""
            diferencia_seguro = ""
            if despacho is not None:
                if tarifa_app is not None:
                    diferencia_tarifa = round(flete - tarifa_app, 2)
                if seguro_app is not None:
                    diferencia_seguro = round(seguro - seguro_app, 2)

                if valor_declarado is None:
                    alertas.append("Filas sin valor declarado. No se pudo ver la diferencia")
                    resumen["sin_valor_declarado"] += 1
                else:
                    if not _son_importes_iguales(flete, tarifa_app) or not _son_importes_iguales(seguro, seguro_app):
                        alertas.append("Diferencia de importes")
                        resumen["diferencias_importe"] += 1

                if estado_app and estado_app.lower() not in ESTADOS_VALIDOS:
                    alertas.append(f"Estado anomalo: {estado_app}")
                    resumen["estado_anomalo"] += 1

            estado_reporte = "sin match" if despacho is None else estado_app
            if kilos > 1000 and valor_declarado is None:
                estado_reporte = "sin match. +1000kg"

            diferencia2 = ""
            if valor_declarado is not None and subtotal_novedades is not None:
                diferencia2 = round((valor_declarado * 0.005) - (subtotal_novedades * 0.005), 2)

            reporte_row = {
                "F PREF": prefijo_guia or row.get("F PREF", ""),
                "NRO.GUIA": nro_guia or row.get("NRO.GUIA", ""),
                "REMITO": row.get("REMITO", ""),
                "FECHA": _format_fecha_reporte(row.get("FECHA")),
                "BULTOS": row.get("BULTOS", ""),
                "KILOS": row.get("KILOS", ""),
                "TC": row.get("TC", ""),
                "CC": row.get("CC", ""),
                "UN": row.get("UN", ""),
                "REMITENTE": row.get("REMITENTE", ""),
                "DESTINATARIO": row.get("DESTINATARIO", ""),
                "DESTINO": row.get("DESTINO", ""),
                "FLETE": _format_decimal_reporte(flete),
                "SEGURO": _format_decimal_reporte(seguro),
                "TOTAL": _format_decimal_reporte(total),
            }
            reporte_row.update({
                "Valor declarado (app interna)": _format_importe(valor_declarado),
                "DIFERENCIA TARIFA": diferencia_tarifa,
                "DIFERENCIA SEGURO": diferencia_seguro,
                "ESTADO (app interna)": estado_reporte,
                "Nº de Factura": nro_factura,
                "Fecha de fac": _format_fecha_yyyymmdd_reporte(fecha_fac),
                "ALERTA/MOTIVO": ", ".join(alertas),
                "SUBTOTAL": _format_decimal_reporte(subtotal_novedades),
                "DIFERENCIA (VD - SUBTOTAL Novedades)": _format_decimal_reporte(diferencia2),
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
            SEVILLANITA_REQUIRED_COLUMNS,
        )
        data_despachos = _leer_excel_con_header_detectado(
            despachos_path,
            ["Nro remito", "Nro factura", "Tarifa", "Valor declarado", "Seguro"],
        )

        prefijo, folio, fecha_emision, texto_intermedio = extraer_info_del_nombre_archivo(sevillanita_path)
        nro_factura = f"{prefijo.zfill(4)}-{folio.zfill(8)}"
        fecha_fac = fecha_emision
        subtotales_novedades = _cargar_subtotales_novedades()

        filas_reporte, filas_detalle_base, resumen = _cruzar_archivos(
            data_sevillanita,
            data_despachos,
            nro_factura,
            fecha_fac,
            subtotales_novedades,
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
