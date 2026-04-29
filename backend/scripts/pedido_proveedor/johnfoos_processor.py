import pandas as pd
import re
from backend.utils.pedido_helpers import (
    detectar_conflictos_suc, formatear_precio, resolver_establecimiento,
    armar_item_auditoria, ejecutar_auditoria_y_exportar,
)

_COLUMNAS_REPORTE = [
    'Fecha', 'Suc', 'EAN', 'Descripcion',
    'Remito', 'Empresa', 'Cantidad', 'PreUni', 'Dto.Com',
]


def _formatear_remito(valor) -> str:
    """Convierte el Remito a formato NNNN-NNNNNNNN (12 dígitos con guion)."""
    if pd.isna(valor):
        return ''
    valor_str = ''.join(ch for ch in str(valor).strip() if ch.isdigit())
    if not valor_str:
        return ''
    valor_str = valor_str.zfill(12)
    return f'{valor_str[:4]}-{valor_str[4:]}'


def process_johnfoos_pedido_proveedor(input_path, output_path):
    """
    Procesa un .xlsx de John Foos.
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
                referencia_formateada = _formatear_remito(row.get('Remito'))
                codigo_barras = str(row['EAN']).strip() if not pd.isna(row['EAN']) else ''
                cantidad = int(row['Cantidad'])
                precio_float = round(float(row['PreUni']), 2)
                establecimiento = resolver_establecimiento(row.get('Empresa', ''))
                almacen = str(int(row['Suc'])).zfill(6)
                dto_raw = row.get('Dto.Com', 0)

                # Artículo limpio: quitar '/' y '-' (ej. "950056/01" → "95005601")
                codigo_articulo = re.sub(r'[/\-]', '', str(row.get('Articulo', '')).strip())
                descripcion = str(row.get('Descripcion', '')).strip().upper()
                talle = str(row.get('Talle', '')).strip()

                registros_cegid.append({
                    'CAB': 'ZCOC1_',
                    'REFERENCIA INTERNA': referencia_formateada,
                    'FECHA': fecha_str,
                    'COD PROVEEDOR': 'FLING',
                    'CODIGO BARRAS': codigo_barras,
                    'CANTIDAD': cantidad,
                    'PRECIO': formatear_precio(precio_float),
                    'ALMACEN': almacen,
                    'ESTABLECIMIENTO': establecimiento,
                    'DESCUENTO': dto_raw,
                })
                items_auditoria.append(armar_item_auditoria(
                    barras=codigo_barras,
                    articulo=codigo_articulo,
                    precio_float=precio_float,
                    detalles={
                        'Material': codigo_articulo,
                        'Descripción': descripcion,
                        'Size': talle,
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
            proveedor='John Foos', conflictos_suc=conflictos_suc,
            sort_by=None,
        )

    except Exception as e:
        raise RuntimeError(f"Error al procesar el archivo John Foos: {e}")