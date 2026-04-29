import pandas as pd

def process_braku_pedido_proveedor(input_path, output_folder):
    try:
        data = pd.read_excel(input_path)
        # Normalizar nombres de columnas a formato capitalizado (primera letra mayúscula)
        #data.columns = data.columns.str.capitalize()
        
        transformed_data = []
        
        for _, row in data.iterrows():
            try:
                fecha_str = pd.to_datetime(row['Fecha'], dayfirst=True).strftime('%d%m%y')
                
                referencia_raw = str(row['Remito']).strip()

                # Separar por el guion
                parte1, parte2 = referencia_raw.split('-')

                # Limpiar espacios y completar con ceros
                parte1 = parte1.strip().zfill(4)
                parte2 = parte2.strip().zfill(8)

                # Formatear resultado final
                referencia_formateada = f"{parte1}-{parte2}"

                codigo_barras = str(row['EAN']).strip().replace('/','-')
                
                cantidad = int(row['Cantidad'])
                
                precio = f"{float(row['PreUni']):.2f}".replace('.', ',') #El precio siempre tendra dos decimales
                
                establecimiento = '002' if row['Empresa'].replace(".", "").strip().upper() == 'MARATHON SRL' else '001'
                
                almacen = str(int(row['Suc'])).zfill(6)
                
                transformed_row = {
                    "CAB": "ZCOC1_",
                    "REFERENCIA INTERNA": referencia_formateada,
                    "FECHA": fecha_str,
                    "COD PROVEEDOR": "BRAKU",
                    "CODIGO BARRAS": codigo_barras,
                    "CANTIDAD": cantidad,
                    "PRECIO": precio,
                    "ALMACEN": almacen,
                    "ESTABLECIMIENTO": establecimiento,
                    "DESCUENTO": 10,
                }
                transformed_data.append(transformed_row)
            except Exception as e:
                print(f"Error procesando fila: {e}")
                
        if transformed_data:
            transformed_df = pd.DataFrame(transformed_data)
            transformed_df.to_csv(output_folder, index=False, sep="|", encoding="utf-8-sig")
            print(f"Archivo generado correctamente en: {output_folder}")
        else:
            print("No se generaron datos válidos para exportar.")
    except Exception as e:
        print(f"Error al procesar el archivo: {e}")
        raise RuntimeError(f"Error al procesar el archivo: {e}")              
            
            