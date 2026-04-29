import pandas as pd
import os
from datetime import datetime
from config import ENVIAR_A_FTP
from services.upload_ftp import upload_to_ftp
from data.prov_database import cuit_proveedores
from utils.cegid_utils import obtener_precios_cegid_por_cod_prov

def buscar_cod_prov(marca_objetivo, pivot_objetivo):
    for cuit, datos in cuit_proveedores.items():
        if datos['marca'] == marca_objetivo and datos['pivot'] == pivot_objetivo:
            return datos['cod_prov']
    return None

def process_puma_price(input_path):
    try:
        # Paso 1: Buscar cod_prov de PUMA con pivot = "PUMA ARG"
        cod_prov = buscar_cod_prov("PUMA", "PUMA ARG")
        if not cod_prov:
            raise ValueError("No se encontró cod_prov para PUMA / PUMA ARG en prov_database")

        # Paso 2: Obtener todos los precios actuales desde CEGID
        precios_cegid = obtener_precios_cegid_por_cod_prov(cod_prov)
        if precios_cegid.empty:
            raise ValueError("No se obtuvieron precios desde CEGID para el proveedor especificado.")

        # Paso 3: Leer la lista del proveedor
        df = pd.read_excel(input_path, skiprows=7, dtype=str)
        df = df[['ART/VTE', 'WHP (Whls Price)', 'SRP (Suggested Retail Price)']]
        # Limpiar espacios en el código del artículo
        df['ART/VTE'] = df['ART/VTE'].str.replace(' ', '')

        # Preparar listas
        compra_data, venta_data, informe_data, no_encontrados = [], [], [], []

        for _, row in df.iterrows():
            try:
                codigo_art = row['ART/VTE']
                precio_lista_compra = float(row['WHP (Whls Price)'].replace(',', '.'))
                precio_lista_venta = float(row['SRP (Suggested Retail Price)'].replace(',', '.'))

                # Buscar en precios_cegid usando CodigoArticulo
                match = precios_cegid[precios_cegid['CodigoArticulo'] == codigo_art]
                if match.empty:
                    no_encontrados.append(codigo_art)
                    continue

                precio_costo = float(match['PrecioCompra'].values[0])
                precio_venta = float(match['PrecioVenta'].values[0])
                nombre_articulo = match['NombreArticulo'].values[0]

                # Calcular variaciones
                var_c = round((precio_lista_compra / precio_costo), 2) if precio_costo else 'N/A'
                var_v = round((precio_lista_venta / precio_venta), 2) if precio_venta else 'N/A'

                informe_data.append({
                    'Codigo articulo': codigo_art,
                    'Nombre articulo': nombre_articulo,
                    'Precio C CEGID': precio_costo,
                    'NUEVO C': precio_lista_compra,
                    'VAR C': var_c,
                    'Precio V CEGID': precio_venta,
                    'NUEVO V': precio_lista_venta,
                    'VAR V': var_v
                })

                compra_data.append({
                    'CABECERA': 'LCOC1_',
                    'PERIODO': 'PERMA',
                    'TIPO': 'LCMAR',
                    'PRECIO': precio_lista_compra,
                    'COD ART': codigo_art
                })
                def redondear_a_999(valor):
                    try:
                        entero = round(float(valor))
                        return float(f"{entero}.999")
                    except:
                        return valor  # por si viene mal el valor

                venta_data.append({
                    'CABECRRA': 'LPMC1_',
                    'CODIGO ARTICULO': codigo_art,
                    'PREC_O': redondear_a_999(precio_lista_venta)
                })

            except Exception as e:
                print(f'Error procesando el artículo {row["ART/VTE"]}: {e}')

        # Crear DataFrames
        compra_df = pd.DataFrame(compra_data)
        venta_df = pd.DataFrame(venta_data)
        informe_df = pd.DataFrame(informe_data)

        print(f'Procesamiento completado:')
        print(f'- Artículos procesados: {len(informe_data)}')
        print(f'- Artículos no encontrados: {len(no_encontrados)}')

        return informe_df, compra_df, venta_df

    except Exception as e:
        print(f'Error en el procesamiento: {e}')
        raise  # Re-lanzar la excepción para que Flask la maneje
