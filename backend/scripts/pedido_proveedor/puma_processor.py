import pandas as pd
import re
import os
from backend.utils.pedido_helpers import (
    formatear_precio, resolver_establecimiento,
    armar_item_auditoria, ejecutar_auditoria_y_exportar,
)

# Constantes
_CAB = 'ZCOC1_'
_COD_PROVEEDOR = 'UNISO'
_ALMACEN = '240001'
_DESCUENTO = '11,445'

# Mapeo de talles numéricos de indumentaria → letras
_TALLES_IND = {
    '0.0': 'XS', '1.0': 'S', '2.0': 'M',
    '3.0': 'L',  '4.0': 'XL', '5.0': 'XXL', '6.0': 'XXXL',
}


def _fecha_desde_nombre_archivo(file_name: str) -> str:
    """
    Extrae la fecha del nombre del archivo Puma.
    Formato esperado: detalle_fact_YYMMDDHHMMSS → retorna DDMMYY.
    """
    match = re.search(r'detalle_fact_(\d{6})\d{6}', file_name)
    if not match:
        raise ValueError(
            "El nombre del archivo Puma no contiene una fecha válida "
            "(esperado: detalle_fact_YYMMDD...)."
        )
    fecha_raw = match.group(1)
    return f'{fecha_raw[4:6]}{fecha_raw[2:4]}{fecha_raw[0:2]}'  # ddmmyy


def process_puma_pedido_proveedor(input_path, output_path):
    """
    Procesa un .csv de Puma (separado por ';').
    Genera el CSV para CEGID y retorna el informe de auditoría.
    """
    fecha_cegid = _fecha_desde_nombre_archivo(os.path.basename(input_path))

    df = pd.read_csv(input_path, sep=';', header=0, dtype=str)
    df = df.map(lambda x: x.strip() if isinstance(x, str) else x)

    registros_cegid = []
    items_auditoria = []

    for _, row in df.iterrows():
        if not re.match(r'^\d{4}-\d{8}$', str(row['Remito'])):
            continue
        if not str(row['Codigo de EAN']).isdigit():
            continue

        # Limpieza de código de artículo (quita espacios internos: "312731 18" → "31273118")
        articulo_limpio = str(row['Articulo']).replace(' ', '')
        codigo_barras = str(row['Codigo de EAN']).zfill(13)
        cantidad = row['Unidades']
        precio_float = float(row['Precio']) if row['Precio'] else 0.0
        establecimiento = resolver_establecimiento(row.get('Nombre', ''))

        talle_str = str(row['Talle']).strip()
        talle_size = talle_str.replace('.', ',')
        talle_ind = _TALLES_IND.get(talle_str, '')

        registros_cegid.append({
            'CAB': _CAB,
            'REFERENCIA INTERNA': row['Remito'],
            'FECHA': fecha_cegid,
            'COD PROVEEDOR': _COD_PROVEEDOR,
            'CODIGO BARRAS': codigo_barras,
            'CANTIDAD': cantidad,
            'PRECIO': formatear_precio(precio_float),
            'ALMACEN': _ALMACEN,
            'ESTABLECIMIENTO': establecimiento,
            'DESCUENTO': _DESCUENTO,
        })
        items_auditoria.append(armar_item_auditoria(
            barras=codigo_barras,
            articulo=articulo_limpio,
            precio_float=precio_float,
            detalles={
                'Material': articulo_limpio,
                'Modelo': str(row['Modelo']).strip(),
                'Color': str(row['Color']).strip(),
                'Size': talle_size,
                'Talles IND': talle_ind,
                'Genero': str(row['Genero']).strip(),
                'Codigo_EAN': codigo_barras,
                'Precio': precio_float,
            },
        ))

    return ejecutar_auditoria_y_exportar(
        items_auditoria, registros_cegid, output_path,
        proveedor='Puma', encoding=None,
    )