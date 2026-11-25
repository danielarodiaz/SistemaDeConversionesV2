import re

import pandas as pd

from backend.utils.pedido_helpers import (
    detectar_conflictos_suc, formatear_precio, resolver_establecimiento,
    armar_item_auditoria, ejecutar_auditoria_y_exportar, detectar_ean_vacios,
)


_COLUMNAS_REPORTE = [
    'Fecha', 'Suc', 'Articulo', 'Descripcion', 'Talle', 'ColorNom', 'EAN',
    'Comprobante', 'Remito', 'Empresa', 'Cantidad', 'PreUni', 'Dto.Com',
]


def _parsear_precio(valor) -> float:
    texto = str(valor or "").strip()
    texto = texto.replace("$", "").replace(" ", "")
    texto = re.sub(r"[^0-9,.\-]", "", texto)
    if "," in texto:
        texto = texto.replace(".", "").replace(",", ".")
    return round(float(texto or 0), 2)


def _validar_columnas(data: pd.DataFrame) -> None:
    requeridas = ['Fecha', 'Suc', 'EAN', 'Remito', 'Empresa', 'Cantidad', 'PreUni']
    faltantes = [col for col in requeridas if col not in data.columns]
    if faltantes:
        raise RuntimeError("Columnas requeridas no encontradas: " + ", ".join(faltantes))


def process_winar_pedido_proveedor(input_path: str, output_path: str) -> dict:
    """
    Procesa un .xlsx de Winar (puede tener múltiples hojas).
    Genera el CSV para CEGID y retorna el informe de auditoría.

    Columnas esperadas: Fecha, Suc, EAN, Remito, Empresa, Cantidad, PreUni.
    """
    try:
        sheets = pd.read_excel(input_path, sheet_name=None, dtype={'EAN': str})
        frames = [df for df in sheets.values() if not df.empty]
        if not frames:
            raise RuntimeError("El archivo no contiene datos válidos.")

        data = pd.concat(frames, ignore_index=True)
        data.columns = data.columns.astype(str).str.strip()
        _validar_columnas(data)

        conflictos_suc = detectar_conflictos_suc(data, _COLUMNAS_REPORTE)
        ean_vacios = detectar_ean_vacios(data, _COLUMNAS_REPORTE)

        registros_cegid = []
        items_auditoria = []

        for i, row in data.iterrows():
            try:
                fecha_str = pd.to_datetime(row['Fecha'], dayfirst=True).strftime('%d%m%y')
                referencia = str(row['Remito']).strip().zfill(4)
                codigo_barras = str(row['EAN']).strip()
                cantidad = int(float(str(row['Cantidad']).replace(",", ".")))
                precio_float = _parsear_precio(row['PreUni'])
                establecimiento = resolver_establecimiento(row.get('Empresa', ''))
                almacen = str(row['Suc']).strip().zfill(6)
                descripcion_raw = str(row.get('Descripcion', '')).strip()
                articulo = str(row.get('Articulo', '')).strip() or codigo_barras
                talle = str(row.get('Talle', '')).strip()
                color = str(row.get('ColorNom', '')).strip()

                registros_cegid.append({
                    'CAB': 'ZCOC1_',
                    'REFERENCIA INTERNA': referencia,
                    'FECHA': fecha_str,
                    'COD PROVEEDOR': 'WINRI',
                    'CODIGO BARRAS': codigo_barras,
                    'CANTIDAD': cantidad,
                    'PRECIO': formatear_precio(precio_float),
                    'ALMACEN': almacen,
                    'ESTABLECIMIENTO': establecimiento,
                    'DESCUENTO': 0,
                })
                items_auditoria.append(armar_item_auditoria(
                    barras=codigo_barras,
                    articulo=articulo,
                    precio_float=precio_float,
                    detalles={
                        'Material': articulo,
                        'Size': talle,
                        'Codigo_EAN': codigo_barras,
                        'Descripción': descripcion_raw,
                        'Color': color,
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
            proveedor='WINAR', conflictos_suc=conflictos_suc,
            ean_vacios=ean_vacios,
            sort_by='REFERENCIA INTERNA',
        )

    except Exception as e:
        raise RuntimeError(f"Error crítico en procesador WINAR: {e}")
