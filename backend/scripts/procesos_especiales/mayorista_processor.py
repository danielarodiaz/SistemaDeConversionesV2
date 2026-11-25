import pandas as pd
import os
import openpyxl
from openpyxl import Workbook
from backend.utils.cegid_utils import obtener_precio_venta_y_promo_por_codigo

def process_mayorista_procesos_especiales(input_path, output_path):
    """
    Procesa archivos de mayoristas agregando precios de venta y campo PROMO.
    """
    try:
        # Leer el archivo de entrada (solo Excel) preservando formatos originales
        print(f"📁 Leyendo archivo: {input_path}")
        
        # Leer con openpyxl para preservar formatos originales
        wb = openpyxl.load_workbook(input_path, data_only=True)
        ws = wb.active
        
        # Obtener datos de la hoja
        data = []
        headers = []
        
        for row in ws.iter_rows(values_only=True):
            if not headers:
                headers = [str(cell).strip() if cell is not None else '' for cell in row]
            else:
                data.append([str(cell) if cell is not None else '' for cell in row])
        
        df = pd.DataFrame(data, columns=headers)
        print("✅ Archivo leído como Excel preservando formatos originales")
        
        # Limpiar nombres de columnas
        df.columns = [col.strip() for col in df.columns]
        print(f"📊 Columnas encontradas: {df.columns.tolist()}")
        
        # Verificar que existen las columnas esperadas
        columnas_esperadas = ['Número de artículo', 'Descripción del artículo', 'Cantidad']
        columnas_faltantes = [col for col in columnas_esperadas if col not in df.columns]
        
        if columnas_faltantes:
            print(f"⚠️ Columnas faltantes: {columnas_faltantes}")
            print(f"📊 Columnas disponibles: {df.columns.tolist()}")
            raise ValueError(f"No se encontraron las columnas esperadas: {columnas_faltantes}")
        
        # Agregar columnas para precio de venta y promo
        df['Precio Venta'] = ''
        df['Promo'] = ''
        df['Marca'] = ''
        
        # Procesar cada fila para obtener precios y promos
        print("🔄 Procesando artículos...")
        total_filas = len(df)
        articulos_no_encontrados = []
        
        for index, row in df.iterrows():
            codigo_articulo = str(row["Número de artículo"]).strip()
            
            # Mostrar progreso cada 10 filas
            if (index + 1) % 10 == 0:
                print(f"📈 Procesando fila {index + 1}/{total_filas}")
            
            # Obtener precio de venta y promo
            datos = obtener_precio_venta_y_promo_por_codigo(codigo_articulo)
            
            # Verificar si no se encontraron datos
            if datos['precio_venta'] == 0.0 and datos['promo'] == '' and datos['marca'] == '':
                articulos_no_encontrados.append(codigo_articulo)
            
            # Actualizar el DataFrame
            df.at[index, 'Precio Venta'] = datos['precio_venta']
            df.at[index, 'Promo'] = datos['promo']
            df.at[index, 'Marca'] = datos['marca']
        
        print("✅ Procesamiento completado")
        
        # Convertir la columna 'Fecha' a string con el formato original
        # if 'Fecha' in df.columns:
        #     df['Fecha'] = pd.to_datetime(df['Fecha'], errors='coerce').dt.strftime('%d/%m/%Y')

        
        # Crear un nuevo archivo Excel con el DataFrame procesado
        with pd.ExcelWriter(output_path, engine='openpyxl') as writer:
            df.to_excel(writer, sheet_name='MAYORISTA', index=False)
        
        print(f"✅ Archivo guardado exitosamente: {output_path}")
        print(f"📊 Total de filas procesadas: {len(df)}")
        
        # Mostrar estadísticas
        filas_con_precio = len(df[df['Precio Venta'] != 0.0])
        filas_con_promo = len(df[df['Promo'] != ''])
        filas_con_marca = len(df[df['Marca'] != ''])
        
        print(f"📈 Estadísticas:")
        print(f"   - Filas con precio de venta: {filas_con_precio}")
        print(f"   - Filas con promo: {filas_con_promo}")
        print(f"   - Filas con marca: {filas_con_marca}")
        print(f"   - Total de filas: {len(df)}")
        
        # Mostrar artículos no encontrados
        if articulos_no_encontrados:
            print(f"⚠️ Artículos no encontrados ({len(articulos_no_encontrados)}):")
            for codigo in articulos_no_encontrados:
                print(f"   - {codigo}")
        else:
            print("✅ Todos los artículos fueron encontrados en la base de datos")
        
        # Retornar información sobre artículos no encontrados para el mensaje flash
        return {
            'articulos_no_encontrados': articulos_no_encontrados,
            'total_filas': len(df),
            'filas_con_precio': filas_con_precio,
            'filas_con_promo': filas_con_promo,
            'filas_con_marca': filas_con_marca
        }
        
    except Exception as e:
        print(f"❌ Error procesando archivo de mayoristas: {str(e)}")
        import traceback
        print(f"Traceback completo:\n{traceback.format_exc()}")
        raise
