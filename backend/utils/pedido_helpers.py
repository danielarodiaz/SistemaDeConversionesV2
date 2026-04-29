"""
pedido_helpers.py
-----------------
Funciones compartidas por los procesadores de Pedido Proveedor.
Centraliza lógica repetida: conflictos de Suc, formateo de precio,
establecimiento, armado de items de auditoría y exportación final.
"""
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
    normalizado = str(empresa_str).replace('.', '').strip().upper()
    return '002' if normalizado == 'MARATHON SRL' else '001'


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
