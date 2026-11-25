import pandas as pd

from backend.utils.pedido_helpers import (
    detectar_conflictos_suc, formatear_precio, resolver_establecimiento,
    resolver_descuento, armar_item_auditoria, ejecutar_auditoria_y_exportar,
    detectar_ean_vacios,
)


_COLUMNAS_REPORTE = [
    'Fecha', 'Suc', 'Articulo', 'Descripcion', 'Talle', 'ColorNom', 'EAN',
    'Numero de Factura', 'Remito', 'Nombre', 'Costo', 'Cantidad', 'DESC',
]


def _validar_columnas(data: pd.DataFrame) -> None:
    requeridas = ['Fecha', 'Suc', 'Articulo', 'EAN', 'Remito', 'Nombre', 'Costo', 'Cantidad']
    faltantes = [col for col in requeridas if col not in data.columns]
    if faltantes:
        raise RuntimeError(
            'No se pudo procesar el template de Rocotex porque faltan estas columnas: '
            + ', '.join(faltantes)
        )


def process_rocotex_pedido_proveedor(input_path: str, output_path: str) -> dict:
    """Procesa el template XLSX de Rocotex y genera el CSV para CEGID."""
    try:
        sheets = pd.read_excel(input_path, sheet_name=None, dtype={'EAN': str})
        frames = [df for df in sheets.values() if not df.empty]
        if not frames:
            raise RuntimeError('El archivo no contiene datos válidos.')

        data = pd.concat(frames, ignore_index=True)
        data.columns = data.columns.astype(str).str.strip()
        _validar_columnas(data)
        # El template usa celdas combinadas para la fecha: solo la primera
        # fila de cada bloque trae el valor y las siguientes quedan vacias.
        data['Fecha'] = data['Fecha'].ffill()

        conflictos_suc = detectar_conflictos_suc(data, _COLUMNAS_REPORTE)
        ean_vacios = detectar_ean_vacios(data, _COLUMNAS_REPORTE)
        registros_cegid = []
        items_auditoria = []

        for i, row in data.iterrows():
            try:
                fecha_str = pd.to_datetime(row['Fecha'], dayfirst=True).strftime('%d%m%y')
                referencia = str(row['Remito']).strip()
                if '-' not in referencia:
                    referencia = referencia.zfill(12)
                    referencia = f'{referencia[:4]}-{referencia[4:]}'

                codigo_barras = str(row['EAN']).strip()
                cantidad = int(float(str(row['Cantidad']).replace(',', '.')))
                precio_float = round(float(row['Costo']), 2)
                establecimiento = resolver_establecimiento(row.get('Nombre', ''))
                almacen = str(row['Suc']).strip().zfill(6)
                descuento = resolver_descuento(row.get('DESC', 0))
                if float(descuento).is_integer():
                    descuento = int(descuento)
                articulo = str(row.get('Articulo', '')).strip() or codigo_barras
                descripcion = str(row.get('Descripcion', '')).strip()
                talle = str(row.get('Talle', '')).strip()
                color = str(row.get('ColorNom', '')).strip()

                registros_cegid.append({
                    'CAB': 'ZCOC1_',
                    'REFERENCIA INTERNA': referencia,
                    'FECHA': fecha_str,
                    'COD PROVEEDOR': 'ROCOT',
                    'CODIGO BARRAS': codigo_barras,
                    'CANTIDAD': cantidad,
                    'PRECIO': formatear_precio(precio_float),
                    'ALMACEN': almacen,
                    'ESTABLECIMIENTO': establecimiento,
                    'DESCUENTO': descuento,
                })
                items_auditoria.append(armar_item_auditoria(
                    barras=codigo_barras,
                    articulo=articulo,
                    precio_float=precio_float,
                    detalles={
                        'Material': articulo,
                        'Size': talle,
                        'Codigo_EAN': codigo_barras,
                        'Descripción': descripcion,
                        'Color': color,
                        'Precio': precio_float,
                    },
                ))
            except Exception as e:
                print(f'Error en fila {i}: {e}')
                continue

        if not registros_cegid:
            return None

        return ejecutar_auditoria_y_exportar(
            items_auditoria, registros_cegid, output_path,
            proveedor='ROCOTEX', conflictos_suc=conflictos_suc,
            ean_vacios=ean_vacios,
            sort_by='REFERENCIA INTERNA',
        )
    except Exception as e:
        raise RuntimeError(f'Error crítico en procesador ROCOTEX: {e}')
