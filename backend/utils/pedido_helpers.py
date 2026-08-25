"""
pedido_helpers.py
-----------------
Funciones compartidas por los procesadores de Pedido Proveedor.
Centraliza lógica repetida: conflictos de Suc, formateo de precio,
establecimiento, armado de items de auditoría, exportación final
y empaquetado en ZIP cuando hay variaciones de precio.
"""
import os
import zipfile
import pandas as pd
from backend.database import SessionLocal, engine
from backend.models import AuditoriaPromo
from backend.services.validator import CegidValidator
from backend.utils.cegid_utils import (
    obtener_articulos_por_codigos_barras,
    obtener_promos_por_codigos_articulo,
)


def _normalizar_valor_reporte(valor):
    if _valor_vacio(valor):
        return ""
    if isinstance(valor, pd.Timestamp):
        return valor.strftime("%d/%m/%Y") if not pd.isna(valor) else ""
    return valor.item() if hasattr(valor, "item") else valor


def _normalizar_dataframe_reporte(df: pd.DataFrame) -> pd.DataFrame:
    if hasattr(df, "map"):
        return df.map(_normalizar_valor_reporte)
    return df.applymap(_normalizar_valor_reporte)


def _valor_vacio(valor) -> bool:
    if valor is None:
        return True
    try:
        if pd.isna(valor):
            return True
    except (TypeError, ValueError):
        pass
    return str(valor).strip().lower() in {"", "nan", "none", "null"}


def _buscar_columna(columns, posibles: list[str]) -> str | None:
    normalizadas = {str(col).strip().lower(): col for col in columns}
    for nombre in posibles:
        col = normalizadas.get(str(nombre).strip().lower())
        if col is not None:
            return col
    return None


def detectar_ean_vacios(
    df: pd.DataFrame,
    columnas_reporte: list | None = None,
    columnas_ean: list[str] | None = None,
) -> list:
    """
    Detecta filas con columna EAN/codigo de barras presente pero sin valor.
    Si no existe una columna EAN equivalente, no genera alerta.
    """
    if df is None or df.empty:
        return []

    columnas_ean = columnas_ean or [
        "EAN",
        "EAN/GTIN",
        "Codigo de EAN",
        "Código de EAN",
        "Codigo EAN",
        "Código EAN",
        "UPC",
        "Codigo Barras",
        "Código de Barras",
        "Código Barras",
    ]
    col_ean = _buscar_columna(df.columns, columnas_ean)
    if col_ean is None:
        return []

    mask = df[col_ean].apply(_valor_vacio)
    columnas_contexto = [col for col in df.columns if col != col_ean]
    if columnas_contexto:
        filas_con_datos = df[columnas_contexto].apply(
            lambda row: any(not _valor_vacio(valor) for valor in row),
            axis=1,
        )
        mask = mask & filas_con_datos

    if not mask.any():
        return []

    columnas_base = columnas_reporte or list(df.columns)
    cols = [c for c in columnas_base if c in df.columns]
    if col_ean not in cols:
        cols.append(col_ean)

    filas = df.loc[mask, cols].copy()
    filas.insert(0, "Fila", [int(idx) + 2 if isinstance(idx, int) else str(idx) for idx in filas.index])
    if col_ean != "EAN":
        filas["Columna EAN"] = col_ean

    if "Fecha" in filas.columns:
        fechas = pd.to_datetime(filas["Fecha"], dayfirst=True, errors="coerce")
        if fechas.notna().any():
            filas["Fecha"] = filas["Fecha"].astype(object)
            filas.loc[fechas.notna(), "Fecha"] = fechas[fechas.notna()].dt.strftime("%d/%m/%Y")

    filas = _normalizar_dataframe_reporte(filas)
    return filas.to_dict(orient="records")


def detectar_campos_requeridos_vacios(
    df: pd.DataFrame,
    columnas_requeridas: list[str],
    columnas_reporte: list | None = None,
) -> list:
    """Detecta campos requeridos vacios sin bloquear el procesamiento."""
    if df is None or df.empty:
        return []

    columnas_existentes = [col for col in columnas_requeridas if col in df.columns]
    if not columnas_existentes:
        return []

    alertas = []
    columnas_base = columnas_reporte or list(df.columns)
    cols = [c for c in columnas_base if c in df.columns]

    for idx, row in df.iterrows():
        campos_vacios = [col for col in columnas_existentes if _valor_vacio(row.get(col))]
        if not campos_vacios:
            continue
        if not any(not _valor_vacio(row.get(col)) for col in df.columns if col not in campos_vacios):
            continue

        detalle = {col: row.get(col) for col in cols}
        detalle["Fila"] = int(idx) + 2 if isinstance(idx, int) else str(idx)
        detalle["Campos vacios"] = ", ".join(campos_vacios)
        alertas.append(detalle)

    if not alertas:
        return []

    filas = pd.DataFrame(alertas)
    if "Fecha" in filas.columns:
        fechas = pd.to_datetime(filas["Fecha"], dayfirst=True, errors="coerce")
        if fechas.notna().any():
            filas["Fecha"] = filas["Fecha"].astype(object)
            filas.loc[fechas.notna(), "Fecha"] = fechas[fechas.notna()].dt.strftime("%d/%m/%Y")

    filas = _normalizar_dataframe_reporte(filas)
    return filas.to_dict(orient="records")


def detectar_conflictos_suc(df: pd.DataFrame, columnas_reporte: list) -> list:
    """
    Detecta remitos que aparecen con más de un valor de Suc en el DataFrame.
    Retorna una lista de dicts con las filas conflictivas (solo columnas disponibles).
    """
    if 'Remito' not in df.columns or 'Suc' not in df.columns:
        return []

    grupos = df.groupby('Remito')['Suc'].nunique()
    remitos_conflictivos = grupos[grupos > 1].index.tolist()

    if not remitos_conflictivos:
        return []

    filas = df[df['Remito'].isin(remitos_conflictivos)].copy()
    cols = [c for c in columnas_reporte if c in filas.columns]
    filas = filas[cols]

    if 'Fecha' in filas.columns:
        fechas = pd.to_datetime(filas['Fecha'], dayfirst=True, errors="coerce")
        filas['Fecha'] = ""
        if fechas.notna().any():
            filas.loc[fechas.notna(), 'Fecha'] = fechas[fechas.notna()].dt.strftime('%d/%m/%Y')

    filas = _normalizar_dataframe_reporte(filas)

    print(f"⚠️ Se encontraron {len(remitos_conflictivos)} remito(s) con Suc inconsistente.")
    return filas.to_dict(orient='records')


def formatear_precio(valor) -> str:
    """
    Convierte un número a string con coma decimal (formato CEGID).
    Ej: 12.5 → '12,50'
    """
    return f"{round(float(valor), 2):.2f}".replace('.', ',')


def resolver_establecimiento(empresa_str) -> str:
    """
    Retorna '002' si la empresa es Marathon SRL, '001' en cualquier otro caso.
    Acepta variantes como 'MARATHON S.R.L.' o 'Marathon SRL'.
    """
    variantes = {
        '002': ['MARATHON SRL', 'MARATHON', 'MARATHON S.A.', 'MARATHON SA', 'MARATHON S.A', 'MARATHON DEPORTES'],
    }
    normalizado = str(empresa_str).replace('.', '').strip().upper()
    for establecimiento, variantes in variantes.items():
        if normalizado in variantes:
            return establecimiento
    return '001'


def resolver_descuento(valor, default: float = 0) -> float:
    """
    Convierte el valor de la columna de descuento a float.
    Si el valor es NaN, None, vacío o no numérico, retorna `default` (por defecto 0).
    Garantiza que el CSV de importación siempre tenga un número válido en DESCUENTO.
    """
    import pandas as pd
    if valor is None:
        return default
    try:
        if pd.isna(valor):
            return default
    except (TypeError, ValueError):
        pass
    try:
        resultado = float(valor)
        return resultado if resultado == resultado else default  # NaN float check
    except (TypeError, ValueError):
        return default


def armar_item_auditoria(barras: str, articulo: str, precio_float: float, detalles: dict) -> dict:
    """Construye el dict estándar que espera CegidValidator.auditar_items()."""
    return {
        'barras': barras,
        'articulo': articulo,
        'precio_prov': precio_float,
        'detalles': detalles,
    }


def auditar_promos_articulos(
    codigos_articulo: list | None = None,
    codigos_barras: list | None = None,
    proveedor: str | None = None,
    origen: str | None = None,
) -> list:
    """
    Detecta articulos con GA_LIBREART6 distinto de N/A y los registra una sola vez.
    """
    codigos = resolver_codigos_articulo_para_auditoria_promos(
        codigos_articulo=codigos_articulo,
        codigos_barras=codigos_barras,
    )

    promos = obtener_promos_por_codigos_articulo(codigos)
    if not promos:
        return []

    alertas = []
    for item in sorted(promos.values(), key=lambda value: value["codigo_articulo"]):
        alerta = {
            "Articulo": item["codigo_articulo"],
            "Descripcion": item.get("descripcion", ""),
            "Promo": item.get("promo", ""),
        }
        if proveedor:
            alerta["Proveedor"] = proveedor
        if origen:
            alerta["Origen"] = origen
        alertas.append(alerta)

    _registrar_auditoria_promos(alertas, proveedor=proveedor, origen=origen)
    return alertas


def resolver_codigos_articulo_para_auditoria_promos(
    codigos_articulo: list | None = None,
    codigos_barras: list | None = None,
) -> list:
    """
    Devuelve codigos de articulo unicos para auditar promo.
    Si hay codigos de barra, prioriza el articulo real resuelto en CEGID.
    """
    barras = []
    for codigo in codigos_barras or []:
        codigo_limpio = str(codigo or "").strip()
        if not codigo_limpio or codigo_limpio.upper().startswith("FALTA"):
            continue
        barras.append(codigo_limpio)

    if barras:
        codigos_resueltos = {
            str(codigo).strip()
            for codigo in obtener_articulos_por_codigos_barras(barras).values()
            if codigo is not None and str(codigo).strip()
        }
        if codigos_resueltos:
            return sorted(codigos_resueltos)

    codigos_template = {
        str(codigo).strip()
        for codigo in (codigos_articulo or [])
        if codigo is not None and str(codigo).strip()
    }
    return sorted(codigos_template)


def _registrar_auditoria_promos(alertas: list, proveedor: str | None, origen: str | None) -> None:
    if not alertas:
        return

    try:
        AuditoriaPromo.__table__.create(bind=engine, checkfirst=True)
        db = SessionLocal()
        try:
            for alerta in alertas:
                codigo_articulo = str(alerta.get("Articulo", "")).strip()
                promo = str(alerta.get("Promo", "")).strip()
                if not codigo_articulo or not promo:
                    continue

                existente = (
                    db.query(AuditoriaPromo)
                    .filter(AuditoriaPromo.codigo_articulo == codigo_articulo)
                    .one_or_none()
                )
                if existente:
                    existente.descripcion = str(alerta.get("Descripcion", "")).strip()
                    existente.promo = promo
                    existente.proveedor = proveedor
                    existente.origen = origen
                else:
                    db.add(AuditoriaPromo(
                        codigo_articulo=codigo_articulo,
                        descripcion=str(alerta.get("Descripcion", "")).strip(),
                        promo=promo,
                        proveedor=proveedor,
                        origen=origen,
                    ))
            db.commit()
        finally:
            db.close()
    except Exception as e:
        print(f"Error registrando auditoria de promos: {e}")


def ejecutar_auditoria_y_exportar(
    items_auditoria: list,
    registros_cegid: list,
    output_path: str,
    proveedor: str,
    conflictos_suc: list = None,
    ean_vacios: list = None,
    campos_requeridos_vacios: list = None,
    codigos_barras_no_encontrados: list = None,
    codigos_barras_completados: list = None,
    sort_by: str = 'REFERENCIA INTERNA',
    encoding: str = 'utf-8-sig',
) -> dict:
    """
    1. Ejecuta la auditoría completa con CegidValidator.
    2. Adjunta conflictos_suc al informe.
    3. Exporta el CSV de CEGID con separador '|'.
    Retorna el informe de auditoría.
    """
    print(f"📦 Items {proveedor} listos para auditar: {len(items_auditoria)}")
    informe = CegidValidator.auditar_items(items_auditoria)
    codigos_promos_chequeados = resolver_codigos_articulo_para_auditoria_promos(
        codigos_articulo=[item.get('articulo') for item in items_auditoria],
        codigos_barras=[item.get('barras') for item in items_auditoria],
    )
    informe['articulos_promos_chequeados'] = [
        {"Articulo": codigo}
        for codigo in codigos_promos_chequeados
    ]
    informe['alertas_promos'] = auditar_promos_articulos(
        codigos_articulo=codigos_promos_chequeados,
        proveedor=proveedor,
        origen='PEDIDO_PROVEEDOR',
    )
    if codigos_promos_chequeados and not informe['alertas_promos']:
        informe.setdefault('avisos_generales', []).append(
            "Todos los articulos chequeados tienen promo N/A."
        )
    informe['conflictos_suc'] = conflictos_suc or []
    informe['ean_vacios'] = ean_vacios or []
    informe['campos_requeridos_vacios'] = campos_requeridos_vacios or []
    informe['codigos_barras_no_encontrados'] = codigos_barras_no_encontrados or []
    informe['codigos_barras_completados'] = codigos_barras_completados or []

    df_out = pd.DataFrame(registros_cegid)
    if sort_by and sort_by in df_out.columns:
        df_out.sort_values(by=sort_by, inplace=True)
    df_out.to_csv(output_path, index=False, sep='|', encoding=encoding)

    return informe


def generar_zip_con_variaciones(
    csv_importacion_path: str,
    cambios_precio: list,
    proveedor: str,
    output_folder: str,
    ts: str,
) -> str:
    """
    Cuando hay variaciones de precio, genera un ZIP con 3 archivos:

    1. <PROVEEDOR>_<ts>_IMPORTACION.csv  → el CSV original de CEGID (ya generado)
    2. <PROVEEDOR>_<ts>_PC.csv           → CSV de actualización de Precio de Compra para CEGID
    3. <PROVEEDOR>_<ts>_PRECIOS_DIFS.csv → Informe de precios diferentes

    Retorna la ruta absoluta al ZIP generado.

    Estructura de cada item en `cambios_precio` (viene de CegidValidator):
        {
            "articulo_cegid":      str,
            "descripcion":         str,
            "precio_cegid":        float,
            "precio_prov":         float,
            "variacion_porcentaje": float,
        }
    """
    base = f"{proveedor}_{ts}"

    # ── 1. Archivo de importación (ya existe en csv_importacion_path) ─────────
    import_filename = f"{base}_IMPORTACION.csv"
    import_path = os.path.join(output_folder, import_filename)
    # Renombrar el CSV original para que quede con el nombre correcto dentro del ZIP
    os.rename(csv_importacion_path, import_path)

    # ── 2. Archivo PC (Precio de Compra) ─────────────────────────────────────
    # Formato que espera CEGID para actualización masiva de precios de compra.
    pc_filename = f"{base}_PC.csv"
    pc_path = os.path.join(output_folder, pc_filename)
    pc_rows = []
    for item in cambios_precio:
        pc_rows.append({
            'Cabecera': "LCOC1_",
            'PERIODO': "PERMA",
            'tipo': "LCMAR",
            'Precio': formatear_precio(item['precio_prov']),
            'COD ARTICULO': item['articulo_cegid']
        })
    pd.DataFrame(pc_rows).to_csv(pc_path, index=False, sep='|', encoding='utf-8-sig')

    # ── 3. Informe de precios diferentes ─────────────────────────────────────
    difs_filename = f"{base}_PRECIOS_DIFERENTES.csv"
    difs_path = os.path.join(output_folder, difs_filename)
    difs_rows = []
    for item in cambios_precio:
        difs_rows.append({
            'Artículo':             item['articulo_cegid'],
            'Descripción':          item['descripcion'],
            'Precio CEGID':         item['precio_cegid'],
            'Precio Proveedor':     item['precio_prov'],
            'Variación (%)':        item['variacion_porcentaje'],
        })
    pd.DataFrame(difs_rows).to_csv(difs_path, index=False, sep=';', encoding='utf-8-sig')

    # ── 4. Empacar en ZIP ────────────────────────────────────────────────────
    zip_filename = f"{base}.zip"
    zip_path = os.path.join(output_folder, zip_filename)
    with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zf:
        zf.write(import_path, import_filename)
        zf.write(pc_path,     pc_filename)
        zf.write(difs_path,   difs_filename)

    # Limpiar archivos intermedios (quedan dentro del ZIP)
    for p in (import_path, pc_path, difs_path):
        if os.path.exists(p):
            os.remove(p)

    print(f"📦 ZIP generado con 3 archivos: {zip_path}")
    return zip_path
