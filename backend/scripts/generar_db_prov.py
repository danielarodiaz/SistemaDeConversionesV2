import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pandas as pd
from config import UPLOAD_FOLDER, OUTPUT_FOLDER

def generar_diccionario_proveedores(nombre_archivo):
    file_path = os.path.join(UPLOAD_FOLDER, nombre_archivo)
    df = pd.read_excel(file_path, dtype=str)
    df.columns = df.columns.str.strip()  # Elimina espacios en los nombres de columnas
    print("Columnas detectadas:", list(map(repr, df.columns)))

    cuit_proveedores = {}

    for _, row in df.iterrows():
        cuit = str(row["Número"]).strip()
        cod_prov = str(row["Cód. proveedor"]).strip()
        marca = str(row["Marca"]).strip()
        pivot = str(row["Pivot"]).strip()


        cuit_proveedores[cuit] = {
            "cod_prov": cod_prov,
            "marca": marca,
            "pivot": pivot
        }

    output_path = os.path.join(OUTPUT_FOLDER, "proveedores_db.txt")

    with open(output_path, "w", encoding="utf-8") as f:
        f.write("cuit_proveedores = {\n")
        for cuit, datos in cuit_proveedores.items():
            f.write(f'    "{cuit}": {datos},\n')
        f.write("}\n")

    print(f"Diccionario generado en: {output_path}")

if __name__ == "__main__":
    generar_diccionario_proveedores("proveedores.xlsx")
