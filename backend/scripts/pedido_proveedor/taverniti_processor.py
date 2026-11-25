import re
import unicodedata

import pandas as pd

from backend.utils.pedido_helpers import (
    detectar_conflictos_suc, formatear_precio, resolver_establecimiento,
    resolver_descuento, armar_item_auditoria, ejecutar_auditoria_y_exportar,
    detectar_ean_vacios,
)


_COLUMNAS_REPORTE = [
    'Fecha', 'Suc', 'EAN', 'Articulo', 'Descripcion',
    'Comprobante', 'Remito', 'Empresa',
    'Cantidad', 'PreUni', 'Dto.Com',
]

_COLUMNAS_ALIASES = {
    'fecha': 'Fecha',
    'suc': 'Suc',
    'articulo': 'Articulo',
    'artculo': 'Articulo',
    'descripcion': 'Descripcion',
    'descripcin': 'Descripcion',
    'talle': 'Talle',
    'colornom': 'ColorNom',
    'ean': 'EAN',
    'comprobante': 'Comprobante',
    'remito': 'Remito',
    'empresa': 'Empresa',
    'cantidad': 'Cantidad',
    'preuni': 'PreUni',
    'dtocom': 'Dto.Com',
}


def _normalizar_nombre_columna(nombre: str) -> str:
    texto = unicodedata.normalize('NFKD', str(nombre).strip().lower())
    texto = ''.join(char for char in texto if not unicodedata.combining(char))
    texto = texto.replace('�', '')
    return re.sub(r'[^a-z0-9]', '', texto)


def _normalizar_columnas(data: pd.DataFrame) -> pd.DataFrame:
    renombres = {}
    for columna in data.columns:
        clave = _normalizar_nombre_columna(columna)
        if clave in _COLUMNAS_ALIASES:
            renombres[columna] = _COLUMNAS_ALIASES[clave]
    return data.rename(columns=renombres)


def _validar_columnas(data: pd.DataFrame) -> None:
    requeridas = ['Fecha', 'Suc', 'EAN', 'Remito', 'Empresa', 'Cantidad', 'PreUni']
    faltantes = [col for col in requeridas if col not in data.columns]
    if faltantes:
        raise RuntimeError("Columnas requeridas no encontradas: " + ", ".join(faltantes))


def _referencia_desde_remito(remito_raw) -> str:
    referencia = str(remito_raw).strip()
    if '-' in referencia:
        partes = referencia.split('-', 1)
        prefijo = re.sub(r'\D', '', partes[0]).zfill(4)[-4:]
        numero = re.sub(r'\D', '', partes[1]).zfill(8)[-8:]
        return f'{prefijo}-{numero}'

    digitos = re.sub(r'\D', '', referencia)
    if len(digitos) > 8:
        return f'{digitos[:-8].zfill(4)[-4:]}-{digitos[-8:].zfill(8)}'
    return f'0000-{digitos.zfill(8)}'


def _descuento_para_exportacion(valor) -> float:
    texto = str(valor or '').strip()
    if '%' in texto:
        texto = texto.replace('%', '').replace(' ', '').replace(',', '.')
        texto = re.sub(r'[^0-9.\-]', '', texto)
        descuento = float(texto or 0)
    else:
        descuento = resolver_descuento(valor)
    if -1 < descuento < 1 and descuento != 0:
        descuento *= 100
    descuento = abs(descuento)
    return int(descuento) if float(descuento).is_integer() else descuento


def _parsear_precio(valor) -> float:
    texto = str(valor or '').strip()
    texto = texto.replace('$', '').replace(' ', '')
    texto = re.sub(r'[^0-9,.\-]', '', texto)
    if ',' in texto:
        texto = texto.replace('.', '').replace(',', '.')
    return round(float(texto or 0), 2)


def process_taverniti_pedido_proveedor(input_path, output_path):
    """
    Procesa un .xlsx de Taverniti.
    Genera el CSV para CEGID y retorna el informe de auditoría.
    """
    try:
        try:
            sheets = pd.read_excel(input_path, sheet_name=None, dtype={'Ean': str, 'EAN': str})
        except ImportError as e:
            if str(input_path).lower().endswith('.xls') and 'xlrd' in str(e).lower():
                raise RuntimeError(
                    "No se pudo leer el archivo .xls porque falta instalar xlrd en el servidor. "
                    "Instalá las dependencias actualizadas y volvé a procesarlo."
                ) from e
            raise
        frames = [df for df in sheets.values() if not df.empty]
        if not frames:
            raise RuntimeError("El archivo no contiene datos válidos.")

        data = pd.concat(frames, ignore_index=True)
        data.columns = data.columns.astype(str).str.strip()
        data = _normalizar_columnas(data)
        _validar_columnas(data)

        conflictos_suc = detectar_conflictos_suc(data, _COLUMNAS_REPORTE)
        ean_vacios = detectar_ean_vacios(data, _COLUMNAS_REPORTE)

        registros_cegid = []
        items_auditoria = []

        for i, row in data.iterrows():
            try:
                fecha_str = pd.to_datetime(row['Fecha'], dayfirst=True).strftime('%d%m%y')
                referencia = _referencia_desde_remito(row['Remito'])
                codigo_barras = str(row['EAN']).strip()
                cantidad = int(float(str(row['Cantidad']).replace(',', '.')))
                precio_float = _parsear_precio(row['PreUni'])
                establecimiento = resolver_establecimiento(row.get('Empresa', ''))
                almacen = str(int(row['Suc'])).zfill(6)
                descuento = _descuento_para_exportacion(row.get('Dto.Com'))

                articulo = str(row.get('Articulo', '')).strip() or codigo_barras.split('.', 1)[0]
                talle = str(row.get('Talle', '')).strip()
                descripcion_raw = str(row.get('Descripcion', '')).strip()
                color = str(row.get('ColorNom', '')).strip()

                registros_cegid.append({
                    'CAB': 'ZCOC1_',
                    'REFERENCIA INTERNA': referencia,
                    'FECHA': fecha_str,
                    'COD PROVEEDOR': 'FUTUR',
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
                        'Descripción': descripcion_raw,
                        'Color': color,
                        'Precio': precio_float,
                    },
                ))

            except Exception as e:
                print(f"Error en fila {i}: {e}")
                continue

        if not registros_cegid:
            return None

        return ejecutar_auditoria_y_exportar(
            items_auditoria, registros_cegid, output_path,
            proveedor='TAVERNITI', conflictos_suc=conflictos_suc,
            ean_vacios=ean_vacios,
            sort_by=None,
        )

    except Exception as e:
        raise RuntimeError(f"Error crítico en procesador TAVERNITI: {e}")
