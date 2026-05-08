import pandas as pd
from backend.utils.pedido_helpers import (
    detectar_conflictos_suc, formatear_precio, resolver_establecimiento,
    resolver_descuento, armar_item_auditoria, ejecutar_auditoria_y_exportar,
)

_COLUMNAS_REPORTE = [
    'Fecha', 'Suc', 'EAN', 'Descripcion',
    'Comprobante', 'Remito', 'Empresa',
    'Cantidad', 'PreUni', 'Dto.Com',
]


def _formatear_referencia(remito_raw: str) -> str:
    """
    Formatea el remito de Braku al estándar CEGID.
    Acepta formato con guión 'XXXX-YYYYYYYY' o número plano.
    Retorna 'XXXX-YYYYYYYY' (parte1 zfill(4) + guión + parte2 zfill(8)).
    """
    remito = str(remito_raw).strip()
    if '-' in remito:
        parte1, parte2 = remito.split('-', 1)
        return f"{parte1.strip().zfill(4)}-{parte2.strip().zfill(8)}"
    # Si viene sin guión, lo trata como número completo de 12 dígitos
    remito_z = remito.zfill(12)
    return f"{remito_z[:4]}-{remito_z[4:]}"


def process_braku_pedido_proveedor(input_path: str, output_path: str) -> dict:
    """
    Procesa un .xlsx de Braku.
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
                referencia_formateada = _formatear_referencia(row['Remito'])
                codigo_barras = str(row['EAN']).strip().replace('/', '-')
                cantidad = int(row['Cantidad'])
                precio_float = round(float(row['PreUni']), 2)
                establecimiento = resolver_establecimiento(row.get('Empresa', ''))
                almacen = str(int(row['Suc'])).zfill(6)
                descuento = resolver_descuento(row.get('Dto.Com'))
                descripcion_raw = str(row.get('Descripcion', '')).strip()

                registros_cegid.append({
                    'CAB': 'ZCOC1_',
                    'REFERENCIA INTERNA': referencia_formateada,
                    'FECHA': fecha_str,
                    'COD PROVEEDOR': 'BRAKU',
                    'CODIGO BARRAS': codigo_barras,
                    'CANTIDAD': cantidad,
                    'PRECIO': formatear_precio(precio_float),
                    'ALMACEN': almacen,
                    'ESTABLECIMIENTO': establecimiento,
                    'DESCUENTO': descuento,
                })
                items_auditoria.append(armar_item_auditoria(
                    barras=codigo_barras,
                    articulo=codigo_barras,          # Braku no tiene código de artículo separado
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
            proveedor='BRAKU', conflictos_suc=conflictos_suc,
            sort_by='REFERENCIA INTERNA',
        )

    except Exception as e:
        raise RuntimeError(f"Error crítico en procesador BRAKU: {e}")