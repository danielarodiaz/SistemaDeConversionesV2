import pandas as pd
import os
import re
import zipfile
import traceback
from utils.ocr_utils import calcular_ocr_code

def extraer_info_del_nombre_archivo(file_path):
    """
    Extrae el número de factura y la fecha del nombre del archivo.
    Formato esperado: 0053-00010127 MAR 20260105 o 0053-00010127_MAR_20260105
    Retorna: (prefijo, folio, fecha_yyyymmdd, texto_intermedio)
    """
    nombre_archivo = os.path.basename(file_path)
    # Remover extensión
    nombre_sin_ext = os.path.splitext(nombre_archivo)[0]
    
    # Buscar patrón: número-número espacio/guion_bajo palabra espacio/guion_bajo fecha
    # Ejemplo: 0053-00010127 MAR 20260105 o 0053-00010127_MAR_20260105
    # Acepta tanto espacios como guiones bajos como separadores
    match = re.search(r'(\d+)-(\d+)[\s_]+(\w+)[\s_]+(\d{8})', nombre_sin_ext)
    if match:
        prefijo = match.group(1)  # "0053"
        folio = match.group(2)  # "00010127"
        texto_intermedio = match.group(3)  # "MAR"
        fecha = match.group(4)  # "20260105"
        return prefijo, folio, fecha, texto_intermedio
    else:
        raise ValueError(f"No se pudo extraer información del nombre del archivo: {nombre_archivo}")

def process_sevillanitaV2_procesos_especiales(input_path, output_path):
    """
    Procesador simplificado V2 para Sevillanita.
    Lee archivo .xlsx y genera archivos de cabecera y detalle.
    """
    try:
        # Leer archivo Excel
        data = pd.read_excel(input_path, dtype=str)
        
        # Limpiar nombres de columnas (eliminar espacios)
        data.columns = [col.strip() for col in data.columns]
        
        # Eliminar columnas vacías o con nombres "Unnamed"
        data = data[[col for col in data.columns if col != "" and not col.startswith("Unnamed")]]
        
        # Extraer información del nombre del archivo
        prefijo, folio, fecha_emision, texto_intermedio = extraer_info_del_nombre_archivo(input_path)
        
        # PTICode: prefijo rellenado a 5 dígitos con ceros a la izquierda
        pti_code = prefijo.zfill(5)  # "0053" -> "00053"
        
        # FolNumFrom: folio rellenado a 8 dígitos con ceros a la izquierda
        fol_num_from = folio.zfill(8)  # "00010127" -> "00010127"
        
        # Construir NumAtCard: A + PTICode (5 dígitos) + FolNumFrom (8 dígitos)
        num_at_card = f"A{pti_code}{fol_num_from}"
        
        letter = "A"
        series = "14"
        
        # Inicializar listas para cabecera y detalle
        # Solo una cabecera única basada en el nombre del archivo
        cabecera = []
        detalle = []
        docnum = 1
        
        # Crear única fila de cabecera basada solo en el nombre del archivo
        cabecera_row = {
            "DocNum": docnum,
            "DocEntry": docnum,
            "DocType": "dDocument_Items",
            "DocDate": fecha_emision,
            "TaxDate": fecha_emision,
            "DocDueDate": "",
            "CardCode": "SEVIL",
            "NumAtCard": num_at_card,
            "DocCur": "ARS",
            "JournalMemo": "Fact.proveedores - SEVIL",
            "Comments": "",  # Vacío como se solicitó
            "PTICode": pti_code,
            "Letter": letter,
            "FolNumFrom": fol_num_from,
            "FolNumTo": fol_num_from,
            "Series": series,
        }
        cabecera.append(cabecera_row)
        
        # Procesar detalle
        # Función para obtener OCR desde "Destinatario Carga"
        def obtener_ocr_code(destinatario_carga):
            """Obtiene el OCR code desde la columna Destinatario Carga"""
            if pd.isna(destinatario_carga) or not destinatario_carga:
                return "240001-1", "240001-2"
            
            destinatario_str = str(destinatario_carga).strip()
            # Verificar si los primeros 6 caracteres son numéricos
            primeros_6 = destinatario_str[:6] if len(destinatario_str) >= 6 else ""
            
            if primeros_6.isdigit():
                ocr_code = f"{primeros_6}-1"
                ocr_code2 = f"{primeros_6}-2"
                return ocr_code, ocr_code2
            else:
                return "240001-1", "240001-2"
        
        # Agrupar filas por OCR
        ocr_groups = {}
        
        for _, row in data.iterrows():
            try:
                # Ignorar filas vacías o corruptas
                if not isinstance(row, pd.Series) or row.isnull().sum() > len(row) - 2:
                    continue
                
                # Obtener OCR desde Destinatario Carga
                destinatario_carga = row.get("Destinatario Carga", "")
                ocr_code, ocr_code2 = obtener_ocr_code(destinatario_carga)
                
                # Inicializar grupo si no existe
                if ocr_code not in ocr_groups:
                    ocr_groups[ocr_code] = {
                        "ocr_code": ocr_code,
                        "ocr_code2": ocr_code2,
                        "flete_total": 0.0,
                        "seguro_total": 0.0
                    }
                
                # Sumar FLETE y SEGURO
                try:
                    flete_val = str(row.get("FLETE", "0")).replace(",", ".").strip()
                    flete_val = float(flete_val) if flete_val else 0.0
                    ocr_groups[ocr_code]["flete_total"] += flete_val
                except (ValueError, TypeError):
                    pass
                
                try:
                    seguro_val = str(row.get("SEGURO", "0")).replace(",", ".").strip()
                    seguro_val = float(seguro_val) if seguro_val else 0.0
                    ocr_groups[ocr_code]["seguro_total"] += seguro_val
                except (ValueError, TypeError):
                    pass
                    
            except Exception as e:
                print(f"Error procesando fila para detalle: {e}")
                traceback.print_exc()
                continue
        
        # Crear filas de detalle agrupadas por OCR
        line_num = 0
        for ocr_code_key, ocr_data in ocr_groups.items():
            # Fila para FLETE (ItemCode 100)
            detalle_row_flete = {
                "DocNum": docnum,
                "LineNum": line_num,
                "ItemCode": "100",
                "Dscription": "FLETES DE TERCEROS",
                "Quantity": 1,
                "Price": round(ocr_data["flete_total"], 2),
                "TaxCode": "IVA_21",
                "TaxOnly": "N",
                "WhsCode": "01",
                "AcctCode": "5.2.020.05.001",
                "OcrCode": ocr_data["ocr_code"],
                "OcrCode2": ocr_data["ocr_code2"]
            }
            detalle.append(detalle_row_flete)
            line_num += 1
            
            # Fila para SEGURO (ItemCode 101)
            detalle_row_seguro = {
                "DocNum": docnum,
                "LineNum": line_num,
                "ItemCode": "101",
                "Dscription": "FLETES - SEGURO",
                "Quantity": 1,
                "Price": round(ocr_data["seguro_total"], 2),
                "TaxCode": "IVA_21",
                "TaxOnly": "N",
                "WhsCode": "01",
                "AcctCode": "5.2.020.05.001",
                "OcrCode": ocr_data["ocr_code"],
                "OcrCode2": ocr_data["ocr_code2"]
            }
            detalle.append(detalle_row_seguro)
            line_num += 1
        
        def save_csv(file_path, data_list, header1, header2):
            """Guarda un archivo CSV con dos líneas de encabezado"""
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
                             "TaxCode", "TaxOnly","WarehouseCode", "AccountCode", "CostingCode", "CostingCode2"]
        header_line_2_det = ["DocNum", "LineNum", "ItemCode", "Dscription", "Quantity", "Price",
                             "TaxCode", "TaxOnly","WhsCode", "AcctCode", "OcrCode", "OcrCode2"]
        
        # Rutas de salida - incluir texto intermedio (ej: MAR) para identificación
        base_name = os.path.splitext(output_path)[0]
        cab_path = f"{base_name}_{texto_intermedio}_CABECERA.csv"
        det_path = f"{base_name}_{texto_intermedio}_DETALLE.csv"
        
        print(f"Registros: cabecera={len(cabecera)}, detalle={len(detalle)}")
        
        # Guardar archivos de cabecera y detalle
        save_csv(cab_path, cabecera, header_line_1_cab, header_line_2_cab)
        save_csv(det_path, detalle, header_line_1_det, header_line_2_det)
        
        # Generar ZIP solo con archivos que existen
        zip_path = output_path.replace(".csv", ".zip")
        with zipfile.ZipFile(zip_path, 'w') as zipf:
            for path in [cab_path, det_path]:
                if os.path.exists(path):
                    zipf.write(path, os.path.basename(path))
        
        return zip_path
        
    except Exception as e:
        print("Error general procesando archivo.")
        traceback.print_exc()
        raise RuntimeError(f"Error al procesar el archivo: {e}")

