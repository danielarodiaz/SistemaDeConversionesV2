import os
import pandas as pd

def process_saucony_pedido_proveedor(input_path, output_folder):
    """
    Transforma las pestañas de un archivo .xlsx en archivos .csv separados con el formato especificado.
    
    :param input_path: Ruta del archivo .xlsx de entrada.
    :param output_folder: Carpeta donde se guardarán los archivos .csv.
    """
    try:
        # Leer todas las hojas del archivo .xlsx
        sheets = pd.read_excel(input_path, sheet_name=None)
   
        transformed_data = []
        for sheet_name, data in sheets.items():
            print(f"Procesando pestaña: {sheet_name}")
            
            for _, row in data.iterrows():
                try:

                    fecha_str = pd.to_datetime(row['Fecha'], dayfirst=True).strftime('%d%m%y')

                    referencia = str(row['Remito']).zfill(4)

                    codigo_barras = str(row['EAN']).strip()

                    cantidad = int(row['Cantidad'])

                    precio = str(float(row['Costo'])).replace('.', ',')

                    establecimiento = '002' if row['Nombre'] == 'MARATHON SRL' else '001'

                    almacen = str(row['Suc']).encode('latin1').decode('utf-8', 'ignore').strip().zfill(6)  # Remover caracteres no deseados y completar a 6 dígitos

                    descuento = 10
                    
                    # Construir la fila transformada
                    transformed_row = {
                        "CAB": "ZCOC1_",
                        "REFERENCIA INTERNA": referencia,
                        "FECHA": fecha_str,
                        "COD PROVEEDOR": "SUOLA",
                        "CODIGO BARRAS": codigo_barras,
                        "CANTIDAD": cantidad,
                        "PRECIO": precio,
                        "ALMACEN": almacen,
                        "ESTABLECIMIENTO": establecimiento,
                        "DESCUENTO": descuento,
                    }
                    transformed_data.append(transformed_row)
                except Exception as e:
                    print(f"Error procesando fila: {e}")
            
            #Guarda todo en un solo archivo CSV
            if transformed_data:
                transformed_df = pd.DataFrame(transformed_data)
                transformed_df.to_csv(output_folder, index=False, sep="|",encoding='utf-8')
                
                os.chmod(output_folder, 0o777)
                
                print(f"Archivo generado: {output_folder}")
            else:
                print("No se generaron datos válidos")

    except Exception as e:
        raise RuntimeError(f"Error al procesar el archivo: {e}")
