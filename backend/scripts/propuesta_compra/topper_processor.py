import pandas as pd
import os
import math
import zipfile
from datetime import datetime
from utils.cegid_utils import obtener_precios_cegid_por_cod_prov, obtener_codigo_barra_flexible

MESES_ES = {
    1: "ENERO", 2: "FEBRERO", 3: "MARZO", 4: "ABRIL",
    5: "MAYO", 6: "JUNIO", 7: "JULIO", 8: "AGOSTO",
    9: "SEPTIEMBRE", 10: "OCTUBRE", 11: "NOVIEMBRE", 12: "DICIEMBRE"
}

def formatear_talle(talle):
    talle = str(talle).strip()
    if talle.endswith("0") and len(talle) == 3:
        return talle[:2]
    return talle

def limpiar_material(material):
    material = str(material).strip()
    return material.lstrip("0") if material.startswith("0") else material

def generar_referencia(fecha_entrega):
    fecha_dt = datetime.strptime(fecha_entrega, "%d.%m.%Y")
    mes = MESES_ES[fecha_dt.month]
    anio = fecha_dt.year
    return f"CAL TOPPER {mes} {anio}"

def process_topper_propuesta_compra(input_path, output_path):
    df = pd.read_excel(input_path, dtype=str).fillna("")
    print("Columnas del archivo:", df.columns.tolist())
    df.columns = df.columns.str.strip()

    df["Material"] = df["Material"].apply(limpiar_material)
    df["Talle"] = df["Talle"].apply(formatear_talle)
    df["Cantidad"] = df["Cantidad"].astype(int)
    df["Fecha Pref Entrega"] = df["Fecha Pref Entrega"].str.strip()

    fecha_doc = datetime.today().strftime("%d%m%y")
    referencia_base = generar_referencia(df["Fecha Pref Entrega"].iloc[0])
    cod_proveedor = "ALSAI"

    precios_df = obtener_precios_cegid_por_cod_prov(cod_proveedor)
    precios_dict = precios_df.set_index("CodigoArticulo")["PrecioCompra"].to_dict()

    filas_resultado = []

    for _, row in df.iterrows():
        material = row["Material"]
        talle = row["Talle"]
        cantidad = row["Cantidad"]
        cliente = row["Cliente"]
        fecha_entrega = datetime.strptime(row["Fecha Pref Entrega"], "%d.%m.%Y").strftime("%d%m%y")

        if not material.isdigit():
            continue

        codigo_barra = obtener_codigo_barra_flexible(material, talle)
        if not codigo_barra:
            print(f"⚠️ Código de barra no encontrado: {material} - {talle}")
            continue

        precio = precios_dict.get(material)
        if precio is None:
            print(f"⚠️ Precio no encontrado: {material}")
            continue

        establecimiento = "002" if cliente == "1279300" else "001"

        filas_resultado.append([
            "PDCC1_",
            referencia_base,
            fecha_doc,
            cod_proveedor,
            codigo_barra,
            cantidad,
            round(precio, 2),
            "240001",
            establecimiento,
            fecha_entrega
        ])

    df_final = pd.DataFrame(filas_resultado, columns=[
        "CAB", "REFERENCIA INTERNA", "FECHA DOC", "COD PROVEEDOR",
        "CODIGO BARRAS", "CANTIDAD", "PRECIO", "ALMACEN", "ESTABLECIMIENTO", "FECHA ENTREGA"
    ])

    archivos_generados = []

    for establecimiento in df_final["ESTABLECIMIENTO"].unique():
        subset = df_final[df_final["ESTABLECIMIENTO"] == establecimiento].copy()
        total_lineas = len(subset)

        # Subdividir si hay muchas líneas
        max_lineas_por_lote = 100
        if total_lineas > max_lineas_por_lote:
            num_lotes = math.ceil(total_lineas / max_lineas_por_lote)
            base = total_lineas // num_lotes
            sobrantes = total_lineas % num_lotes
            start = 0

            for i in range(num_lotes):
                cantidad = base + (1 if i < sobrantes else 0)
                end = start + cantidad
                ref_actual = f"{referencia_base} - Parte {i+1}"
                idx = subset.iloc[start:end].index
                subset.loc[idx, "REFERENCIA INTERNA"] = ref_actual
                start = end
        else:
            subset["REFERENCIA INTERNA"] = referencia_base

        filename = f"topper_est_{establecimiento}.csv"
        filepath = os.path.join(os.path.dirname(output_path), filename)
        subset.to_csv(filepath, sep="|", index=False)
        archivos_generados.append(filepath)

    # Crear ZIP con todos los archivos generados
    zip_path = output_path.replace(".csv", ".zip")
    with zipfile.ZipFile(zip_path, "w") as zipf:
        for file in archivos_generados:
            zipf.write(file, arcname=os.path.basename(file))
            os.remove(file)  # limpiar CSV temporales

    print(f"✅ ZIP generado con {len(archivos_generados)} archivos: {zip_path}")
    return zip_path
