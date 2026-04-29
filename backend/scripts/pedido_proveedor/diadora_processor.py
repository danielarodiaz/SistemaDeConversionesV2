import pandas as pd
from backend.utils.pedido_helpers import (
    detectar_conflictos_suc, formatear_precio, resolver_establecimiento,
    armar_item_auditoria, ejecutar_auditoria_y_exportar,
)

_COLUMNAS_REPORTE = [
    'Fecha', 'Suc', 'EAN', 'Articulo', 'Talle',
    'Remito', 'Nombre', 'Cantidad', 'PreUni',
]


def process_diadora_pedido_proveedor(input_path, output_path):
    """
    Procesa un .xlsx de Diadora.
    Genera el CSV para CEGID y retorna el informe de auditoría.
    Nota: el código de artículo se muestra tal cual viene (ej. '3020/1'), sin limpiar.
    """
    try:
        data = pd.read_excel(input_path)
        data.rename(columns=lambda x: x.strip(), inplace=True)

        # Validar columnas requeridas
        required_columns = ['Fecha', 'Remito', 'EAN', 'Cantidad', 'PreUni', 'Suc', 'Nombre']
        missing = [c for c in required_columns if c not in data.columns]
        if missing:
            raise RuntimeError(f"Faltan columnas críticas en el archivo: {missing}")

        conflictos_suc = detectar_conflictos_suc(data, _COLUMNAS_REPORTE)

        registros_cegid = []
        items_auditoria = []

        for i, row in data.iterrows():
            try:
                fecha_str = pd.to_datetime(row['Fecha'], dayfirst=True).strftime('%d%m%y')

                referencia = str(row['Remito']).strip()
                if not referencia or len(referencia) != 15:
                    continue

                codigo_barras = str(row['EAN']).strip()
                if len(codigo_barras) != 13:
                    continue

                cantidad = row['Cantidad']
                precio_float = round(float(row['PreUni']), 2)

                almacen = str(row['Suc']).strip()
                if len(almacen) == 5:
                    almacen = f'0{almacen}'
                elif len(almacen) > 6:
                    almacen = almacen[:6]

                establecimiento = resolver_establecimiento(row.get('Nombre', ''))

                # Artículo se conserva tal cual (ej. "3020/1" no se limpia)
                codigo_articulo = str(row.get('Articulo', '')).strip()
                talle = str(row.get('Talle', '')).strip()
                descripcion = str(row.get('Descripcion', '')).strip()

                registros_cegid.append({
                    'CAB': 'ZCOC1_',
                    'REFERENCIA INTERNA': referencia,
                    'FECHA': fecha_str,
                    'COD PROVEEDOR': 'GSIET',
                    'CODIGO BARRAS': codigo_barras,
                    'CANTIDAD': int(cantidad),
                    'PRECIO': formatear_precio(precio_float),
                    'ALMACEN': almacen,
                    'ESTABLECIMIENTO': establecimiento,
                    'DESCUENTO': 8,
                })
                items_auditoria.append(armar_item_auditoria(
                    barras=codigo_barras,
                    articulo=codigo_articulo,
                    precio_float=precio_float,
                    detalles={
                        'Material': codigo_articulo,
                        'Size': talle,
                        'Descripción': descripcion,
                        'Codigo_EAN': codigo_barras,
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
            proveedor='Diadora', conflictos_suc=conflictos_suc,
            sort_by=None,
        )

    except Exception as e:
        raise RuntimeError(f"Error al procesar el archivo Diadora: {e}")
