import pandas as pd

from backend.utils.pedido_helpers import (
    detectar_conflictos_suc, formatear_precio, resolver_establecimiento,
    resolver_descuento, armar_item_auditoria, ejecutar_auditoria_y_exportar,
    detectar_ean_vacios,
)


_COLUMNAS_REPORTE = [
    'Fecha', 'Suc', 'Articulo', 'Descripcion', 'Talle', 'ColorNom', 'EAN',
    'Comprobante', 'Remito', 'Empresa', 'Cantidad', 'PreUni', 'Dto.Com',
]


def _validar_columnas(data: pd.DataFrame) -> None:
    requeridas = [
        'Fecha', 'Suc', 'Articulo', 'Descripcion', 'Talle', 'ColorNom',
        'EAN', 'Remito', 'Empresa', 'Cantidad', 'PreUni',
    ]
    faltantes = [col for col in requeridas if col not in data.columns]
    if faltantes:
        raise RuntimeError(
            'No se pudo procesar el template de Destreza porque faltan estas columnas: '
            + ', '.join(faltantes)
        )


def _mapear_articulos_por_color(data: pd.DataFrame) -> dict[tuple[str, str], str]:
    """
    Destreza usa un mismo articulo base para colores distintos, pero CEGID
    necesita un modelo diferente por color: 5604.01, 5604.02, etc.
    Se conserva el orden de primera aparicion del template.
    """
    mapa = {}
    vistos_por_articulo = {}
    for _, row in data.iterrows():
        articulo = str(row.get('Articulo', '')).strip()
        color = str(row.get('ColorNom', '')).strip()
        if not articulo:
            continue
        clave_color = color.upper() or '__SIN_COLOR__'
        colores = vistos_por_articulo.setdefault(articulo, [])
        if clave_color not in colores:
            colores.append(clave_color)
        mapa[(articulo, clave_color)] = f'{articulo}.{colores.index(clave_color) + 1:02d}'
    return mapa


def process_destreza_pedido_proveedor(input_path: str, output_path: str) -> dict:
    """Procesa el template XLSX de Destreza y genera el CSV para CEGID."""
    try:
        sheets = pd.read_excel(input_path, sheet_name=None, dtype={'EAN': str})
        frames = [df for df in sheets.values() if not df.empty]
        if not frames:
            raise RuntimeError('El archivo no contiene datos validos.')

        data = pd.concat(frames, ignore_index=True)
        data.columns = data.columns.astype(str).str.strip()
        _validar_columnas(data)

        conflictos_suc = detectar_conflictos_suc(data, _COLUMNAS_REPORTE)
        ean_vacios = detectar_ean_vacios(data, _COLUMNAS_REPORTE)
        articulos_por_color = _mapear_articulos_por_color(data)
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
                precio_float = round(float(row['PreUni']), 2)
                establecimiento = resolver_establecimiento(row.get('Empresa', ''))
                almacen = str(row['Suc']).strip().zfill(6)
                descuento = resolver_descuento(row.get('Dto.Com', 0))
                if float(descuento).is_integer():
                    descuento = int(descuento)

                articulo_base = str(row.get('Articulo', '')).strip() or codigo_barras
                color = str(row.get('ColorNom', '')).strip()
                clave_color = color.upper() or '__SIN_COLOR__'
                articulo_auditoria = articulos_por_color.get(
                    (articulo_base, clave_color), articulo_base
                )
                descripcion = str(row.get('Descripcion', '')).strip()
                talle = str(row.get('Talle', '')).strip()

                registros_cegid.append({
                    'CAB': 'ZCOC1_',
                    'REFERENCIA INTERNA': referencia,
                    'FECHA': fecha_str,
                    'COD PROVEEDOR': 'ROBER',
                    'CODIGO BARRAS': codigo_barras,
                    'CANTIDAD': cantidad,
                    'PRECIO': formatear_precio(precio_float),
                    'ALMACEN': almacen,
                    'ESTABLECIMIENTO': establecimiento,
                    'DESCUENTO': descuento,
                })
                items_auditoria.append(armar_item_auditoria(
                    barras=codigo_barras,
                    articulo=articulo_auditoria,
                    precio_float=precio_float,
                    detalles={
                        'Material': articulo_auditoria,
                        'Articulo base': articulo_base,
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
            proveedor='DESTREZA', conflictos_suc=conflictos_suc,
            ean_vacios=ean_vacios,
            sort_by='REFERENCIA INTERNA',
        )
    except Exception as e:
        raise RuntimeError(f'Error critico en procesador DESTREZA: {e}')
