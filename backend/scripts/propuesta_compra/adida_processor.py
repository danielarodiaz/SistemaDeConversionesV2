import pandas as pd
import os
import re
import math
from datetime import datetime

def parsear_fecha(fecha_str):
    meses_es = {
        "ene": "01", "ene.": "01",
        "feb": "02", "feb.": "02",
        "mar": "03", "mar.": "03",
        "abr": "04", "abr.": "04",
        "may": "05", "may.": "05",
        "jun": "06", "jun.": "06",
        "jul": "07", "jul.": "07",
        "ago": "08", "ago.": "08",
        "sep": "09", "sep.": "09",
        "oct": "10", "oct.": "10",
        "nov": "11", "nov.": "11",
        "dic": "12", "dic.": "12"
    }

    try:
        fecha_str = str(fecha_str).strip().lower()

        if fecha_str.startswith("w"):
            fecha_str = fecha_str.split(" - ")[-1]

        partes = fecha_str.split()

        if len(partes) == 3 and partes[1] in meses_es:
            dia = partes[0].zfill(2)
            mes = meses_es[partes[1]]
            anio = partes[2]

            return f"{dia}{mes}{anio[-2:]}"

    except Exception as e:
        print(f"⚠️ Error parseando fecha: {fecha_str} → {e}")

    print(f"⚠️ Formato inesperado en la fecha de entrega: {fecha_str}")
    return None

def formatear_talle(talle):
    talle = str(talle).strip().upper()
    
    if talle == "NS":
        return "U"
    
    # Reemplazar nXL por la cantidad de X correspondiente
    if re.match(r"^\d+XL$", talle):
        num = int(talle[0])
        return "X" * num + "L"
    # Reemplazar nXS por la cantidad de X correspondiente
    if re.match(r"^\d+XS$", talle):
        num = int(talle[0])
        return "X" * num + "S"
    # Reemplazar "-" por ".5" solo si es un formato como "7-"
    if re.match(r"^\d+-$", talle):
        return talle.replace("-", ".5")

    return talle

def process_adidas_propuesta_compra(input_path, output_path):
    try:
        data = pd.read_excel(input_path, skiprows=4, dtype=str)
        transformed_data = []

        for _, row in data.iterrows():
            try:
                referencia_interna = str(row.get('SAP Order number', '')).strip()
                if not referencia_interna or referencia_interna.lower() == 'nan':
                    continue

                total = row.get('Total quantity', '0')
                rechazado = row.get('Rejected', '0')

                try:
                    cantidad = int(float(total)) - int(float(rechazado))
                except ValueError:
                    continue

                if cantidad <= 0:
                    continue

                fecha_entrega_raw = str(
                    row.get('Requested Delivery Date') 
                    or row.get('Requested On Shelf Date(s)') 
                    or ''
                ).strip()

                fecha_entrega = parsear_fecha(fecha_entrega_raw)

                fecha_doc = str(row.get('Order creation date', '')).strip()
                fecha_doc_parseada = parsear_fecha(fecha_doc)

                ean = str(row.get('EAN', '')).strip()
                if not ean or ean.lower() == 'nan':
                    cod_art = str(row.get('Article ID', '')).strip().replace(" ", "")
                    talle = formatear_talle(row.get('Size', ''))
                    ean = f"T{cod_art}{talle}"

                precio = str(row.get('LP', '0')).strip().replace('.', ',')
                establecimiento = '002' if str(row.get('Sold To', '')).strip() == '7300000658' else '001'

                transformed_row = {
                    "CAB": "PDCC1_",
                    "REFERENCIA INTERNA": referencia_interna,
                    "FECHA DOC": fecha_doc_parseada,
                    "COD PROVEEDOR": "ADIDA",
                    "CODIGO BARRAS": ean,
                    "CANTIDAD": cantidad,
                    "PRECIO": precio,
                    "ALMACEN": "240001",
                    "ESTABLECIMIENTO": establecimiento,
                    "FECHA ENTREGA": fecha_entrega,
                }

                transformed_data.append(transformed_row)
            except Exception as e:
                print(f"⚠️ Error procesando fila: {e}")
                continue

        if transformed_data:
            transformed_df = pd.DataFrame(transformed_data)

            # ✅ Ordenar por fecha de entrega (ddmmAA → orden cronológico)
            transformed_df["FECHA ENTREGA"] = transformed_df["FECHA ENTREGA"].astype(str)
            transformed_df["orden"] = transformed_df["FECHA ENTREGA"].apply(lambda x: x[4:6] + x[2:4] + x[0:2])
            transformed_df = transformed_df.sort_values(by="orden").drop(columns=["orden"])

            # ✅ Dividir dinámicamente si hay más de X líneas
            max_lineas_por_lote = 115
            total_lineas = len(transformed_df)

            if total_lineas > max_lineas_por_lote:
                referencia_original = transformed_df.iloc[0]["REFERENCIA INTERNA"]
                num_lotes = math.ceil(total_lineas / max_lineas_por_lote)

                base = total_lineas // num_lotes
                sobrantes = total_lineas % num_lotes

                start = 0
                for i in range(num_lotes):
                    # Distribuir 1 sobrante extra a los primeros `sobrantes` lotes
                    cantidad = base + (1 if i < sobrantes else 0)
                    end = start + cantidad
                    actual_ref = f"{referencia_original}/{i + 1}"
                    transformed_df.iloc[start:end, transformed_df.columns.get_loc("REFERENCIA INTERNA")] = actual_ref
                    print(f"📦 {actual_ref}: {cantidad} líneas")
                    start = end

                print(f"🔹 Total de líneas: {total_lineas}")
                print(f"🔸 Dividido en {num_lotes} sub-referencias equilibradas de ~{base} líneas.")
                
            # Exportar
            transformed_df.to_csv(output_path, index=False, sep="|", encoding="utf-8-sig")
            print(f"✅ Archivo generado correctamente en: {output_path}")

        else:
            print("⚠️ No se generaron datos válidos para exportar.")

    except Exception as e:
        print(f"❌ Error al procesar el archivo: {e}")
