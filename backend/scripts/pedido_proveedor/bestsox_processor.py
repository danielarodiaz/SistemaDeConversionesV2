import pandas as pd
import re
from datetime import datetime
from backend.utils.pedido_helpers import (
    detectar_conflictos_suc, formatear_precio, resolver_establecimiento,
    armar_item_auditoria, ejecutar_auditoria_y_exportar, detectar_ean_vacios,
    detectar_campos_requeridos_vacios,
)
from backend.utils.cegid_utils import obtener_codigo_barra

_COLUMNAS_REPORTE = [
    'Fecha', 'Suc', 'EAN', 'Articulo', 'Talle',
    'ColorNom', 'Remito', 'Nombre', 'Cantidad', 'PreUni',
]


def _parsear_almacen(suc_raw: str):
    """Convierte el valor de Suc en el código de almacén CEGID (6 dígitos)."""
    if suc_raw.upper() == 'DEPOSITO':
        return '240001'
    match = re.match(r'^\d{5,6}', suc_raw)
    if match:
        almacen = match.group(0)
        return almacen if len(almacen) == 6 else f'0{almacen}'
    return None


def _valor_alerta(valor):
    if pd.isna(valor):
        return ''
    if isinstance(valor, pd.Timestamp):
        return valor.strftime('%d/%m/%Y')
    return valor.item() if hasattr(valor, 'item') else valor


def _codigo_barra_valido(codigo_barras: str) -> bool:
    codigo = str(codigo_barras or '').strip()
    return (
        (len(codigo) in (12, 13) and codigo.isdigit())
        or bool(re.fullmatch(r'T[A-Za-z0-9]+', codigo))
    )


def _fila_alerta_codigo_barra_no_encontrado(row, fila_idx, codigo_articulo, talle):
    return {
        'Fila': int(fila_idx) + 2 if isinstance(fila_idx, int) else str(fila_idx),
        'Fecha': _valor_alerta(row.get('Fecha', '')),
        'Suc': _valor_alerta(row.get('Suc', '')),
        'Articulo': _valor_alerta(row.get('Articulo', '')),
        'Articulo buscado': codigo_articulo,
        'Talle': talle,
        'Descripcion': _valor_alerta(row.get('Descripcion', '')),
        'Remito': _valor_alerta(row.get('Remito', '')),
        'Nombre': _valor_alerta(row.get('Nombre', '')),
        'Motivo': 'EAN vacío y código de barras no encontrado en CEGID por artículo + talle',
    }


def _deduplicar_alertas_por_articulo(alertas):
    agrupadas = {}
    for alerta in alertas:
        articulo = str(alerta.get('Articulo buscado', '')).strip()
        if not articulo:
            continue
        if articulo not in agrupadas:
            agrupadas[articulo] = dict(alerta)
            agrupadas[articulo]['Talles'] = set()
            agrupadas[articulo]['Remitos'] = set()
        if alerta.get('Talle'):
            agrupadas[articulo]['Talles'].add(str(alerta['Talle']))
        if alerta.get('Remito'):
            agrupadas[articulo]['Remitos'].add(str(alerta['Remito']))

    resultado = []
    for alerta in agrupadas.values():
        talles = sorted(alerta.pop('Talles'))
        remitos = sorted(alerta.pop('Remitos'))
        alerta['Talles'] = ', '.join(talles)
        alerta['Remitos'] = ', '.join(remitos)
        resultado.append(alerta)
    return resultado


def _deduplicar_codigos_completados(codigos):
    vistos = set()
    unicos = []
    for item in codigos:
        clave = (
            str(item.get('Articulo buscado', '')).strip(),
            str(item.get('Talle', '')).strip(),
            str(item.get('Codigo_EAN', '')).strip(),
        )
        if clave in vistos:
            continue
        vistos.add(clave)
        unicos.append(item)
    return unicos


def process_bestsox_pedido_proveedor(input_path, output_path):
    """
    Procesa un .xlsx de BestSox (puede tener múltiples hojas).
    Genera el CSV para CEGID y retorna el informe de auditoría.
    """
    try:
        sheets = pd.read_excel(input_path, sheet_name=None)
        frames = list(sheets.values())
        data_all = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()

        conflictos_suc = detectar_conflictos_suc(data_all, _COLUMNAS_REPORTE)
        ean_vacios = detectar_ean_vacios(data_all, _COLUMNAS_REPORTE)
        campos_requeridos_vacios = detectar_campos_requeridos_vacios(
            data_all,
            ["Fecha", "EAN"],
            _COLUMNAS_REPORTE,
        )

        registros_cegid = []
        items_auditoria = []
        codigos_barras_no_encontrados = []
        codigos_barras_completados = []
        prev_fecha_str = prev_suc = prev_referencia = None
        fecha_exportacion = datetime.now().strftime('%d%m%y')
        fechas_completadas = 0
        eans_completados = 0

        for idx, row in data_all.iterrows():
            try:
                # ── Fecha ─────────────────────────────────────────────────────
                fecha = row['Fecha']
                fecha_str = None
                if not pd.isna(fecha):
                    if isinstance(fecha, (str, int, float)):
                        try:
                            fecha = pd.to_datetime(fecha, dayfirst=True, errors='raise')
                        except Exception:
                            fecha = None
                    if isinstance(fecha, pd.Timestamp):
                        fecha_str = fecha.strftime('%d%m%y')

                if not fecha_str:
                    fecha_str = fecha_exportacion
                    fechas_completadas += 1

                # ── Referencia ────────────────────────────────────────────────
                referencia = str(row['Remito']).strip()
                if not (referencia.startswith('R') and len(referencia) == 13):
                    print(f"Referencia inválida: {referencia}")
                    continue

                # ── Código de barras ──────────────────────────────────────────
                codigo_articulo = re.sub(r'[/\-]', '', str(row.get('Articulo', '')).strip())
                talle = str(row.get('Talle', '')).strip()
                ean_val = row.get('EAN')
                codigo_buscado_en_cegid = False
                if pd.isna(ean_val):
                    codigo_barras = ''
                elif isinstance(ean_val, float):
                    ean_val = int(ean_val)
                    codigo_barras = str(ean_val).strip()
                else:
                    codigo_barras = str(ean_val).strip()
                if not codigo_barras or codigo_barras.lower() in ('nan', 'none', 'null'):
                    codigo_buscado_en_cegid = True
                    codigo_barras = str(obtener_codigo_barra(codigo_articulo, talle) or '').strip()
                    if not codigo_barras:
                        codigos_barras_no_encontrados.append(
                            _fila_alerta_codigo_barra_no_encontrado(row, idx, codigo_articulo, talle)
                        )
                        descripcion = str(row.get('Descripcion', '')).strip().upper()
                        color = str(row.get('ColorNom', '')).strip()
                        precio_float = round(float(row.get('PreUni') or 0), 2)
                        items_auditoria.append(armar_item_auditoria(
                            barras=f'FALTA_{codigo_articulo}_{talle}',
                            articulo=codigo_articulo,
                            precio_float=precio_float,
                            detalles={
                                'Material': codigo_articulo,
                                'Descripción': descripcion,
                                'ColorNom': color,
                                'Size': talle,
                                'Codigo_EAN': '',
                                'Precio': precio_float,
                            },
                        ))
                    else:
                        eans_completados += 1
                        codigos_barras_completados.append({
                            'Articulo': _valor_alerta(row.get('Articulo', '')),
                            'Articulo buscado': codigo_articulo,
                            'Talle': talle,
                            'Descripcion': _valor_alerta(row.get('Descripcion', '')),
                            'Codigo_EAN': codigo_barras,
                        })

                if not _codigo_barra_valido(codigo_barras):
                    if not codigo_buscado_en_cegid:
                        print(f"Código de barras inválido: {codigo_barras}")
                    continue

                # ── Almacén ───────────────────────────────────────────────────
                almacen = _parsear_almacen(str(row['Suc']).strip())
                if almacen is None:
                    print(f"Almacén inválido: {row['Suc']}")
                    continue

                # ── Cantidad / Precio ─────────────────────────────────────────
                cantidad = row['Cantidad']
                if not isinstance(cantidad, (int, float)):
                    continue
                precio_float = round(float(row['PreUni']), 2)

                # ── Datos del artículo ────────────────────────────────────────
                establecimiento = resolver_establecimiento(row.get('Nombre', ''))
                color = str(row.get('ColorNom', '')).strip()
                descripcion = str(row.get('Descripcion', '')).strip().upper()

                registros_cegid.append({
                    'CAB': 'ZCOC1_',
                    'REFERENCIA INTERNA': referencia,
                    'FECHA': fecha_str,
                    'COD PROVEEDOR': 'BESTS',
                    'CODIGO BARRAS': codigo_barras,
                    'CANTIDAD': int(cantidad),
                    'PRECIO': formatear_precio(precio_float),
                    'ALMACEN': almacen,
                    'ESTABLECIMIENTO': establecimiento,
                    'DESCUENTO': 14,
                })
                items_auditoria.append(armar_item_auditoria(
                    barras=codigo_barras,
                    articulo=codigo_articulo,
                    precio_float=precio_float,
                    detalles={
                        'Material': codigo_articulo,
                        'Descripción': descripcion,
                        'ColorNom': color,
                        'Size': talle,
                        'Codigo_EAN': codigo_barras,
                        'Precio': precio_float,
                    },
                ))

                prev_fecha_str, prev_suc, prev_referencia = fecha_str, almacen, referencia

            except Exception as e:
                print(f"Error procesando fila: {e}")
                continue

        if not registros_cegid and not items_auditoria:
            return None

        informe = ejecutar_auditoria_y_exportar(
            items_auditoria, registros_cegid, output_path,
            proveedor='BestSox',
            conflictos_suc=conflictos_suc,
            ean_vacios=ean_vacios,
            campos_requeridos_vacios=campos_requeridos_vacios,
            codigos_barras_no_encontrados=codigos_barras_no_encontrados,
            codigos_barras_completados=codigos_barras_completados,
        )

        articulos_a_crear = {
            str(item.get('Material', '')).strip()
            for item in informe.get('faltantes', [])
            if item.get('Material')
        }
        codigos_barras_no_encontrados = [
            alerta
            for alerta in codigos_barras_no_encontrados
            if str(alerta.get('Articulo buscado', '')).strip() not in articulos_a_crear
        ]
        informe['codigos_barras_no_encontrados'] = _deduplicar_alertas_por_articulo(codigos_barras_no_encontrados)
        informe['codigos_barras_completados'] = _deduplicar_codigos_completados(codigos_barras_completados)

        acciones = []
        if fechas_completadas:
            acciones.append('Fecha con la fecha de importación')
        if eans_completados:
            acciones.append('EAN con el código de barras de CEGID')
        if acciones:
            informe.setdefault('avisos_generales', []).append(
                f"Se completaron campos vacíos automáticamente: {', '.join(acciones)}."
            )
        return informe

    except Exception as e:
        raise RuntimeError(f"Error al procesar el archivo BestSox: {e}")
