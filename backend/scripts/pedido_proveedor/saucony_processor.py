import pandas as pd
from backend.utils.pedido_helpers import (
    detectar_conflictos_suc, formatear_precio, resolver_establecimiento,
    armar_item_auditoria, ejecutar_auditoria_y_exportar,
)

_COLUMNAS_REPORTE = [
    'Fecha', 'Suc', 'EAN', 'Descripcion',
    'Comprobante', 'Remito', 'Nombre',
    'Cantidad', 'Costo',
]


def process_saucony_pedido_proveedor(input_path: str, output_path: str) -> dict:
    """
    Procesa un .xlsx de Saucony (puede tener múltiples hojas).
    Genera el CSV para CEGID y retorna el informe de auditoría.

    Columnas esperadas: Fecha, Remito, EAN, Cantidad, Costo, Nombre, Suc
    """
    try:
        sheets = pd.read_excel(input_path, sheet_name=None)
        # Consolidar todas las hojas en un solo DataFrame
        frames = [df for df in sheets.values() if not df.empty]
        if not frames:
            raise RuntimeError("El archivo no contiene datos válidos.")
        data = pd.concat(frames, ignore_index=True)

        conflictos_suc = detectar_conflictos_suc(data, _COLUMNAS_REPORTE)

        registros_cegid = []
        items_auditoria = []

        for i, row in data.iterrows():
            try:
                fecha_str = pd.to_datetime(row['Fecha'], dayfirst=True).strftime('%d%m%y')
                referencia = str(row['Remito']).strip().zfill(4)
                codigo_barras = str(row['EAN']).strip()
                cantidad = int(row['Cantidad'])
                precio_float = round(float(row['Costo']), 2)
                establecimiento = resolver_establecimiento(row.get('Nombre', ''))
                almacen = str(row['Suc']).encode('latin1').decode('utf-8', 'ignore').strip().zfill(6)
                descuento = 10
                descripcion_raw = str(row.get('Descripcion', '')).strip()

                registros_cegid.append({
                    'CAB': 'ZCOC1_',
                    'REFERENCIA INTERNA': referencia,
                    'FECHA': fecha_str,
                    'COD PROVEEDOR': 'SUOLA',
                    'CODIGO BARRAS': codigo_barras,
                    'CANTIDAD': cantidad,
                    'PRECIO': formatear_precio(precio_float),
                    'ALMACEN': almacen,
                    'ESTABLECIMIENTO': establecimiento,
                    'DESCUENTO': descuento,
                })
                items_auditoria.append(armar_item_auditoria(
                    barras=codigo_barras,
                    articulo=codigo_barras,
                    precio_float=precio_float,
                    detalles={
                        'Material': codigo_barras,
                        'Size': '',
                        'Codigo_EAN': codigo_barras,
                        'Descripción': descripcion_raw,
                        'Precio': precio_float,
                    },
                ))

            except Exception as e:
                print(f"❌ Error en fila {i}: {e}")
                continue

        if not registros_cegid:
            return None

        return ejecutar_auditoria_y_exportar(
            items_auditoria, registros_cegid, output_path,
            proveedor='SAUCONY', conflictos_suc=conflictos_suc,
            sort_by='REFERENCIA INTERNA',
        )

    except Exception as e:
        raise RuntimeError(f"Error crítico en procesador SAUCONY: {e}")
