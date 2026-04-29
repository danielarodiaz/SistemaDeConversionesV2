import pandas as pd
import os
import re
import math
from datetime import datetime
from utils.cegid_utils import obtener_codigo_barra

def detectar_tipo_producto(nombre_archivo):
    nombre = nombre_archivo.lower()
    if "ftw" in nombre:
        return "FTW"
    elif "acc" in nombre:
        return "ACC"
    elif "app" in nombre:
        return "APP"
    return None

def detectar_establecimiento(nombre_archivo):
    return "002" if re.search(r"marathon", nombre_archivo, re.IGNORECASE) else "001"

def generar_referencia_interna(tipo, hoja):
    match = re.search(r"(\d{4})\s*-\s*(Q\d)", hoja.upper())
    if not match:
        return "PUMA DESCONOCIDO"
    anio, quarter = match.groups()
    prefijo = {"FTW": "CAL", "ACC": "ACC", "APP": "IND"}.get(tipo, "PUMA")
    anio_2d = anio[-2:]
    return f"{prefijo} PUMA {quarter} {anio_2d}"

def calcular_fecha_entrega(hoja):
    match = re.search(r"(\d{4})\s*-\s*(Q\d)", hoja.upper())
    if not match:
        return ""
    anio, quarter = match.groups()
    mes = {"Q1": 1, "Q2": 4, "Q3": 7, "Q4": 10}.get(quarter, 1)
    dia = 2 if quarter == "Q1" else 1
    anio_2d = anio[-2:]
    return f"{dia:02d}{mes:02d}{anio_2d}"

def limpiar_codigo_articulo(valor):
    return str(valor).replace(" ", "").strip()

def formatear_talle(talle, curva_id=None, tipo_producto=None):
    talle = str(talle).strip().replace(",", ".")
    talle = talle.replace("½", ".5").replace(" ", "")
    
    # Para APP: extraer lo que está dentro del paréntesis
    # Para ACC con curva 2: también extraer lo que está dentro del paréntesis
    if tipo_producto == "APP" and "(" in talle and ")" in talle:
        talle = talle.split("(")[-1].replace(")", "")
    elif tipo_producto == "ACC" and curva_id == 2 and "(" in talle and ")" in talle:
        talle = talle.split("(")[-1].replace(")", "")
    
    if talle.endswith(".0"):
        talle = talle[:-2]
    talles_k = ["10", "10.5", "11", "11.5", "12", "12.5", "13", "13.5"]
    if curva_id == 2 and talle in talles_k and not talle.endswith("K"):
        talle = f"{talle}K"
    return talle

def process_puma_propuesta_compra(input_path, output_path):
    nombre_archivo = os.path.basename(input_path)
    tipo_producto = detectar_tipo_producto(nombre_archivo)
    establecimiento = detectar_establecimiento(nombre_archivo)
    fecha_doc = datetime.now().strftime("%d%m%y")

    todas_las_filas = []

    excel = pd.ExcelFile(input_path)
    for hoja in excel.sheet_names:
        try:
            df_full = pd.read_excel(excel, sheet_name=hoja, header=None)

            # Para ACC la cabecera comienza en la fila 7 (índice 6), para otros tipos en fila 8 (índice 7)
            header_row_index = 6 if tipo_producto == "ACC" else 7
            headers = df_full.iloc[header_row_index]
            df = df_full[header_row_index + 1:].copy()
            df.columns = headers

            col_total = next((i for i, col in enumerate(headers) if str(col).strip().lower() == "total"), None)
            col_talles = next((i for i, col in enumerate(headers) if str(col).strip().lower() == "talles"), None)
            if col_total is None or col_talles is None:
                print(f"❌ No se encontró columna 'Talles' o 'Total' en hoja '{hoja}'")
                continue

            total_col_name = headers[col_total]
            df[total_col_name] = df[total_col_name].astype(str).str.replace(",", ".").str.replace(r"[^\d.]", "", regex=True)
            df = df[df[total_col_name].astype(float) > 0]

            col_art_final = next(
                (col for col in df.columns if str(col).lower().replace(" ", "").replace(".", "") == "artfinal"),
                None
            )
            if not col_art_final:
                print(f"❌ No se encontró la columna Art. Final en hoja '{hoja}'")
                continue

            col_art_group = next(
                (col for col in df.columns if str(col).lower().replace(" ", "").replace(".", "") == "artgroup"),
                None
            )
            col_talle = next(
                (col for col in df.columns if str(col).lower().replace(" ", "").replace(".", "") == "talles"),
                None
            )

            referencia_base = generar_referencia_interna(tipo_producto, hoja)
            fecha_entrega = calcular_fecha_entrega(hoja)

            curva_block_start = 3
            curva_block_end = header_row_index + 1
            curva_block = df_full.iloc[curva_block_start:curva_block_end]

            filas_hoja = []

            for idx, row in df.iterrows():
                try:
                    cod_articulo = limpiar_codigo_articulo(row[col_art_final])

                    # Caso especial: pelotas (Art. Group = "Balls") -> usar columna "Talles" directamente,
                    # sin depender de curvas.
                    if col_art_group is not None:
                        try:
                            grupo_val = str(row[col_art_group]).strip().lower()
                        except Exception:
                            grupo_val = ""
                    else:
                        grupo_val = ""

                    if grupo_val == "balls":
                        if col_talle is None:
                            print(f"❌ No se encontró la columna 'Talles' para Art. Group = Balls en hoja '{hoja}'")
                            continue

                        # Tomar el valor de la columna Talles como talle
                        if pd.isna(row[col_talle]):
                            talle_balls = ""
                        else:
                            talle_balls = str(row[col_talle]).strip()

                        if not talle_balls or talle_balls.lower() == "nan":
                            print(f"❌ Talle vacío para pelota → Artículo: {cod_articulo}")
                            continue

                        # Particularidad: si el valor es 100, se busca como talle 1
                        if talle_balls == "100":
                            talle_balls = "1"

                        try:
                            precio = round(float(row["Fab"]), 2)
                        except Exception:
                            print(f"❌ Precio 'Fab' inválido para pelota → Artículo: {cod_articulo}")
                            continue

                        precio_str = str(precio).replace(".", ",")

                        try:
                            cantidad_total = int(float(row[total_col_name]))
                        except Exception:
                            print(f"❌ Cantidad 'Total' inválida para pelota → Artículo: {cod_articulo}")
                            continue

                        cod_barra = obtener_codigo_barra(cod_articulo, talle_balls)
                        if not cod_barra:
                            print(f"❌ Código de barras NO encontrado (pelota) → Artículo: {cod_articulo}, Talle: {talle_balls}")
                            continue

                        filas_hoja.append({
                            "CAB": "PDCC1_",
                            "REFERENCIA INTERNA": referencia_base,
                            "FECHA DOC": fecha_doc,
                            "COD PROVEEDOR": "UNISO",
                            "CODIGO BARRAS": cod_barra,
                            "CANTIDAD": cantidad_total,
                            "PRECIO": precio_str,
                            "ALMACEN": "240001",
                            "ESTABLECIMIENTO": establecimiento,
                            "FECHA ENTREGA": fecha_entrega
                        })
                        # Ya procesamos la fila como pelota, no seguimos con la lógica de curvas
                        continue

                    curva_id = None
                    curva_col_idx = None

                    if tipo_producto == "APP":
                        try:
                            col_curvas = df.columns.get_loc("Curvas")
                        except KeyError:
                            print(f"❌ No se encontró la columna 'Curvas' en hoja '{hoja}'")
                            continue

                        if col_curvas + 1 < len(df.columns):
                            try:
                                val = row.iloc[col_curvas + 1]
                                if not pd.isna(val) and str(val).strip() != "":
                                    posible_id = int(float(val))
                                    curva_id = posible_id
                                    curva_col_idx = col_curvas + 1
                            except Exception as e:
                                print(f"❌ Error al leer ID de curva en hoja '{hoja}', fila {idx}: {e}")
                                continue
                        else:
                            print(f"❌ No hay columna a la derecha de 'Curvas' para leer ID de curva en hoja '{hoja}', fila {idx}'")
                            continue
                    else:
                        # Para FTW y otros tipos, se busca a la derecha de 'Talles'
                        for i in range(col_talles + 1, col_total):
                            val = row.iloc[i]
                            try:
                                if not pd.isna(val) and str(val).strip() != "":
                                    posible_id = int(float(val))
                                    curva_id = posible_id
                                    curva_col_idx = i
                                    break
                            except:
                                continue
                        if curva_id is None or curva_col_idx is None:
                            continue

                    curva_row_idx = None
                    for j in range(curva_block.shape[0]):
                        val = curva_block.iloc[j, curva_col_idx]
                        try:
                            if int(float(val)) == curva_id:
                                curva_row_idx = curva_block_start + j
                                break
                        except:
                            continue
                    if curva_row_idx is None:
                        continue

                    talles = df_full.iloc[curva_row_idx, curva_col_idx+1:col_total]
                    cantidades = row.iloc[curva_col_idx+1:col_total]

                    for col_offset, cantidad in enumerate(cantidades):
                        if pd.isna(cantidad) or float(cantidad) == 0:
                            continue
                        talle = formatear_talle(talles.iloc[col_offset], curva_id, tipo_producto)
                        precio = round(float(row["Fab"]), 2)
                        precio_str = str(precio).replace(".", ",")
                        cod_barra = obtener_codigo_barra(cod_articulo, talle)

                        # Para ACC con curva 5 y talles específicos, intentar con "U" si no se encuentra
                        if not cod_barra and tipo_producto == "ACC" and curva_id == 5:
                            talles_curva_5 = ["100", "110", "120", "130", "140", "150", "160"]
                            if talle in talles_curva_5:
                                cod_barra = obtener_codigo_barra(cod_articulo, "U")

                        if not cod_barra:
                            print(f"❌ Código de barras NO encontrado → Artículo: {cod_articulo}, Talle: {talle}")
                            continue

                        filas_hoja.append({
                            "CAB": "PDCC1_",
                            "REFERENCIA INTERNA": referencia_base,
                            "FECHA DOC": fecha_doc,
                            "COD PROVEEDOR": "UNISO",
                            "CODIGO BARRAS": cod_barra,
                            "CANTIDAD": int(cantidad),
                            "PRECIO": precio_str,
                            "ALMACEN": "240001",
                            "ESTABLECIMIENTO": establecimiento,
                            "FECHA ENTREGA": fecha_entrega
                        })

                except Exception as e:
                    print(f"❌ Error procesando fila {idx} en hoja '{hoja}': {e}")
                    continue

            if filas_hoja:
                max_lineas_por_lote = 100
                total_lineas = len(filas_hoja)

                if total_lineas > max_lineas_por_lote:
                    lotes = []
                    lote_actual = []
                    ultimo_precio = None

                    for fila in filas_hoja:
                        precio_actual = fila["PRECIO"]
                        supero_limite = len(lote_actual) >= max_lineas_por_lote
                        cambio_precio = ultimo_precio is not None and precio_actual != ultimo_precio

                        if lote_actual and supero_limite and cambio_precio:
                            lotes.append(lote_actual)
                            lote_actual = []

                        lote_actual.append(fila)
                        ultimo_precio = precio_actual

                    if lote_actual:
                        lotes.append(lote_actual)

                    # Fallback: si nunca hubo cambio de precio y se superó el límite,
                    # dividir de forma tradicional para evitar archivos gigantes.
                    if len(lotes) == 1 and len(lotes[0]) > max_lineas_por_lote:
                        lotes = [
                            lotes[0][i : i + max_lineas_por_lote]
                            for i in range(0, len(lotes[0]), max_lineas_por_lote)
                        ]
                        print(f"⚠️ Se forzó división por longitud en hoja '{hoja}' al no detectarse cambio de precio.")

                    for idx, lote in enumerate(lotes, start=1):
                        nueva_ref = referencia_base if len(lotes) == 1 else f"{referencia_base} Parte {idx}"
                        for fila in lote:
                            fila["REFERENCIA INTERNA"] = nueva_ref
                        print(f"📦 {nueva_ref}: {len(lote)} líneas")
                    print(f"🔹 Total de líneas en hoja '{hoja}': {total_lineas}")
                    print(f"🔸 Dividido en {len(lotes)} sub-referencias respetando curvas completas")
                else:
                    for fila in filas_hoja:
                        fila["REFERENCIA INTERNA"] = referencia_base
                    print(f"✅ Hoja '{hoja}' exportada con referencia: {referencia_base} ({total_lineas} líneas)")
                todas_las_filas.extend(filas_hoja)
            else:
                print(f"⚠️ No se encontraron datos válidos para exportar en hoja '{hoja}'.")

        except Exception as e:
            print(f"❌ Error general en hoja '{hoja}': {e}")
            continue

    if todas_las_filas:
        transformed_df = pd.DataFrame(todas_las_filas)
        transformed_df.to_csv(output_path, index=False, sep="|", encoding="utf-8-sig")
        print(f"✅ Archivo generado correctamente en: {output_path}")
    else:
        print("⚠️ No se encontraron datos válidos para exportar.")
