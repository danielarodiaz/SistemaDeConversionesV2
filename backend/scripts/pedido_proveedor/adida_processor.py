import pandas as pd
import re
from backend.utils.pedido_helpers import (
    formatear_precio, resolver_establecimiento, armar_item_auditoria,
)
from backend.services.validator import CegidValidator
from backend.utils.cegid_utils import obtener_codigo_barra


def _convertir_talle(size: str) -> str:
    """
    Normaliza los talles de Adidas para la búsqueda en CEGID.
    Ej: 'NS'→'U', '42-'→'42.5', '2XL'→'XXL', 'M'→'M'
    """
    if size == 'NS':
        return 'U'
    if re.match(r'^\d+-$', size):
        return size.replace('-', '.5')
    if 'XL' in size and size[:-2].isdigit():
        return 'X' * int(size[:-2]) + 'L'
    m = re.match(r'^[A-Z]+', size)
    return m.group(0) if m else size


def _particionar_en_lotes(df: pd.DataFrame) -> pd.DataFrame:
    """
    Parte grupos de más de 100 líneas respetando cambios de precio.
    Modifica REFERENCIA INTERNA agregando '/1', '/2', etc.
    """
    partes = []
    for ref, grupo in df.groupby('REFERENCIA INTERNA', sort=False):
        if len(grupo) <= 100:
            partes.append(grupo)
            continue
        lote = 1
        chunk = []
        precio_actual = None
        for _, fila in grupo.iterrows():
            if precio_actual is not None and fila['PRECIO'] != precio_actual and len(chunk) > 100:
                df_chunk = pd.DataFrame(chunk)
                df_chunk['REFERENCIA INTERNA'] = f'{ref}/{lote}'
                partes.append(df_chunk)
                lote += 1
                chunk = []
            precio_actual = fila['PRECIO']
            chunk.append(fila)
        if chunk:
            df_chunk = pd.DataFrame(chunk)
            df_chunk['REFERENCIA INTERNA'] = f'{ref}/{lote}'
            partes.append(df_chunk)
    return pd.concat(partes, ignore_index=True)


def process_adidas_pedido_proveedor(input_path, output_path):
    """
    Procesa un .xlsx de Adidas (hoja 'Datos', solo pedidos facturados).
    Genera el CSV para CEGID con partición de lotes y retorna el informe de auditoría.
    """
    df = pd.read_excel(input_path, sheet_name='Datos', dtype={'EAN': str})
    df = df[df['Status de pedido'] == 'Pedido Facturado']
    df = df[df['Payer'].isin([7300000357, 7300000658])]
    df.sort_values(by=['Material'], inplace=True)

    items_auditoria = []
    registros_cegid = []

    for i, (_, row) in enumerate(df.iterrows()):
        try:
            payer = str(row['Payer']).strip()
            establecimiento = '002' if payer == '7300000658' else '001'
            fecha = pd.to_datetime(row['Invoice Date'], dayfirst=True).strftime('%d%m%y')

            # Normalización de EAN con fallback por Material + Talle
            ean = str(row['EAN']).strip().replace('.0', '') if pd.notna(row['EAN']) else ''
            if ean == '' or '-' in ean:
                material = str(row['Material']).strip()
                size_conv = _convertir_talle(str(row['Size']).strip().upper())
                ean_final = obtener_codigo_barra(material, size_conv) or ean
            else:
                ean_final = ean

            precio_float = round(float(str(row['Unit Price']).replace('$', '').strip()), 2)
            articulo_limpio = str(row['Material']).strip()

            items_auditoria.append(armar_item_auditoria(
                barras=ean_final,
                articulo=articulo_limpio,
                precio_float=precio_float,
                detalles={
                    'Material': articulo_limpio,
                    'Size': str(row['Size']).strip(),
                    'Descripción': str(row['Descripción']).strip(),
                    'Division': str(row['Division Description']).strip(),
                    'Sports': str(row['Sports Description']).strip(),
                    'Age Group': str(row['Age Group']).strip(),
                    'Unit Price': precio_float,
                    'EAN': ean_final,
                },
            ))
            registros_cegid.append({
                'CAB': 'ZCOC1_',
                'REFERENCIA INTERNA': str(row['Delivery']),
                'FECHA': fecha,
                'COD PROVEEDOR': 'ADIDA',
                'CODIGO BARRAS': ean_final,
                'CANTIDAD': int(row['Quantity']),
                'PRECIO': precio_float,           # float temporal → se formatea al final
                'ALMACEN': '240001',
                'ESTABLECIMIENTO': establecimiento,
                'DESCUENTO': 8.15,
            })

        except Exception as e:
            print(f"❌ Error en fila {i} (Material: {row.get('Material')}): {e}")
            continue

    print(f"📦 Items Adidas listos para auditar: {len(items_auditoria)}")
    informe = CegidValidator.auditar_items(items_auditoria)

    # Partición de lotes + formateo de precio antes de exportar
    df_transformado = pd.DataFrame(registros_cegid)
    df_transformado.sort_values(by=['REFERENCIA INTERNA', 'PRECIO'], inplace=True)
    df_final = _particionar_en_lotes(df_transformado)
    df_final['PRECIO'] = df_final['PRECIO'].apply(formatear_precio)
    df_final.to_csv(output_path, sep='|', index=False)

    return informe