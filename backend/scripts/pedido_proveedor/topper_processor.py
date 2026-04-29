import csv
import re
from backend.services.validator import CegidValidator
from backend.utils.pedido_helpers import armar_item_auditoria


def _extraer_articulo(articulo_raw: str) -> str:
    """
    Limpia el código de artículo Topper: quita letras iniciales y ceros a la izquierda.
    Ej: 'D050300' → '50300'
    """
    sin_letras = re.sub(r'^[a-zA-Z]+', '', articulo_raw)
    return sin_letras.lstrip('0')


def process_topper_pedido_proveedor(txt_file_path, csv_file_path):
    """
    Procesa un .txt de ancho fijo de Topper.
    Genera el CSV para CEGID y retorna el informe de auditoría.
    """
    items_para_auditar = []
    datos_procesados = []

    with open(txt_file_path, 'r', encoding='utf-8') as f:
        referencia_actual = fecha_actual = establecimiento_actual = ''

        for line in f:
            # ── Referencia ────────────────────────────────────────────────
            ref_match = re.search(r'\b\d{4}A\d{8}\b', line)
            if ref_match:
                referencia_actual = ref_match.group(0).replace('A', '-')

            # ── Fecha ─────────────────────────────────────────────────────
            fecha_match = re.search(r'\b\d{4}-\d{2}-\d{2}\b', line[35:45])
            if fecha_match:
                f = fecha_match.group(0)
                fecha_actual = f'{f[8:10]}{f[5:7]}{f[2:4]}'

            # ── Establecimiento ───────────────────────────────────────────
            establecimiento_raw = line[191:198].strip()
            if establecimiento_raw == '1279300':
                establecimiento_actual = '002'
            elif establecimiento_raw == '1279084':
                establecimiento_actual = '001'

            # ── Línea de artículo ─────────────────────────────────────────
            codigo_barras = line[74:88].strip()
            if not codigo_barras.isdigit():
                continue

            cantidad_raw = line[31:37].strip()
            cantidad = cantidad_raw.split(',')[0]
            if int(cantidad) == 0:
                continue

            precio = line[44:53].strip().replace(',', '.')
            articulo_limpio = _extraer_articulo(line[0:8].strip())
            talle = line[21:26].strip()

            datos_procesados.append([
                'ZCOC1_', referencia_actual, fecha_actual, 'ALSAI',
                codigo_barras, cantidad, precio, '240001',
                establecimiento_actual, 12,
            ])
            items_para_auditar.append(armar_item_auditoria(
                barras=codigo_barras,
                articulo=articulo_limpio,
                precio_float=precio,
                detalles={
                    'Material': articulo_limpio,
                    'Size': talle,
                    'Codigo_EAN': codigo_barras,
                    'Precio': precio,
                },
            ))

    informe_auditoria = CegidValidator.auditar_items(items_para_auditar)

    with open(csv_file_path, mode='w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f, delimiter='|')
        writer.writerow([
            'CAB', 'REFERENCIA INTERNA', 'FECHA', 'COD PROVEEDOR',
            'CODIGO BARRAS', 'CANTIDAD', 'PRECIO', 'ALMACEN',
            'ESTABLECIMIENTO', 'DESCUENTO',
        ])
        writer.writerows(datos_procesados)

    return informe_auditoria