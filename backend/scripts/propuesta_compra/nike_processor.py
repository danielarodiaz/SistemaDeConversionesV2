import pandas as pd
import os
import re
import math
from datetime import datetime

def normalizar_nombre_columna(col_name):
    """Normaliza el nombre de columna para comparación flexible."""
    if pd.isna(col_name):
        return ""
    return str(col_name).strip().lower().replace(".", "").replace(" ", "")

def encontrar_columna(df, posibles_nombres):
    """Encuentra una columna por múltiples variantes de nombre."""
    columnas_normalizadas = {normalizar_nombre_columna(col): col for col in df.columns}
    
    for nombre_posible in posibles_nombres:
        nombre_normalizado = normalizar_nombre_columna(nombre_posible)
        if nombre_normalizado in columnas_normalizadas:
            return columnas_normalizadas[nombre_normalizado]
    
    return None

def parsear_fecha_nike(fecha_val):
    """Parsea fechas en formato de Nike a ddmmAA."""
    try:
        # Si es un objeto datetime de pandas o Python
        if isinstance(fecha_val, (pd.Timestamp, datetime)):
            return fecha_val.strftime("%d%m%y")
        
        # Si es NaN o None
        if pd.isna(fecha_val):
            return None
        
        # Convertir a string
        fecha_str = str(fecha_val).strip()
        if not fecha_str or fecha_str.lower() == 'nan':
            return None
        
        # Intentar parsear como fecha de Excel (número serial)
        if isinstance(fecha_val, (int, float)):
            try:
                fecha_dt = pd.to_datetime(fecha_val, origin='1899-12-30', unit='D')
                return fecha_dt.strftime("%d%m%y")
            except:
                pass
        
        # Intentar parsear como string de fecha
        # Formatos posibles: "dd/mm/yyyy", "dd-mm-yyyy", "dd.mm.yyyy", etc.
        for formato in ["%d/%m/%Y", "%d-%m-%Y", "%d.%m.%Y", "%Y-%m-%d", "%d/%m/%y", "%d-%m-%y", "%d.%m.%y"]:
            try:
                fecha_dt = datetime.strptime(fecha_str, formato)
                return fecha_dt.strftime("%d%m%y")
            except:
                continue
        
        # Intentar parseo automático de pandas
        try:
            fecha_dt = pd.to_datetime(fecha_str)
            return fecha_dt.strftime("%d%m%y")
        except:
            pass
            
    except Exception as e:
        print(f"⚠️ Error parseando fecha: {fecha_val} → {e}")
    
    return None

def determinar_establecimiento(nombre_solicitante):
    """Determina el establecimiento basado en el nombre del solicitante."""
    if pd.isna(nombre_solicitante):
        return "001"
    
    nombre = str(nombre_solicitante).strip().upper()
    
    # Variantes de MARATHON SRL
    variantes_marathon = [
        "MARATHON SRL",
        "MARATHON",
        "MARATHON S.A.",
        "MARATHON SA",
        "MARATHON S.A",
    ]
    
    for variante in variantes_marathon:
        if variante in nombre:
            return "002"
    
    return "001"

def process_nike_propuesta_compra(input_path, output_path):
    """
    Procesa archivo de propuesta de compra de Nike.
    
    Mapea las columnas del archivo Excel a el formato requerido:
    - CAB: PDCC1_ (por defecto)
    - REFERENCIA INTERNA: "Pedido de Venta"
    - FECHA DOC: "Fec.Creación Ped."
    - COD PROVEEDOR: SOUTH (por defecto)
    - CODIGO BARRAS: "UPC"
    - CANTIDAD: "Alocado P."
    - PRECIO: "Importe U."
    - ALMACEN: 240001 (por defecto)
    - ESTABLECIMIENTO: 002 si "Nombre Solicitante" contiene "MARATHON SRL" o variantes, sino 001
    - FECHA ENTREGA: "Fec.Entrega"
    """
    try:
        print(f"--- INICIO PROCESO: {os.path.basename(input_path)} ---")
        
        # 1. Cargar el libro completo para verificar pestañas
        xl = pd.ExcelFile(input_path)
        nombres_hojas = xl.sheet_names
        print(f"📋 Pestañas detectadas: {nombres_hojas}")

        # 2. Determinar la hoja correcta
        # Priorizamos 'Sheet1' que es donde dijiste que están los datos
        if "Sheet1" in nombres_hojas:
            target_sheet = "Sheet1"
        elif len(nombres_hojas) > 1:
            target_sheet = nombres_hojas[1] # Backup: la segunda pestaña
            print(f"⚠️ 'Sheet1' no encontrada, usando la segunda pestaña: {target_sheet}")
        else:
            target_sheet = nombres_hojas[0]

        # 3. Encontrar la fila del encabezado dentro de esa hoja
        # Leemos las primeras 20 filas para localizar "Pedido de Venta"
        header_check = pd.read_excel(input_path, sheet_name=target_sheet, nrows=20, header=None)
        header_row_index = 0
        
        for i, row in header_check.iterrows():
            fila_str = " ".join([str(val) for val in row.values]).lower()
            if "pedido de venta" in fila_str:
                header_row_index = i
                print(f"🎯 Cabecera encontrada en {target_sheet}, fila: {header_row_index}")
                break

        # 4. Carga definitiva de datos
        df = pd.read_excel(input_path, sheet_name=target_sheet, skiprows=header_row_index, dtype=str)
        
        # Limpieza de columnas fantasma (Unnamed)
        df = df.loc[:, ~df.columns.str.contains('^Unnamed')]
        
        print(f"📊 Columnas cargadas exitosamente: {len(df.columns)}")
        
        # VALIDACIÓN DE SEGURIDAD
        if df.empty or len(df.columns) < 5:
            raise ValueError(f"La pestaña {target_sheet} parece no tener los datos esperados.")

        # ... resto de tu lógica de búsqueda de columnas (col_pedido_venta, etc)
        # Buscar columnas con los nombres exactos del encabezado proporcionado
        col_pedido_venta = encontrar_columna(df, [
            "Pedido de Venta",
            "PedidoVenta",
            "Pedido Venta"
        ])
        
        col_fec_creacion = encontrar_columna(df, [
            "Fec.Creación Ped.",
            "Fec Creación Ped",
            "Fec.Creacion Ped.",
            "Fecha Creación Pedido",
            "Fecha Creacion Pedido",
            "Fec.Creación Ped",
            "Fec Creación Ped."
        ])
        
        col_nombre_solicitante = encontrar_columna(df, [
            "Nombre Solicitante",
            "NombreSolicitante",
            "Solicitante",
            "Nombre del Solicitante"
        ])
        
        col_upc = encontrar_columna(df, [
            "UPC",
            "Codigo Barras",
            "Código de Barras",
            "Código Barras"
        ])
        
        col_alocado_p = encontrar_columna(df, [
            "Alocado P.",
            "Alocado P",
            "AlocadoP.",
            "Alocado Pendiente"
        ])
        
        col_importe_u = encontrar_columna(df, [
            "Importe U.",
            "Importe U",
            "ImporteU.",
            "Importe Unitario",
            "Precio Unitario"
        ])
        
        col_fec_entrega = encontrar_columna(df, [
            "Fec.Entrega",
            "Fec Entrega",
            "Fecha Entrega",
            "Fecha de Entrega"
        ])
        
        # Validar que todas las columnas requeridas estén presentes
        columnas_requeridas = {
            "Pedido de Venta": col_pedido_venta,
            "Fec.Creación Ped.": col_fec_creacion,
            "Nombre Solicitante": col_nombre_solicitante,
            "UPC": col_upc,
            "Alocado P.": col_alocado_p,
            "Importe U.": col_importe_u,
            "Fec.Entrega": col_fec_entrega
        }
        
        columnas_faltantes = [nombre for nombre, col in columnas_requeridas.items() if col is None]
        if columnas_faltantes:
            error_msg = f"❌ Columnas requeridas no encontradas: {', '.join(columnas_faltantes)}"
            print(error_msg)
            raise ValueError(error_msg)
        
        transformed_data = []
        
        for idx, row in df.iterrows():
            try:
                # Obtener valores de las columnas
                referencia_interna = str(row[col_pedido_venta]).strip()
                if not referencia_interna or referencia_interna.lower() == 'nan':
                    continue
                
                # Cantidad: "Alocado P."
                cantidad_str = str(row[col_alocado_p]).strip()
                try:
                    cantidad = float(cantidad_str.replace(',', '.'))
                    if cantidad <= 0:
                        continue
                    cantidad = int(cantidad)
                except (ValueError, AttributeError):
                    continue
                
                # Precio: "Importe U."
                precio_str = str(row[col_importe_u]).strip()
                try:
                    precio = float(precio_str.replace(',', '.'))
                    precio_str = str(precio).replace('.', ',')
                except (ValueError, AttributeError):
                    precio_str = "0"
                
                # UPC: "CODIGO BARRAS"
                codigo_barras = str(row[col_upc]).strip()
                if not codigo_barras or codigo_barras.lower() == 'nan':
                    continue
                
                # Fecha DOC: "Fec.Creación Ped."
                fecha_doc_raw = row[col_fec_creacion]
                fecha_doc = parsear_fecha_nike(fecha_doc_raw)
                if not fecha_doc:
                    print(f"⚠️ Fecha de documento inválida en fila {idx + 1}, usando fecha actual")
                    fecha_doc = datetime.now().strftime("%d%m%y")
                
                # Fecha ENTREGA: "Fec.Entrega"
                fecha_entrega_raw = row[col_fec_entrega]
                fecha_entrega = parsear_fecha_nike(fecha_entrega_raw)
                if not fecha_entrega:
                    print(f"⚠️ Fecha de entrega inválida en fila {idx + 1}")
                    continue
                
                # ESTABLECIMIENTO: basado en "Nombre Solicitante"
                nombre_solicitante = row[col_nombre_solicitante]
                establecimiento = determinar_establecimiento(nombre_solicitante)
                
                transformed_row = {
                    "CAB": "PDCC1_",
                    "REFERENCIA INTERNA": referencia_interna,
                    "FECHA DOC": fecha_doc,
                    "COD PROVEEDOR": "SOUTH",
                    "CODIGO BARRAS": codigo_barras,
                    "CANTIDAD": cantidad,
                    "PRECIO": precio_str,
                    "ALMACEN": "240001",
                    "ESTABLECIMIENTO": establecimiento,
                    "FECHA ENTREGA": fecha_entrega,
                }
                
                transformed_data.append(transformed_row)
                
            except Exception as e:
                print(f"⚠️ Error procesando fila {idx + 1}: {e}")
                continue
        
        if transformed_data:
            transformed_df = pd.DataFrame(transformed_data)
            
            # Ordenar por fecha de entrega (ddmmAA → orden cronológico)
            transformed_df["FECHA ENTREGA"] = transformed_df["FECHA ENTREGA"].astype(str)
            transformed_df["orden"] = transformed_df["FECHA ENTREGA"].apply(
                lambda x: x[4:6] + x[2:4] + x[0:2] if len(x) == 6 else "000000"
            )
            transformed_df = transformed_df.sort_values(by="orden").drop(columns=["orden"])
            
            # Dividir dinámicamente si hay más de X líneas
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
            return output_path
            
        else:
            print("⚠️ No se generaron datos válidos para exportar.")
            raise ValueError("No se generaron datos válidos para exportar.")
            
    except Exception as e:
        print(f"❌ Error al procesar el archivo: {e}")
        raise
