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
from backend.services.validator import CegidValidator


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
        filas['Fecha'] = pd.to_datetime(
            filas['Fecha'], dayfirst=True
        ).dt.strftime('%d/%m/%Y')

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


def ejecutar_auditoria_y_exportar(
    items_auditoria: list,
    registros_cegid: list,
    output_path: str,
    proveedor: str,
    conflictos_suc: list = None,
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
    informe['conflictos_suc'] = conflictos_suc or []

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
