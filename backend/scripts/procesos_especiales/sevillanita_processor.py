import pandas as pd
import os
import re
import zipfile
import traceback
import chardet
from utils.ocr_utils import calcular_ocr_code

def detectar_encoding(file_path, num_bytes=4096):
    """Detecta la codificación del archivo usando más bytes para mejor precisión"""
    with open(file_path, 'rb') as f:
        raw_data = f.read(num_bytes)
        result = chardet.detect(raw_data)
        # Si la confianza es baja o no se detectó encoding, usar latin1
        if result['confidence'] < 0.7 or not result['encoding']:
            return 'latin1'
        return result['encoding']

def limpiar_caracteres_especiales(texto):
    """Limpia caracteres especiales problemáticos"""
    if not isinstance(texto, str):
        return texto
    # Reemplazar el símbolo del Yen por 'Ñ'
    texto = texto.replace('¥', 'Ñ')
    # Reemplazar otros caracteres problemáticos comunes
    reemplazos = {
        '€': 'E',
        '£': 'L',
        '¥': 'Ñ',
        '¿': '?',
        '¡': '!'
    }
    for char, reemplazo in reemplazos.items():
        texto = texto.replace(char, reemplazo)
    return texto

def process_csv_to_transformed_sevillanita(input_path, output_path):
    try:
        # Detectar encoding primero
        encoding_detectado = detectar_encoding(input_path)
        print(f"⚠️ Codificación detectada: {encoding_detectado}")
        
        # Intentar leer el archivo con el encoding detectado
        try:
            with open(input_path, 'r', encoding=encoding_detectado) as f:
                first_line = f.readline()
                delimiter = ";" if ";" in first_line else ","
            
            data = pd.read_csv(input_path, dtype=str, delimiter=delimiter, 
                             on_bad_lines="skip", encoding=encoding_detectado)
            
        except UnicodeDecodeError:
            # Si falla, intentar con latin1 que es más permisivo
            print("⚠️ Falló el encoding detectado, intentando con latin1")
            with open(input_path, 'r', encoding='latin1') as f:
                first_line = f.readline()
                delimiter = ";" if ";" in first_line else ","
            
            data = pd.read_csv(input_path, dtype=str, delimiter=delimiter, 
                             on_bad_lines="skip", encoding='latin1')

        # Limpiar caracteres especiales en las columnas relevantes
        columnas_a_limpiar = ['Domicilio de Entrega', 'Localidad', 'Destinatario', 'Remitente']
        for columna in columnas_a_limpiar:
            if columna in data.columns:
                data[columna] = data[columna].apply(limpiar_caracteres_especiales)

        data.columns = [col.strip() for col in data.columns]
        
        # 🔹 Eliminar columnas vacías o con nombres "Unnamed"
        data = data[[col for col in data.columns if col != "" and not col.startswith("Unnamed")]]
        
        # Mapeo de nombres de columnas con variantes
        column_mapping = {
            "Importe Flete": ["Importe Flete", "Inporte Flete", "ImporteFlete"],
            "Importe Seguro": ["Importe Seguro", "Inporte Seguro", "ImporteSeguro"],
            "F.Emis.": ["F.Emis.", "F.Emision"],
            "Nro.Guia": ["Nro.Guia", "Nro Guia"],
            # Agregás más si encontrás otros casos
        }

        # Renombrar columnas si tienen errores comunes
        for standard_name, alternatives in column_mapping.items():
            for alt in alternatives:
                if alt in data.columns:
                    data.rename(columns={alt: standard_name}, inplace=True)
                    break

        if "F.Emis." not in data.columns:
            raise ValueError("No se encontró la columna 'F.Emis.' en el archivo CSV.")

        cabecera_marathon = []
        cabecera_otros = []
        detalle_marathon = []
        detalle_otros = []
        docnum_marathon = 1
        docnum_otros = 1

        for _, row in data.iterrows():
            try:
                # Ignorar filas corruptas o vacías en su mayoría
                if not isinstance(row, pd.Series) or row.isnull().sum() > len(row) - 2:
                    continue

                # 🔒 También descartar si no hay 'Cuenta' o 'F.Emis.'
                if pd.isna(row.get("Cuenta")) or pd.isna(row.get("F.Emis.")):
                    continue
                
                # Fecha de emisión: soporta DDMMYYYY o DD/MM/YYYY
                fecha_emision = str(row["F.Emis."]).strip()
                if re.match(r"^\d{1,2}/\d{1,2}/\d{4}$", fecha_emision):  # permite 1/4/2025
                    partes = fecha_emision.split("/")
                    fecha_emision = f"{partes[2]}{partes[1].zfill(2)}{partes[0].zfill(2)}"
                elif re.match(r"^\d{8}$", fecha_emision):  # ej: 20032025
                    fecha_emision = f"{fecha_emision[4:8]}{fecha_emision[2:4]}{fecha_emision[0:2]}"
                else:
                    print(f"Formato de fecha inválido: {fecha_emision}")
                    continue

                pti_code = row["Pref"].strip().zfill(5)
                letter = "A"
                fol_num_from = row["Nro.Guia"].strip().zfill(8)
                num_at_card = f"{letter}{pti_code}{fol_num_from}"

                # 🔐 Normalizar campos que puedan venir como float o NaN
                cuenta = str(row.get("Cuenta", "")).strip()
                if cuenta == "":
                    continue
                
                # Asignación directa por cuenta
                if cuenta == "13437":
                    belongs_to_marathon = True
                elif cuenta == "74061":
                    belongs_to_marathon = False
                else:
                    # Fallback a la lógica anterior
                    remitente = row.get("Remitente", "").strip()
                    destinatario = row.get("Destinatario", "").strip()
                    belongs_to_marathon = "MARATHON SRL" in [remitente, destinatario]   
                    
                # Comments: Remito y Valor Declarado
                remito = str(row.get("Remito","")).strip()  
                valor_declarado = str(row.get("Valor Declarado", "0").replace(",", ".")).strip()
                
                # Validaciones y formateo
                try:
                    remit = int(float(remito)) if remito else 0
                except ValueError:
                    remit = 0

                try:
                    value_D = round(float(valor_declarado), 2)
                except ValueError:
                    value_D = 0.0
                    
                # Formatear con separador de miles y decimales
                valor_formateado = f"{value_D:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
                    
                comentario = f"REM: {remit} - VD: {valor_formateado}"
                
                # 🧠 DocNum local
                docnum_local = docnum_marathon if belongs_to_marathon else docnum_otros

                cabecera_row = {
                    "DocNum": docnum_local,
                    "DocEntry": docnum_local,
                    "DocType": "dDocument_Items",
                    "DocDate": fecha_emision,
                    "TaxDate": fecha_emision,
                    "DocDueDate": "",
                    "CardCode": "SEVIL",
                    "NumAtCard": num_at_card,
                    "DocCur": "ARS",
                    "JournalMemo": "Fact.proveedores - SEVIL",
                    "Comments": comentario,
                    "PTICode": pti_code,
                    "Letter": letter,
                    "FolNumFrom": fol_num_from,
                    "FolNumTo": fol_num_from,
                    "Series": "14",
                }

                ocr_code = calcular_ocr_code(
                    destinatario=row.get("Destinatario", ""),
                    localidad=row.get("Localidad", ""),
                    domicilio=row.get("Domicilio de Entrega", ""),
                    remitente=row.get("Remitente", ""),
                    puerta=row.get("Puerta", "")
                )
                ocr_code2 = ocr_code[:-1] + "2"
  
                # DETALLE
                detalle_fila = []
                for line_num in range(4):
                    item_code = 100 + line_num
                    dscription = {
                        100: "FLETE DE TERCEROS",
                        101: "FLETES - SEGURO",
                        102: "FLETES - KILOS",
                        103: "FLETES - CAJAS"
                    }.get(item_code, "FLETE")
                    
                    def safe_int(value):
                        try:
                            return int(str(value).replace(",", ".").split(".")[0].strip())
                        except:
                            return 0

                    quantity = 1
                    if item_code == 102:
                        quantity = safe_int(row.get("Kilos", "0"))
                    elif item_code == 103:
                        quantity = safe_int(row.get("Bultos", "0"))

                    price = 0.0
                    if item_code == 100:
                        price = float(row.get("Importe Flete", "0").replace(",", "."))
                    elif item_code == 101:
                        price = float(row.get("Importe Seguro", "0").replace(",", "."))

                    detalle_row = {
                        "DocNum": docnum_local,
                        "LineNum": line_num,
                        "ItemCode": str(item_code),
                        "Dscription": dscription,
                        "Quantity": quantity,
                        "Price": price,
                        "TaxCode": "IVA_21",
                        "TaxOnly": "N",
                        "AcctCode": "5.2.020.05.001",
                        "OcrCode": ocr_code,
                        "OcrCode2": ocr_code2
                    }

                    detalle_fila.append(detalle_row)

                if belongs_to_marathon:
                    cabecera_marathon.append(cabecera_row)
                    detalle_marathon.extend(detalle_fila)
                    docnum_marathon += 1
                else:
                    cabecera_otros.append(cabecera_row)
                    detalle_otros.extend(detalle_fila)
                    docnum_otros += 1

            except Exception as e:
                print(f"Error procesando fila: {e}")

        def save_csv(file_path, data_list, header1, header2):
            if data_list:
                df = pd.DataFrame(data_list)
                with open(file_path, "w", encoding="utf-8", newline="") as f:
                    f.write(";".join(header1) + "\n")
                    f.write(";".join(header2) + "\n")
                    df.to_csv(f, index=False, sep=";", header=False)
                os.chmod(file_path, 0o777)
                print(f"Archivo generado: {file_path}")

        # ENCABEZADOS
        header_line_1_cab = ["DocNum", "DocEntry", "DocType", "DocDate", "TaxDate", "DocDueDate",
                             "CardCode", "NumAtCard", "DocCurrency", "JournalMemo", "Comments",
                             "PointOfIssueCode", "Letter", "FolioNumberFrom", "FolioNumberTo", "Series"]
        header_line_2_cab = ["DocNum", "DocEntry", "DocType", "DocDate", "TaxDate", "DocDueDate",
                             "CardCode", "NumAtCard", "DocCur", "JournalMemo", "Comments",
                             "PTICode", "Letter", "FolNumFrom", "FolNumTo", "Series"]

        header_line_1_det = ["ParentKey", "LineNum", "ItemCode", "ItemDescription", "Quantity", "Price",
                             "TaxCode", "TaxOnly", "AccountCode", "CostingCode", "CostingCode2"]
        header_line_2_det = ["DocNum", "LineNum", "ItemCode", "Dscription", "Quantity", "Price",
                             "TaxCode", "TaxOnly", "AcctCode", "OcrCode", "OcrCode2"]

        # Rutas
        cab_mar_path = output_path.replace(".csv", "_CABECERA_marathon.csv")
        cab_otr_path = output_path.replace(".csv", "_CABECERA_blanco.csv")
        det_mar_path = output_path.replace(".csv", "_DETALLE_marathon.csv")
        det_otr_path = output_path.replace(".csv", "_DETALLE_blanco.csv")
        
        print(f"Registros MARATHON: cabecera={len(cabecera_marathon)}, detalle={len(detalle_marathon)}")
        print(f"Registros BLANCO: cabecera={len(cabecera_otros)}, detalle={len(detalle_otros)}")

        # Guardar archivos
        save_csv(cab_mar_path, cabecera_marathon, header_line_1_cab, header_line_2_cab)
        save_csv(cab_otr_path, cabecera_otros, header_line_1_cab, header_line_2_cab)
        save_csv(det_mar_path, detalle_marathon, header_line_1_det, header_line_2_det)
        save_csv(det_otr_path, detalle_otros, header_line_1_det, header_line_2_det)     
        
        # ✅ Generar ZIP solo con archivos que existen
        zip_path = output_path.replace(".csv", ".zip")
        with zipfile.ZipFile(zip_path, 'w') as zipf:
            for path in [cab_mar_path, cab_otr_path, det_mar_path, det_otr_path]:
                if os.path.exists(path):
                    zipf.write(path, os.path.basename(path))

        return zip_path

    except Exception as e:
        print("Error general procesando archivo.")
        if 'row' in locals():
            print("Fila con error:", row.to_dict())
        traceback.print_exc()
        raise RuntimeError(f"Error al procesar el archivo: {e}")

