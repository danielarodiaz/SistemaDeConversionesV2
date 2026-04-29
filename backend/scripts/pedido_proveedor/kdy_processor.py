import pandas as pd
from backend.utils.pedido_helpers import (
    detectar_conflictos_suc, formatear_precio, resolver_establecimiento,
    armar_item_auditoria, ejecutar_auditoria_y_exportar,
)

_COLUMNAS_REPORTE = [
    'Fecha', 'Suc', 'EAN', 'Descripcion',
    'Comprobante', 'Remito', 'Empresa',
    'Cantidad', 'PreUni', 'Dto.Com',
]


def _codigo_articulo_desde_ean(ean_raw: str, descripcion: str) -> str:
    """
    Deriva el código de artículo desde el EAN de Kenya.
    EAN: 'Y220102/106/0XL' → primeros 11 chars sin '/' = 'Y220102106'
    Si la descripción contiene 'NIÑO' se añade 'N' al final.
    """
    codigo = ean_raw.replace('/', '')[:11]
    if 'NIÑO' in descripcion.upper():
        codigo += 'N'
    return codigo


def _talle_desde_descripcion(descripcion: str) -> str:
    """
    Extrae el talle de la descripción del artículo Kenya.
    Ej: 'TERMICA OMEGA BLANCO T:S' → 'S'
    """
    if ':' in descripcion:
        return descripcion.split(':', 1)[1].strip()
    return ''


def process_kdy_pedido_proveedor(input_path, output_path):
    """
    Procesa un .xlsx de Kenya (KDY).
    Genera el CSV para CEGID y retorna el informe de auditoría.
    """
    try:
        data = pd.read_excel(input_path)
        conflictos_suc = detectar_conflictos_suc(data, _COLUMNAS_REPORTE)

        registros_cegid = []
        items_auditoria = []

        for i, row in data.iterrows():
            try:
                fecha_str = pd.to_datetime(row['Fecha'], dayfirst=True).strftime('%d%m%y')

                referencia = str(row['Remito']).strip().zfill(12)
                referencia_formateada = f'{referencia[:4]}-{referencia[4:]}'

                # Kenya usa '/' en el EAN → lo convierte a '-' para CEGID
                codigo_barras = str(row['EAN']).strip().replace('/', '-')
                cantidad = int(row['Cantidad'])
                precio_float = round(float(row['PreUni']), 2)
                establecimiento = resolver_establecimiento(row.get('Empresa', ''))
                almacen = str(int(row['Suc'])).zfill(6)
                descuento = row['Dto.Com']

                descripcion_raw = str(row.get('Descripcion', '')).strip()
                codigo_articulo = _codigo_articulo_desde_ean(str(row['EAN']).strip(), descripcion_raw)
                talle = _talle_desde_descripcion(descripcion_raw)

                registros_cegid.append({
                    'CAB': 'ZCOC1_',
                    'REFERENCIA INTERNA': referencia_formateada,
                    'FECHA': fecha_str,
                    'COD PROVEEDOR': 'KENYA',
                    'CODIGO BARRAS': codigo_barras,
                    'CANTIDAD': cantidad,
                    'PRECIO': formatear_precio(precio_float),
                    'ALMACEN': almacen,
                    'ESTABLECIMIENTO': establecimiento,
                    'DESCUENTO': descuento,
                })
                items_auditoria.append(armar_item_auditoria(
                    barras=codigo_barras,
                    articulo=codigo_articulo,
                    precio_float=precio_float,
                    detalles={
                        'Material': codigo_articulo,
                        'Size': talle,
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
            proveedor='KDY', conflictos_suc=conflictos_suc,
            sort_by=None,
        )

    except Exception as e:
        raise RuntimeError(f"Error crítico en procesador KDY: {e}")