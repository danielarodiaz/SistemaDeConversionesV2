import pandas as pd
import os
from datetime import datetime
import sys
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..'))
from utils.cegid_utils import obtener_costos_por_codigos_barras

def process_kosiuko_pedido_proveedor(input_path, output_path):
    """
    Procesa archivos .txt de Kosiuko y los convierte a formato CSV estándar.
    
    Formato de entrada:
    /DR 
    *FE 22/10/2025
    4+3926911271NE10L 
    4+3926911271NE10M 
    ...
    
    Formato de salida CSV:
    CAB|REFERENCIA INTERNA|FECHA|COD PROVEEDOR|CODIGO BARRAS|CANTIDAD|PRECIO|ALMACEN|ESTABLECIMIENTO|DESCUENTO
    """
    
    # Extraer nombre del archivo para usar como referencia interna
    filename = os.path.basename(input_path)
    referencia_interna = os.path.splitext(filename)[0]  # Sin extensión
    
    # Leer archivo .txt
    with open(input_path, 'r', encoding='utf-8') as file:
        lines = file.readlines()
    
    # Variables para almacenar datos
    fecha = None
    registros = []
    codigos_barras = []
    
    # Procesar cada línea
    for line in lines:
        line = line.strip()
        
        # Ignorar líneas vacías y líneas que empiecen con /DR
        if not line or line.startswith('/DR'):
            continue
            
        # Extraer fecha de líneas que empiecen con *FE
        if line.startswith('*FE'):
            fecha_str = line.replace('*FE', '').strip()
            try:
                # Convertir fecha de DD/MM/YYYY a DDMMYY
                fecha_obj = datetime.strptime(fecha_str, '%d/%m/%Y')
                fecha = fecha_obj.strftime('%d%m%y')
            except ValueError:
                print(f"⚠️ Error parseando fecha: {fecha_str}")
                continue
        
        # Procesar líneas de productos (formato: cantidad+codigo_barra)
        elif '+' in line:
            try:
                # Separar cantidad y código de barras
                parts = line.split('+')
                if len(parts) != 2:
                    continue
                    
                cantidad = int(parts[0])
                codigo_barra = parts[1]
                
                # Almacenar código de barras para búsqueda de precios
                codigos_barras.append(codigo_barra)
                
                # Crear registro
                registro = {
                    "CAB": "ZCOC_",
                    "REFERENCIA INTERNA": referencia_interna,
                    "FECHA": fecha,
                    "COD PROVEEDOR": "KOWZEF",
                    "CODIGO BARRAS": codigo_barra,
                    "CANTIDAD": cantidad,
                    "PRECIO": "0,00",  # Se llenará después
                    "ALMACEN": "240001",
                    "ESTABLECIMIENTO": "002",
                    "DESCUENTO": 0
                }
                registros.append(registro)
                
            except (ValueError, IndexError) as e:
                print(f"⚠️ Error procesando línea: {line} - {e}")
                continue
    
    if not registros:
        print("❌ No se encontraron registros válidos en el archivo")
        return
    
    # Obtener precios de CEGID
    print(f"🔍 Buscando precios para {len(codigos_barras)} códigos de barras...")
    precios_cegid = obtener_costos_por_codigos_barras(codigos_barras)
    
    # Actualizar precios en los registros
    for registro in registros:
        codigo_barra = registro["CODIGO BARRAS"]
        if codigo_barra in precios_cegid:
            _, precio_compra, _ = precios_cegid[codigo_barra]
            # Formatear precio con coma decimal
            precio_formateado = f"{round(precio_compra, 2):.2f}".replace('.', ',')
            registro["PRECIO"] = precio_formateado
        else:
            print(f"⚠️ No se encontró precio para código de barras: {codigo_barra}")
            # Mantener precio en 0,00 si no se encuentra
            registro["PRECIO"] = "0,00"
    
    # Crear DataFrame y exportar CSV
    df = pd.DataFrame(registros)
    
    # Ordenar por código de barras
    df.sort_values(by=["CODIGO BARRAS"], inplace=True)
    
    # Exportar CSV con delimitador pipe
    df.to_csv(output_path, sep="|", index=False, header=True)
    print(f"✅ Archivo procesado y guardado exitosamente: {output_path}")
    print(f"📊 Total de registros procesados: {len(registros)}")
    
    # Mostrar resumen de precios encontrados
    precios_encontrados = sum(1 for r in registros if r["PRECIO"] != "0,00")
    print(f"💰 Precios encontrados: {precios_encontrados}/{len(registros)}")