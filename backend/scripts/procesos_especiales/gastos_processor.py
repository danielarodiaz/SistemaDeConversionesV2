import pandas as pd
import os
import zipfile
import traceback
from utils.gastos_utils import (
    obtener_codprov_por_cuit_y_proveedor,
    convertir_fecha_formato,
    obtener_valores_por_comentario,
)

def process_gastos_procesos_especiales(input_path, output_path):
    """
    Procesador para Gastos.
    Lee archivo .xlsx y genera archivos de cabecera y detalle.
    """
    try:
        # 1. Leer archivo Excel
        data = pd.read_excel(input_path, dtype=str)
        
        # Limpiar nombres de columnas
        data.columns = [col.strip() for col in data.columns]
        data = data[[col for col in data.columns if col != "" and not col.startswith("Unnamed")]]
        
        # Validar columnas
        required_columns = ["NÚMERO", "FECHA", "PROVEEDOR", "CUIT", "FACTURA", "SUCURSAL", "MONTO", "COMENTARIO"]
        missing_columns = [col for col in required_columns if col not in data.columns]
        if missing_columns:
            raise ValueError(f"Faltan columnas requeridas: {', '.join(missing_columns)}")

        # --- SOLUCIÓN AL ERROR 'filas' ---
        # Convertimos el DataFrame a una lista de diccionarios para poder iterar
        filas = data.to_dict('records')
        
        # Inicializar listas para salida
        cabecera = []
        detalle = []
        
        # 2. AGRUPACIÓN POR DOCUMENTO (Proveedor + Número)
        # Esto separa TIQUEB de TIQUEX aunque compartan el mismo número en el Excel
        grupos_por_documento = {}

        for fila in filas:
            cuit = str(fila.get("CUIT", "")).strip()
            proveedor_txt = str(fila.get("PROVEEDOR", "")).strip()
            numero = str(fila.get("NÚMERO", "")).strip()
            
            # Identificar el proveedor real usando la lógica de utils
            codigo_proveedor = obtener_codprov_por_cuit_y_proveedor(cuit, proveedor_txt)
            
            if not codigo_proveedor:
                print(f"Advertencia: No se pudo identificar proveedor para {proveedor_txt} (CUIT {cuit})")
                continue

            # Clave única para el grupo
            clave_doc = f"{codigo_proveedor}_{numero}"
            
            if clave_doc not in grupos_por_documento:
                grupos_por_documento[clave_doc] = []
            
            grupos_por_documento[clave_doc].append(fila)

        # 3. PROCESAMIENTO DE GRUPOS
        docnum = 1
        for clave_doc, filas_grupo in grupos_por_documento.items():
            if not filas_grupo:
                continue
            
            primera_fila = filas_grupo[0]
            
            # FECHA
            fecha = convertir_fecha_formato(primera_fila.get("FECHA", ""))
            if not fecha:
                continue
            
            # Datos del Proveedor (ya validados en la agrupación)
            cuit_input = str(primera_fila.get("CUIT", "")).strip()
            proveedor_input = str(primera_fila.get("PROVEEDOR", "")).strip()
            codigo_proveedor = obtener_codprov_por_cuit_y_proveedor(cuit_input, proveedor_input)

            # FACTURA, Letra y Series
            factura_val = str(primera_fila.get("FACTURA", "")).strip().upper()
            letter = factura_val
            numero_raw = str(primera_fila.get("NÚMERO", "")).strip()

            if factura_val in ("B", "C"):
                series = "14"
                if "-" in numero_raw:
                    pti_parte, folio_parte = numero_raw.split("-", 1)
                    pti_parte = "".join(ch for ch in pti_parte if ch.isdigit())
                    folio_parte = "".join(ch for ch in folio_parte if ch.isdigit())
                else:
                    pti_parte = ""
                    folio_parte = "".join(ch for ch in numero_raw if ch.isdigit())

                pti_code = pti_parte.zfill(5) if pti_parte else "00001"
                fol_num_from = folio_parte.zfill(8) if folio_parte else "0".zfill(8)
            else:
                series = "139"
                pti_code = "99999"
                folio_parte = "".join(ch for ch in numero_raw if ch.isdigit())
                fol_num_from = folio_parte.zfill(8) if folio_parte else "0".zfill(8)

            fol_num_to = fol_num_from
            num_at_card = f"{letter}{pti_code}{fol_num_from}"
            
            # CABECERA
            cabecera.append({
                "DocNum": docnum,
                "DocEntry": docnum,
                "DocType": "dDocument_Items",
                "DocDate": fecha,
                "TaxDate": fecha,
                "DocDueDate": "",
                "CardCode": codigo_proveedor,
                "NumAtCard": num_at_card,
                "DocCur": "ARS",
                "JournalMemo": f"Fact.proveedores - {codigo_proveedor}",
                "Comments": "",
                "PTICode": pti_code,
                "Letter": letter,
                "FolNumFrom": fol_num_from,
                "FolNumTo": fol_num_to,
                "Series": series,
            })
            
            # DETALLE (Agrupado por sucursal + artículo resultante)
            grupos_por_sucursal = {}
            for fila in filas_grupo:
                sucursal = str(fila.get("SUCURSAL", "")).strip()
                comentario = str(fila.get("COMENTARIO", "")).strip()
                monto = str(fila.get("MONTO", "0")).strip()
                
                if not sucursal: continue
                
                valores_temp = obtener_valores_por_comentario(comentario, sucursal)
                if not valores_temp: continue
                
                item_code_temp = valores_temp["articulo"]
                clave_grupo_det = f"{sucursal}|{item_code_temp}"
                
                if clave_grupo_det not in grupos_por_sucursal:
                    grupos_por_sucursal[clave_grupo_det] = {
                        "sucursal": sucursal,
                        "comentario": comentario,
                        "monto_total": 0.0
                    }
                
                try:
                    # 1. Convertir a string, quitar espacios y el símbolo $ (por si acaso)
                    m_str = str(monto).strip().replace("$", "")
                    
                    # 2. Manejo de miles y decimales:
                    # Si tiene coma, es el separador decimal de Argentina.
                    # Primero quitamos el punto de miles (solo si hay coma)
                    # y luego pasamos la coma a punto.
                    if "," in m_str:
                        m_str = m_str.replace(".", "").replace(",", ".")
                    
                    # 3. Convertir a número
                    monto_val = float(m_str)
                    grupos_por_sucursal[clave_grupo_det]["monto_total"] += monto_val
                    
                except Exception as e:
                    print(f"Error al convertir monto '{monto}': {e}")
            
            line_num = 0
            for clave, grupo_data in sorted(grupos_por_sucursal.items()):
                valores = obtener_valores_por_comentario(grupo_data["comentario"], grupo_data["sucursal"])
                
                # Regla de TaxCode
                letra_norm = str(letter).strip().upper()
                tax_code = "IVA_NL"
                if letra_norm == "C": tax_code = "IVA_EXE"
                elif letra_norm == "B": tax_code = "IVA_NG"

                # OCR Codes
                suc_norm = str(grupo_data["sucursal"]).zfill(6)
                ocr1 = valores["ocr_code"] if valores["ocr_code"] else f"{suc_norm}-1"
                ocr2 = valores["ocr_code2"] if valores["ocr_code2"] else f"{suc_norm}-2"

                detalle.append({
                    "DocNum": docnum,
                    "LineNum": line_num,
                    "ItemCode": valores["articulo"],
                    "Dscription": valores["descripcion"],
                    "Quantity": 1,
                    "Price": round(grupo_data["monto_total"], 2),
                    "TaxCode": tax_code,
                    "TaxOnly": "N",
                    "WhsCode": "01",
                    "AcctCode": valores["cuenta"],
                    "OcrCode": ocr1,
                    "OcrCode2": ocr2,
                })
                line_num += 1
            
            docnum += 1

        # --- GUARDADO DE ARCHIVOS ---
        def save_csv(file_path, data_list, h1, h2):
            if data_list:
                df_out = pd.DataFrame(data_list)
                with open(file_path, "w", encoding="utf-8", newline="") as f:
                    f.write(";".join(h1) + "\n")
                    f.write(";".join(h2) + "\n")
                    df_out.to_csv(f, index=False, sep=";", header=False)

        base_name = os.path.splitext(output_path)[0]
        cab_path, det_path = f"{base_name}_CABECERA.csv", f"{base_name}_DETALLE.csv"
        
        # Encabezados SAP
        h1_cab = ["DocNum", "DocEntry", "DocType", "DocDate", "TaxDate", "DocDueDate", "CardCode", "NumAtCard", "DocCurrency", "JournalMemo", "Comments", "PointOfIssueCode", "Letter", "FolioNumberFrom", "FolioNumberTo", "Series"]
        h2_cab = ["DocNum", "DocEntry", "DocType", "DocDate", "TaxDate", "DocDueDate", "CardCode", "NumAtCard", "DocCur", "JournalMemo", "Comments", "PTICode", "Letter", "FolNumFrom", "FolNumTo", "Series"]
        h1_det = ["ParentKey", "LineNum", "ItemCode", "ItemDescription", "Quantity", "Price", "TaxCode", "TaxOnly", "WarehouseCode", "AccountCode", "CostingCode", "CostingCode2"]
        h2_det = ["DocNum", "LineNum", "ItemCode", "Dscription", "Quantity", "Price", "TaxCode", "TaxOnly", "WhsCode", "AcctCode", "OcrCode", "OcrCode2"]

        save_csv(cab_path, cabecera, h1_cab, h2_cab)
        save_csv(det_path, detalle, h1_det, h2_det)

        zip_path = output_path.replace(".csv", ".zip")
        with zipfile.ZipFile(zip_path, 'w') as zipf:
            for p in [cab_path, det_path]:
                if os.path.exists(p): zipf.write(p, os.path.basename(p))
        
        return zip_path
        
    except Exception as e:
        traceback.print_exc()
        raise RuntimeError(f"Error al procesar el archivo: {e}")