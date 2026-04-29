import pandas as pd
import re
from backend.utils.pedido_helpers import (
    detectar_conflictos_suc, formatear_precio, resolver_establecimiento,
    armar_item_auditoria, ejecutar_auditoria_y_exportar,
)

_COLUMNAS_REPORTE = [
    'Fecha', 'Suc', 'EAN', 'Articulo', 'Talle',
    'ColorNom', 'Remito', 'Nombre', 'Cantidad', 'PreUni',
]


def _parsear_almacen(suc_raw: str):
    """Convierte el valor de Suc en el código de almacén CEGID (6 dígitos)."""
    if suc_raw.upper() == 'DEPOSITO':
        return '240001'
    match = re.match(r'^\d{5,6}', suc_raw)
    if match:
        almacen = match.group(0)
        return almacen if len(almacen) == 6 else f'0{almacen}'
    return None


def process_bestsox_pedido_proveedor(input_path, output_path):
    """
    Procesa un .xlsx de BestSox (puede tener múltiples hojas).
    Genera el CSV para CEGID y retorna el informe de auditoría.
    """
    try:
        sheets = pd.read_excel(input_path, sheet_name=None)
        frames = list(sheets.values())
        data_all = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()

        conflictos_suc = detectar_conflictos_suc(data_all, _COLUMNAS_REPORTE)

        registros_cegid = []
        items_auditoria = []
        prev_fecha_str = prev_suc = prev_referencia = None

        for _, row in data_all.iterrows():
            try:
                # ── Fecha ─────────────────────────────────────────────────────
                fecha = row['Fecha']
                fecha_str = None
                if not pd.isna(fecha):
                    if isinstance(fecha, (str, int, float)):
                        try:
                            fecha = pd.to_datetime(fecha, errors='raise')
                        except Exception:
                            fecha = None
                    if isinstance(fecha, pd.Timestamp):
                        fecha_str = fecha.strftime('%d%m%y')

                if not fecha_str:
                    ref_act = str(row['Remito']).strip()
                    suc_act = str(row['Suc']).strip()
                    if prev_fecha_str and suc_act == prev_suc and ref_act == prev_referencia:
                        fecha_str = prev_fecha_str
                    else:
                        print(f"Formato inesperado de Fecha: {fecha}")
                        continue

                # ── Referencia ────────────────────────────────────────────────
                referencia = str(row['Remito']).strip()
                if not (referencia.startswith('R') and len(referencia) == 13):
                    print(f"Referencia inválida: {referencia}")
                    continue

                # ── Código de barras ──────────────────────────────────────────
                ean_val = row['EAN']
                if isinstance(ean_val, float):
                    ean_val = int(ean_val)
                codigo_barras = str(ean_val).strip()
                if len(codigo_barras) not in (12, 13) or not codigo_barras.isdigit():
                    print(f"Código de barras inválido: {codigo_barras}")
                    continue

                # ── Almacén ───────────────────────────────────────────────────
                almacen = _parsear_almacen(str(row['Suc']).strip())
                if almacen is None:
                    print(f"Almacén inválido: {row['Suc']}")
                    continue

                # ── Cantidad / Precio ─────────────────────────────────────────
                cantidad = row['Cantidad']
                if not isinstance(cantidad, (int, float)):
                    continue
                precio_float = round(float(row['PreUni']), 2)

                # ── Datos del artículo ────────────────────────────────────────
                establecimiento = resolver_establecimiento(row.get('Nombre', ''))
                codigo_articulo = re.sub(r'[/\-]', '', str(row.get('Articulo', '')).strip())
                talle = str(row.get('Talle', '')).strip()
                color = str(row.get('ColorNom', '')).strip()
                descripcion = str(row.get('Descripcion', '')).strip().upper()

                registros_cegid.append({
                    'CAB': 'ZCOC1_',
                    'REFERENCIA INTERNA': referencia,
                    'FECHA': fecha_str,
                    'COD PROVEEDOR': 'BESTS',
                    'CODIGO BARRAS': codigo_barras,
                    'CANTIDAD': int(cantidad),
                    'PRECIO': formatear_precio(precio_float),
                    'ALMACEN': almacen,
                    'ESTABLECIMIENTO': establecimiento,
                    'DESCUENTO': 14,
                })
                items_auditoria.append(armar_item_auditoria(
                    barras=codigo_barras,
                    articulo=codigo_articulo,
                    precio_float=precio_float,
                    detalles={
                        'Material': codigo_articulo,
                        'Descripción': descripcion,
                        'ColorNom': color,
                        'Size': talle,
                        'Codigo_EAN': codigo_barras,
                        'Precio': precio_float,
                    },
                ))

                prev_fecha_str, prev_suc, prev_referencia = fecha_str, almacen, referencia

            except Exception as e:
                print(f"Error procesando fila: {e}")
                continue

        if not registros_cegid:
            return None

        return ejecutar_auditoria_y_exportar(
            items_auditoria, registros_cegid, output_path,
            proveedor='BestSox', conflictos_suc=conflictos_suc,
        )

    except Exception as e:
        raise RuntimeError(f"Error al procesar el archivo BestSox: {e}")
