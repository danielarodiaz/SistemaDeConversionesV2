import pandas as pd
import numpy as np
import os
from services.upload_ftp import upload_to_ftp
from config import ENVIAR_A_FTP

def process_price_bike(input_path, output_path):
    if not os.path.exists(input_path):
        raise Exception(f'Archivo no encontrado en: {input_path}')

    xls = pd.ExcelFile(input_path)
    print("Hojas encontradas:", xls.sheet_names)

    # MONDRAKER
    df_mondraker = xls.parse(sheet_name='MONDRAKER', dtype={'Código artículo': str} )
    print("Columnas MONDRAKER:", list(df_mondraker.columns))

    if 'Código artículo' not in df_mondraker.columns:
        raise Exception('No se encontró la columna Código artículo en MONDRAKER')

    df_mondraker_resultado = pd.DataFrame()
    df_mondraker_resultado['CABECRRA'] = ['LPMC1_'] * len(df_mondraker)

    def formatear_codigo_mondraker(x):
        x = str(x).strip()
        if '.' in x:
            parte_izq = x.split('.')[0]
            if len(parte_izq) == 2:
                return '0' + x
        return x

    df_mondraker_resultado['COD_GO ART_CULO'] = df_mondraker['Código artículo'].apply(formatear_codigo_mondraker)
    df_mondraker_resultado['PREC_O'] = df_mondraker.iloc[:, 11] #columna L

    # TREK
    df_trek = xls.parse(sheet_name='TREK')
    print("Columnas TREK:", list(df_trek.columns))

    if 'Código artículo' not in df_trek.columns:
        raise Exception('No se encontró la columna Código artículo en TREK')

    df_trek_resultado = pd.DataFrame()
    df_trek_resultado['CABECRRA'] = ['LPMC1_'] * len(df_trek)
    df_trek_resultado['COD_GO ART_CULO'] = df_trek['Código artículo'].astype(str).str.strip()
    
    # Redondear precios de TREK → si termina en .5 sube al siguiente entero
    df_trek_resultado['PREC_O'] = df_trek.iloc[:, 13].apply(lambda x: int(np.ceil(x)))

    # Unir ambos
    df_resultado = pd.concat([df_mondraker_resultado, df_trek_resultado], ignore_index=True)

    # Exportar temporalmente en local
    if os.path.exists(output_path):
        os.remove(output_path)

    df_resultado.to_csv(output_path, sep='|', index=False)
    print("Archivo exportado temporalmente en:", output_path)

    # Subir al FTP si está habilitado
    if ENVIAR_A_FTP:
        remote_path = f"IMPORTACIONES/PRECIOS/{os.path.basename(output_path)}"
        upload_to_ftp(output_path, remote_path)
        print("Archivo subido al FTP correctamente.")
    else:
        print("🛑 ENVIAR_A_FTP está deshabilitado. El archivo no fue enviado.")

    return output_path
