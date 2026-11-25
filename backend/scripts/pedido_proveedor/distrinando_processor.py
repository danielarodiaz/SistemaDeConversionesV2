import pandas as pd
import os
import gc
import re

if os.getenv("RENDER") == "1":
    from utils.cegid_utils import obtener_codigo_barra_por_talle_mock as obtener_codigo_barra_flexible
else:
    from utils.cegid_utils import obtener_codigo_barra_flexible

from data_service import obtener_talle_db, obtener_lista_talles_por_sistema


def limpiar_columnas(data):
    data.rename(columns=lambda x: " ".join(x.strip().split()), inplace=True)

def normalizar_nombres_columnas(df):
    equivalencias = {
        'NRO REMITO': ['Nro Remito', 'Remito nro', 'Nº Remito', 'Número de remito', 'Remito', 'Número de Remito', "N° Remito"],
        'Sucursal': ['sucursal', 'suucrsal']
    }

    columnas_actuales = list(df.columns)

    for nombre_estandar, variantes in equivalencias.items():
        for variante in variantes:
            for col in columnas_actuales:
                if col.strip().lower() == variante.strip().lower():
                    df.rename(columns={col: nombre_estandar}, inplace=True)
                    break


def procesar_crocs_casm_cat(data):
    transformed_data = []
    descuento_porcentaje = 15  # 15% de descuento informado

    for _, row in data.iterrows():
        try:
            # Conversión robusta de fecha
            valor_fecha = row['Fecha de contabilización']
            if pd.isna(valor_fecha):
                continue
            if isinstance(valor_fecha, pd.Timestamp):
                fecha = valor_fecha.strftime("%d%m%y")
            else:
                try:
                    fecha = pd.to_datetime(valor_fecha, format="%d/%m/%Y").strftime("%d%m%y")
                except Exception:
                    fecha = pd.to_datetime(valor_fecha).strftime("%d%m%y")

            referencia = str(row['NRO REMITO']).strip()
            if not referencia:
                continue

            codigo_barras = str(row['EAN/GTIN']).strip()
            if not codigo_barras or len(codigo_barras) < 12:
                continue

            cantidad = int(row['Cant en UM Inventario'])

            precio_base = float(row['Precio tras el descuento'])
            precio_final = round(precio_base / (1 - (descuento_porcentaje/100)), 2)
            precio_final = str(precio_final).replace('.', ',')

            almacen = str(row['Sucursal']).strip()
            if len(almacen) == 5:
                almacen = f"0{almacen}"
            elif len(almacen) > 6:
                almacen = almacen[:6]

            nombre_cliente = str(row['Nombre de cliente/proveedor']).replace('.', '').upper()
            establecimiento = '002' if 'MARATHON SRL' in nombre_cliente else '001'

            transformed_row = {
                "CAB": "ZCOC1_",
                "REFERENCIA INTERNA": referencia,
                "FECHA": fecha,
                "COD PROVEEDOR": "DISTR",
                "CODIGO BARRAS": codigo_barras,
                "CANTIDAD": cantidad,
                "PRECIO": precio_final,
                "ALMACEN": almacen,
                "ESTABLECIMIENTO": establecimiento,
                "DESCUENTO": descuento_porcentaje
            }
            transformed_data.append(transformed_row)
        except Exception as e:
            print(f"⚠️ Error procesando fila CROCS/CASM: {e}")
            continue

    return transformed_data, []

def procesar_reebok_kappa(data):
    """Procesa los datos de REEBOK y KAPPA (sin CASM)."""
    transformed_data = []
    articulos_no_encontrados = []

    for _, row in data.iterrows():
        try:
            # Obtener MODELO y COLOR
            modelo = str(row['MODELO']).strip()
            color = str(row['COLOR']).strip()
            numero_articulo = str(row['Número de artículo']).strip()

            # Si el número de artículo ya viene con el talle (ejemplo: K5321J4QW-K005-32), usar EAN/GTIN directamente
            # Normalización opcional por si vienen comas:
            numero_articulo = numero_articulo.replace(',', '.')
            
            if re.match(r'^.+-.+-(?:\d{1,2}(?:\.5)?|[A-Za-z]+)$|^.+-(\d{1,2}(?:\.5)?)$', numero_articulo):
                valor_fecha = row['Fecha de contabilización']
                if pd.isna(valor_fecha):
                    continue
                if isinstance(valor_fecha, pd.Timestamp):
                    fecha = valor_fecha.strftime("%d%m%y")
                else:
                    try:
                        fecha = pd.to_datetime(valor_fecha, format="%d/%m/%Y").strftime("%d%m%y")
                    except Exception:
                        fecha = pd.to_datetime(valor_fecha).strftime("%d%m%y")
                referencia = str(row['NRO REMITO']).strip()
                if not referencia:
                    continue
                cantidad_unidades = int(row['Cant en UM Inventario'])
                total_lineas = float(row['Total líneas'])
                total_pares = int(row['Total Pares'])
                precio_unitario_base = total_lineas / total_pares
                marca = str(row['Marca']).upper()
                if "REEBOK" in marca:
                    porcentaje_divisor = 0.87
                    descuento = 13
                else:  # KAPPA
                    porcentaje_divisor = 0.85
                    descuento = 15
                precio_final = round(precio_unitario_base / porcentaje_divisor, 2)
                precio_final = str(precio_final).replace('.', ',')
                almacen = str(row['Sucursal']).strip()
                if len(almacen) == 5:
                    almacen = f"0{almacen}"
                elif len(almacen) > 6:
                    almacen = almacen[:6]
                nombre_cliente = str(row['Nombre de cliente/proveedor']).replace('.', '').upper()
                establecimiento = '002' if 'MARATHON SRL' in nombre_cliente else '001'
                codigo_barras = str(row['EAN/GTIN']).strip()
                if not codigo_barras or len(codigo_barras) < 12:
                    articulo_info = f"{numero_articulo} (EAN/GTIN faltante o inválido)"
                    articulos_no_encontrados.append(articulo_info)
                    print(f"⚠️ Código de barra no encontrado en Excel para {numero_articulo}")
                    continue
                transformed_row = {
                    "CAB": "ZCOC1_",
                    "REFERENCIA INTERNA": referencia,
                    "FECHA": fecha,
                    "COD PROVEEDOR": "DISTR",
                    "CODIGO BARRAS": codigo_barras,
                    "CANTIDAD": cantidad_unidades,
                    "PRECIO": precio_final,
                    "ALMACEN": almacen,
                    "ESTABLECIMIENTO": establecimiento,
                    "DESCUENTO": descuento
                }
                transformed_data.append(transformed_row)
                continue

            # Buscar el rango y la curva, con o sin espacio
            match = re.search(r'(\d{2}/\d{2})\s*\((\d+)\)', numero_articulo)
            if not match:
                print(f"⚠️ Número de artículo inválido (no se encontró rango y curva): {numero_articulo}")
                continue

            rango_talles = match.group(1)  # '35/40'
            cantidades = match.group(2)    # '123321'

            rango_inicio, rango_fin = map(int, rango_talles.split('/'))

            if not cantidades.isdigit():
                print(f"⚠️ Cantidades inválidas en: {numero_articulo}")
                continue

            # Extraer valores
            valor_fecha = row['Fecha de contabilización']
            if pd.isna(valor_fecha):
                continue
            if isinstance(valor_fecha, pd.Timestamp):
                fecha = valor_fecha.strftime("%d%m%y")
            else:
                try:
                    fecha = pd.to_datetime(valor_fecha, format="%d/%m/%Y").strftime("%d%m%y")
                except Exception:
                    fecha = pd.to_datetime(valor_fecha).strftime("%d%m%y")

            referencia = str(row['NRO REMITO']).strip()
            if not referencia:
                continue

            cantidad_unidades = int(row['Cant en UM Inventario'])

            total_lineas = float(row['Total líneas'])
            total_pares = int(row['Total Pares'])

            precio_unitario_base = total_lineas / total_pares

            # Definir porcentaje descuento por marca
            marca = str(row['Marca']).upper()
            if "REEBOK" in marca:
                porcentaje_divisor = 0.87
                descuento = 13
            else:  # KAPPA
                porcentaje_divisor = 0.85
                descuento = 15

            precio_final = round(precio_unitario_base / porcentaje_divisor, 2)
            precio_final = str(precio_final).replace('.', ',')

            almacen = str(row['Sucursal']).strip()
            if len(almacen) == 5:
                almacen = f"0{almacen}"
            elif len(almacen) > 6:
                almacen = almacen[:6]

            nombre_cliente = str(row['Nombre de cliente/proveedor']).replace('.', '').upper()
            establecimiento = '002' if 'MARATHON SRL' in nombre_cliente else '001'

            for idx, talle in enumerate(range(rango_inicio, rango_fin + 1)):
                multiplicador = int(str(cantidades)[idx])
                cantidad_total = cantidad_unidades * multiplicador

                codigo_barra = obtener_codigo_barra_flexible(modelo, talle, incluir_color=True, color=color)

                if not codigo_barra:
                    # Intentar con modelo+color pegados (sin guion)
                    modelo_color_pegado = f"{modelo.replace('-', '')}{color}"
                    print(f"Buscando código de barra para modelo+color pegados: '{modelo_color_pegado}', talle: {talle}")
                    codigo_barra = obtener_codigo_barra_flexible(modelo_color_pegado, talle, incluir_color=False)
                    if not codigo_barra:
                        articulo_info = f"{modelo}-{color} (talle {talle})"
                        articulos_no_encontrados.append(articulo_info)
                        print(f"⚠️ Código de barra no encontrado para {modelo}-{color} ni para {modelo_color_pegado} (talle {talle})")
                        continue

                transformed_row = {
                    "CAB": "ZCOC1_",
                    "REFERENCIA INTERNA": referencia,
                    "FECHA": fecha,
                    "COD PROVEEDOR": "DISTR",
                    "CODIGO BARRAS": codigo_barra,
                    "CANTIDAD": cantidad_total,
                    "PRECIO": precio_final,
                    "ALMACEN": almacen,
                    "ESTABLECIMIENTO": establecimiento,
                    "DESCUENTO": descuento
                }
                transformed_data.append(transformed_row)

        except Exception as e:
            print(f"⚠️ Error procesando fila REEBOK/KAPPA: {e}")
            continue

    return transformed_data, articulos_no_encontrados


def obtener_talles_en_rango_crocs(talle_inicio_codigo, talle_fin_codigo):
    """
    Obtiene la lista de códigos de talles de Crocs en un rango dado.
    
    Args:
        talle_inicio_codigo: Código de talle inicial (ej: 'C4/5', 'M8/W10')
        talle_fin_codigo: Código de talle final (ej: 'C10/11', 'M12')
    
    Returns:
        list: Lista de códigos de talles en el rango, ordenados por talle numérico
    """
    talle_inicio_num = obtener_talle_db('CROCS', talle_inicio_codigo)
    talle_fin_num = obtener_talle_db('CROCS', talle_fin_codigo)
    
    if talle_inicio_num is None or talle_fin_num is None:
        return []
    
    lista_talles_crocs = obtener_lista_talles_por_sistema('CROCS')
    talles_en_rango = []
    
    for talle_obj in lista_talles_crocs:
            # talle_obj tendría atributos: talle_origen y talle_destino
            if talle_inicio_num <= talle_obj.talle_destino <= talle_fin_num:
                talles_en_rango.append(talle_obj.talle_origen)
    
    # Ordenar por talle numérico
    talles_en_rango.sort(key=lambda x: obtener_talle_db('CROCS', x))
    
    return talles_en_rango


def normalizar_codigo_talle_crocs(codigo_raw, es_inicio=True):
    """
    Normaliza un código de talle de Crocs al formato de la base de datos.
    
    Args:
        codigo_raw: Código crudo (ej: 'M8W10', 'C4', 'M12')
        es_inicio: True si es el inicio del rango, False si es el fin
    
    Returns:
        str: Código normalizado o None
    """
    codigo_raw = codigo_raw.upper().strip()
    
    # Si ya está en formato correcto, retornarlo
    if codigo_raw in TALLES_CROCS:
        return codigo_raw
    
    # Convertir M8W10 -> M8/W10
    match_w = re.match(r'M(\d+)W(\d+)', codigo_raw)
    if match_w:
        return f"M{match_w.group(1)}/W{match_w.group(2)}"
    
    # Para códigos C sin /, determinar el formato correcto
    match_c = re.match(r'C(\d+)', codigo_raw)
    if match_c:
        num = int(match_c.group(1))
        # C4 -> C4/5, C6 -> C6/7, C8 -> C8/9, C10 -> C10/11, C12 -> C12/13
        if num in [2, 4, 6, 8, 10, 12]:
            return f"C{num}/{num+1}"
    
    # Para códigos M sin W, convertir a formato M/W
    match_m = re.match(r'M(\d+)$', codigo_raw)
    if match_m:
        num = int(match_m.group(1))
        # M11, M12, M13 existen directamente
        if num in [11, 12, 13]:
            return codigo_raw
        # M4, M5, M6, M7, M8, M9, M10 se convierten a M/W
        # M4 -> M4/W6, M5 -> M5/W7, M6 -> M6/W8, M7 -> M7/W9, M8 -> M8/W10, M9 -> M9/W11, M10 -> M10/W12
        if num in [4, 5, 6, 7, 8, 9, 10]:
            w_num = num + 2  # M4 -> W6, M5 -> W7, etc.
            return f"M{num}/W{w_num}"
    
    # Para códigos W sin M, convertir a formato M/W
    match_w_solo = re.match(r'W(\d+)$', codigo_raw)
    if match_w_solo:
        w_num = int(match_w_solo.group(1))
        # W5 -> M3/W5, W6 -> M4/W6, W7 -> M5/W7, W8 -> M6/W8, W9 -> M7/W9, W10 -> M8/W10, W11 -> M9/W11, W12 -> M10/W12
        if w_num in [5, 6, 7, 8, 9, 10, 11, 12]:
            m_num = w_num - 2  # W5 -> M3, W6 -> M4, etc.
            return f"M{m_num}/W{w_num}"
    
    # Intentar buscar directamente
    if codigo_raw in TALLES_CROCS:
        return codigo_raw
    
    return None


def parsear_curva_crocs(numero_articulo):
    """
    Parsea el formato de curva de Crocs del número de artículo.
    
    Ejemplos:
    - "M12 M8W10/M12 (23322)" → ('M8/W10', 'M12', '23322')
    - "M12 M4W6/M8W10 (23331)" → ('M4/W6', 'M8/W10', '23331')
    - "M12I C4/C10 (2244)" → ('C4/5', 'C10/11', '2244')
    - "M12 C12/J3 (3333)" → ('C12/13', 'J3', '3333')
    
    Returns:
        tuple: (talle_inicio, talle_fin, cantidades) o None si no se encuentra
    """
    # Patrón para extraer la curva: puede estar en formato M8W10/M12 o C4/C10 o C12/J3 o W5/W9 o M4/M8
    # Buscar patrón: algo como "M8W10/M12" o "C4/C10" o "C12/J3" o "W5/W9" o "M4/M8" seguido de (números)
    match = re.search(r'([CMJ]\d+W\d+|[CMJ]\d+(?:/\d+)?|W\d+)\s*/\s*([CMJ]\d+W\d+|[CMJ]\d+(?:/\d+)?|W\d+)\s*\((\d+)\)', numero_articulo, re.IGNORECASE)
    
    if not match:
        return None
    
    talle_inicio_raw = match.group(1).upper()  # 'M8W10' o 'C4' o 'C12'
    talle_fin_raw = match.group(2).upper()      # 'M12' o 'C10' o 'J3'
    cantidades = match.group(3)                 # '23322'
    
    # Normalizar formatos: M8W10 -> M8/W10, C4 -> C4/5 (si es inicio de rango C)
    talle_inicio = normalizar_codigo_talle_crocs(talle_inicio_raw, es_inicio=True)
    talle_fin = normalizar_codigo_talle_crocs(talle_fin_raw, es_inicio=False)
    
    if not talle_inicio or not talle_fin:
        return None
    
    return (talle_inicio, talle_fin, cantidades)


def buscar_codigo_barra_crocs(modelo, color, talle_num):
    """
    Busca el código de barras en CEGID para Crocs con dos estrategias:
    1. MODELO-COLOR
    2. MODELO+COLOR sin guion y sin la C inicial del color
    
    Returns:
        str: Código de barras o None
    """
    # Estrategia 1: MODELO-COLOR
    codigo_barra = obtener_codigo_barra_flexible(modelo, talle_num, incluir_color=True, color=color)
    if codigo_barra:
        return codigo_barra
    
    # Estrategia 2: MODELO+COLOR sin guion y sin la C inicial del color
    color_sin_c = color[1:] if color.startswith('C') else color
    modelo_color_pegado = f"{modelo.replace('-', '')}{color_sin_c}"
    print(f"Buscando código de barra para modelo+color pegados (sin C): '{modelo_color_pegado}', talle: {talle_num}")
    codigo_barra = obtener_codigo_barra_flexible(modelo_color_pegado, talle_num, incluir_color=False)
    
    return codigo_barra


def procesar_crocs_con_curvas(data):
    """
    Procesa los datos de CROCS con lógica de curvas similar a REEBOK/KAPPA.
    Verifica la columna "Código de grupo de unidad de medida":
    - Si es "Pares" o "Unidades" → usa lógica simple (procesar_crocs_casm_cat)
    - Si no → usa lógica de curvas
    """
    transformed_data = []
    articulos_no_encontrados = []
    descuento_porcentaje = 15  # 15% de descuento informado

    for _, row in data.iterrows():
        try:
            # Verificar "Código de grupo de unidad de medida"
            codigo_grupo_um = str(row.get('Código de grupo de unidad de medida', '')).strip().upper()
            
            # Si es "Pares" o "Unidades", usar lógica simple
            if codigo_grupo_um in ['PARES', 'UNIDADES']:
                # Lógica simple similar a procesar_crocs_casm_cat
                valor_fecha = row['Fecha de contabilización']
                if pd.isna(valor_fecha):
                    continue
                if isinstance(valor_fecha, pd.Timestamp):
                    fecha = valor_fecha.strftime("%d%m%y")
                else:
                    try:
                        fecha = pd.to_datetime(valor_fecha, format="%d/%m/%Y").strftime("%d%m%y")
                    except Exception:
                        fecha = pd.to_datetime(valor_fecha).strftime("%d%m%y")

                referencia = str(row['NRO REMITO']).strip()
                if not referencia:
                    continue

                codigo_barras = str(row['EAN/GTIN']).strip()
                if not codigo_barras or len(codigo_barras) < 12:
                    continue

                cantidad = int(row['Cant en UM Inventario'])

                precio_base = float(row['Precio tras el descuento'])
                precio_final = round(precio_base / (1 - (descuento_porcentaje/100)), 2)
                precio_final = str(precio_final).replace('.', ',')

                almacen = str(row['Sucursal']).strip()
                if len(almacen) == 5:
                    almacen = f"0{almacen}"
                elif len(almacen) > 6:
                    almacen = almacen[:6]

                nombre_cliente = str(row['Nombre de cliente/proveedor']).replace('.', '').upper()
                establecimiento = '002' if 'MARATHON SRL' in nombre_cliente else '001'

                transformed_row = {
                    "CAB": "ZCOC1_",
                    "REFERENCIA INTERNA": referencia,
                    "FECHA": fecha,
                    "COD PROVEEDOR": "DISTR",
                    "CODIGO BARRAS": codigo_barras,
                    "CANTIDAD": cantidad,
                    "PRECIO": precio_final,
                    "ALMACEN": almacen,
                    "ESTABLECIMIENTO": establecimiento,
                    "DESCUENTO": descuento_porcentaje
                }
                transformed_data.append(transformed_row)
                continue
            
            # Lógica de curvas (similar a procesar_reebok_kappa)
            modelo = str(row['MODELO']).strip()
            color = str(row['COLOR']).strip()
            numero_articulo = str(row['Número de artículo']).strip()

            # Parsear la curva
            curva_parseada = parsear_curva_crocs(numero_articulo)
            if not curva_parseada:
                print(f"⚠️ No se pudo parsear la curva de Crocs en: {numero_articulo}")
                continue

            talle_inicio, talle_fin, cantidades = curva_parseada
            
            # Obtener talles en el rango
            talles_en_rango = obtener_talles_en_rango_crocs(talle_inicio, talle_fin)
            
            if len(talles_en_rango) != len(cantidades):
                print(f"⚠️ La cantidad de talles ({len(talles_en_rango)}) no coincide con la cantidad de dígitos ({len(cantidades)}) en: {numero_articulo}")
                continue

            # Extraer valores comunes
            valor_fecha = row['Fecha de contabilización']
            if pd.isna(valor_fecha):
                continue
            if isinstance(valor_fecha, pd.Timestamp):
                fecha = valor_fecha.strftime("%d%m%y")
            else:
                try:
                    fecha = pd.to_datetime(valor_fecha, format="%d/%m/%Y").strftime("%d%m%y")
                except Exception:
                    fecha = pd.to_datetime(valor_fecha).strftime("%d%m%y")

            referencia = str(row['NRO REMITO']).strip()
            if not referencia:
                continue

            cantidad_unidades = int(row['Cant en UM Inventario'])

            # Calcular precio igual que procesar_reebok_kappa
            total_lineas = float(row['Total líneas'])
            total_pares = int(row['Total Pares'])
            precio_unitario_base = total_lineas / total_pares
            
            # Crocs tiene 15% de descuento (igual que Kappa)
            porcentaje_divisor = 0.85
            precio_final = round(precio_unitario_base / porcentaje_divisor, 2)
            precio_final = str(precio_final).replace('.', ',')

            almacen = str(row['Sucursal']).strip()
            if len(almacen) == 5:
                almacen = f"0{almacen}"
            elif len(almacen) > 6:
                almacen = almacen[:6]

            nombre_cliente = str(row['Nombre de cliente/proveedor']).replace('.', '').upper()
            establecimiento = '002' if 'MARATHON SRL' in nombre_cliente else '001'

            # Procesar cada talle en la curva
            for idx, codigo_talle_crocs in enumerate(talles_en_rango):
                multiplicador = int(str(cantidades)[idx])
                cantidad_total = cantidad_unidades * multiplicador
                
                talle_num = obtener_talle_numerico_crocs(codigo_talle_crocs)
                if talle_num is None:
                    continue

                # Buscar código de barras con las dos estrategias
                codigo_barra = buscar_codigo_barra_crocs(modelo, color, talle_num)

                if not codigo_barra:
                    articulo_info = f"{modelo}-{color} (talle Crocs: {codigo_talle_crocs}, numérico: {talle_num})"
                    articulos_no_encontrados.append(articulo_info)
                    print(f"⚠️ Código de barra no encontrado para {modelo}-{color} (talle Crocs: {codigo_talle_crocs}, numérico: {talle_num})")
                    continue

                transformed_row = {
                    "CAB": "ZCOC1_",
                    "REFERENCIA INTERNA": referencia,
                    "FECHA": fecha,
                    "COD PROVEEDOR": "DISTR",
                    "CODIGO BARRAS": codigo_barra,
                    "CANTIDAD": cantidad_total,
                    "PRECIO": precio_final,
                    "ALMACEN": almacen,
                    "ESTABLECIMIENTO": establecimiento,
                    "DESCUENTO": descuento_porcentaje
                }
                transformed_data.append(transformed_row)

        except Exception as e:
            print(f"⚠️ Error procesando fila CROCS con curvas: {e}")
            continue

    return transformed_data, articulos_no_encontrados


def process_distrinando_pedido_proveedor(input_path, output_path):
    try:
        # Leer el archivo con control de memoria
        data = pd.read_excel(input_path, engine="openpyxl", dtype=str)

        print("Columnas del archivo:", data.columns.tolist())
        
        # 🔹 Primero limpiar y normalizar columnas
        limpiar_columnas(data)
        normalizar_nombres_columnas(data)
        
        print("Columnas después de normalizar:", list(data.columns))


        # Mantener solo las columnas necesarias
        columnas_necesarias = [
            'Marca', 'Model Description', 'NRO REMITO', 'Fecha de contabilización',
            'EAN/GTIN', 'Cant en UM Inventario', 'Precio tras el descuento',
            'Sucursal', 'Nombre de cliente/proveedor',
            'MODELO', 'COLOR', 'Número de artículo', 'Total líneas', 'Total Pares',
            'Código de grupo de unidad de medida'
        ]
        data = data[[col for col in columnas_necesarias if col in data.columns]].copy()

        gc.collect()  # Forzar liberación de memoria innecesaria

        if data.empty:
            raise RuntimeError("El archivo está vacío.")



        required_columns = [
            'Marca', 'Model Description', 'NRO REMITO', 'Fecha de contabilización',
            'EAN/GTIN', 'Cant en UM Inventario', 'Precio tras el descuento',
            'Sucursal', 'Nombre de cliente/proveedor'
        ]
        missing_columns = [col for col in required_columns if col not in data.columns]
        if missing_columns:
            raise RuntimeError(f"Faltan columnas críticas en el archivo: {missing_columns}")

        # Detectar qué función aplicar
        marca = str(data['Marca'].iloc[0]).upper()
        model_description = str(data['Model Description'].iloc[0]).upper()

        articulos_no_encontrados = []
        
        if marca == 'CROCS':
            # Verificar si tiene las columnas necesarias para procesamiento con curvas
            tiene_columnas_curvas = (
                'MODELO' in data.columns 
                and 'COLOR' in data.columns 
                and 'Número de artículo' in data.columns
                and 'Código de grupo de unidad de medida' in data.columns
            )
            
            if tiene_columnas_curvas:
                print("🟦 Procesando como CROCS con curvas")
                transformed_data, articulos_no_encontrados = procesar_crocs_con_curvas(data)
            else:
                print("🟢 Procesando como CROCS/CASM/CAT")
                transformed_data, _ = procesar_crocs_casm_cat(data)
        elif (
            ('KAPPA' in marca and 'SAN MARTIN DE TUCUMAN' in model_description)
            or ('KAPPA' in marca and 'TUCUMAN' in model_description)
        ):
            print("🟢 Procesando como CROCS/CASM/CAT")
            transformed_data, _ = procesar_crocs_casm_cat(data)
        elif marca == 'REEBOK' or 'KAPPA' in marca:
            print("🟠 Procesando como REEBOK/KAPPA")
            transformed_data, articulos_no_encontrados = procesar_reebok_kappa(data)
        else:
            raise RuntimeError(f"Marca desconocida: {marca}")

        # Liberar memoria del DataFrame original
        del data
        gc.collect()

        if transformed_data:
            transformed_df = pd.DataFrame(transformed_data)
            transformed_df.to_csv(output_path, index=False, sep="|", encoding="utf-8-sig")
            print(f"✅ Archivo generado correctamente en: {output_path}")
            
            # Mostrar artículos no encontrados en CEGID
            if articulos_no_encontrados:
                print("\n" + "="*80)
                print("⚠️ ADVERTENCIA: Se encontraron artículos que no están en la base de datos de CEGID")
                print("="*80)
                print(f"Total de artículos no encontrados: {len(articulos_no_encontrados)}")
                print("\nArtículos no encontrados:")
                for idx, articulo in enumerate(articulos_no_encontrados, 1):
                    print(f"  {idx}. {articulo}")
                print("="*80 + "\n")
                
                # Retornar diccionario con información para mostrar en UI
                return {
                    "articulos_no_encontrados": articulos_no_encontrados,
                    "total_articulos": len(transformed_data),
                    "total_no_encontrados": len(articulos_no_encontrados)
                }
        else:
            print("⚠️ No se generaron datos válidos para exportar.")

    except Exception as e:
        print(f"❌ Error al procesar el archivo: {e}")
        raise RuntimeError(f"Error al procesar el archivo: {e}")