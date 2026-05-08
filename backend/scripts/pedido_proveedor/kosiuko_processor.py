import os
import pandas as pd
from datetime import datetime
from backend.utils.cegid_utils import obtener_costos_por_codigos_barras
from backend.utils.pedido_helpers import (
    formatear_precio, armar_item_auditoria, ejecutar_auditoria_y_exportar,
)


def process_kosiuko_pedido_proveedor(input_path: str, output_path: str) -> dict:
    """
    Procesa archivos .txt de Kosiuko y los convierte a formato CSV estándar para CEGID.

    Formato de entrada:
    /DR
    *FE 22/10/2025
    4+3926911271NE10L
    4+3926911271NE10M
    ...

    Reglas:
    - CAB: 'ZCOC_'
    - REFERENCIA INTERNA: nombre del archivo sin extensión
    - FECHA: extraída de la línea *FE en formato ddmmyy
    - COD PROVEEDOR: 'KOWZEF'
    - CODIGO BARRAS: parte después del '+'
    - CANTIDAD: parte antes del '+'
    - PRECIO: precio de compra desde CEGID (por código de barras)
    - ALMACEN: '240001'
    - ESTABLECIMIENTO: '002'
    - DESCUENTO: 0
    """
    referencia_interna = os.path.splitext(os.path.basename(input_path))[0]

    with open(input_path, 'r', encoding='utf-8') as f:
        lines = f.readlines()

    fecha = None
    registros = []
    codigos_barras = []

    for line in lines:
        line = line.strip()
        if not line or line.startswith('/DR'):
            continue

        if line.startswith('*FE'):
            fecha_str = line.replace('*FE', '').strip()
            try:
                fecha = datetime.strptime(fecha_str, '%d/%m/%Y').strftime('%d%m%y')
            except ValueError:
                print(f"⚠️ Error parseando fecha: {fecha_str}")
            continue

        if '+' in line:
            try:
                parts = line.split('+')
                if len(parts) != 2:
                    continue
                cantidad = int(parts[0])
                codigo_barra = parts[1].strip()
                codigos_barras.append(codigo_barra)
                registros.append({
                    'CAB': 'ZCOC_',
                    'REFERENCIA INTERNA': referencia_interna,
                    'FECHA': fecha,
                    'COD PROVEEDOR': 'KOWZEF',
                    'CODIGO BARRAS': codigo_barra,
                    'CANTIDAD': cantidad,
                    'PRECIO': None,
                    'ALMACEN': '240001',
                    'ESTABLECIMIENTO': '002',
                    'DESCUENTO': 0,
                })
            except (ValueError, IndexError) as e:
                print(f"⚠️ Error procesando línea '{line}': {e}")
            continue

    if not registros:
        raise RuntimeError("No se encontraron registros válidos en el archivo.")

    # Obtener precios de CEGID por código de barras
    print(f"🔍 Buscando precios para {len(codigos_barras)} códigos de barras...")
    precios_cegid = obtener_costos_por_codigos_barras(codigos_barras)

    items_auditoria = []
    for reg in registros:
        cb = reg['CODIGO BARRAS']
        precio_float = 0.0
        if cb in precios_cegid:
            try:
                precio_float = float(precios_cegid[cb][1] or 0.0)
            except Exception:
                precio_float = 0.0
        reg['PRECIO'] = formatear_precio(precio_float)
        items_auditoria.append(armar_item_auditoria(
            barras=cb,
            articulo=cb,
            precio_float=precio_float,
            detalles={
                'Material': cb,
                'Size': '',
                'Codigo_EAN': cb,
                'Descripción': '',
                'Precio': precio_float,
            },
        ))

    return ejecutar_auditoria_y_exportar(
        items_auditoria, registros, output_path,
        proveedor='KOSIUKO', conflictos_suc=[],
        sort_by='CODIGO BARRAS',
    )