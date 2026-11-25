import pandas as pd
import os
from openpyxl import Workbook
from backend.database import SessionLocal
from backend.models import Proveedor

def generar_num(punto_venta, numero):
    return f"{str(punto_venta).zfill(4)}-{str(numero).zfill(8)}"
def process_arca_procesos_especiales(input_path, output_path):
    db = SessionLocal()
    try:
        maestro_provs = db.query(Proveedor).all()
        cuit_map = {
            p.cuit: {
                'cod_prov': p.cod_prov, 
                'marca': p.marca, 
                'pivot': p.pivot,
                'tipo_prov': p.tipo
            } for p in maestro_provs
        }
    finally:
        db.close()

    df = pd.read_excel(input_path, skiprows=1, dtype=str)
    df.columns = [col.strip() for col in df.columns]

    primera_linea = pd.read_excel(input_path, nrows=1).columns[0]
    cuit_encontrado = "30675376669" if "30675376669" in primera_linea else "OTRO"
    empresa = "MARATHON" if cuit_encontrado == "30675376669" else "BLANCO"

    pendientes = []
    resto = []

    for _, row in df.iterrows():
        cuit = str(row["Nro. Doc. Emisor"]).strip()
        emision = row["Fecha"]
        tipo_camb = str(row["Tipo Cambio"]).replace(".", ",")
        monto = str(row["Imp. Total"]).replace(".", ",")
        iva = "" if pd.isna(row["Total IVA"]) else str(row["Total IVA"]).replace(".", ",")
        netoG = "" if pd.isna(row["Neto Gravado Total"]) else str(row["Neto Gravado Total"]).replace(".", ",")
        netoNG = "" if pd.isna(row["Neto No Gravado"]) else str(row["Neto No Gravado"]).replace(".", ",")
        exentas = "" if pd.isna(row["Op. Exentas"]) else str(row["Op. Exentas"]).replace(".", ",")
        otros = "" if pd.isna(row["Otros Tributos"]) else str(row["Otros Tributos"]).replace(".", ",")
        tipo_doc = str(row.get("Tipo", "")).upper()
        
        if "CRÉDITO" in tipo_doc:
            for val in [monto, iva, netoG, netoNG, exentas, otros]:
                if val not in ["", "0", "0,00"]:
                    pass 
            monto = f"-{monto}" if monto not in ["", "0", "0,00"] else monto
            iva = f"-{iva}" if iva not in ["", "0", "0,00"] else iva
            netoG = f"-{netoG}" if netoG not in ["", "0", "0,00"] else netoG
            netoNG = f"-{netoNG}" if netoNG not in ["", "0", "0,00"] else netoNG
            exentas = f"-{exentas}" if exentas not in ["", "0", "0,00"] else exentas
            otros = f"-{otros}" if otros not in ["", "0", "0,00"] else otros
        
        num = generar_num(row["Punto de Venta"], row["Número Desde"])

        es_pendiente = False
        datos_prov = cuit_map.get(cuit)

        if datos_prov:
            tipo_prov = str(datos_prov['tipo_prov']).upper() if datos_prov['tipo_prov'] else ""
            pivot_val = str(datos_prov['pivot']).strip() if datos_prov['pivot'] else ""
            marca_val = str(datos_prov['marca']).strip() if datos_prov['marca'] else ""

            if tipo_prov != "GASTOS" and pivot_val != "" and marca_val != "":
                es_pendiente = True

        if es_pendiente:
            factura_nc = num
            if "-" in num:
                before, after = num.split("-", 1)
                before_formatted = "".join(ch for ch in before if ch.isdigit())[-4:].zfill(4)
                factura_nc = f"{before_formatted}-{after}"

            tipo = "FC" if "FACTURA" in tipo_doc else ("NC" if "CRÉDITO" in tipo_doc else ("ND" if "DÉBITO" in tipo_doc else ""))
            
            pendientes.append({
                "EMPRESA": empresa,
                "PIVOT": datos_prov["pivot"],
                "COD. PROV.": datos_prov["cod_prov"],
                "MARCA": datos_prov["marca"],
                "TIPO": tipo,
                "FACTURA/NC": factura_nc,
                "EMISION": emision,
                "SUBTOTAL": netoG,
                "MONTO": monto
            })
        else:
            resto.append({
                "FECHA": emision,
                "TIPO": row["Tipo"],
                "NUM": num,
                "NRO. DOC. EMISOR": cuit,
                "RAZÓN SOCIAL": row["Denominación Emisor"],
                "TIPO DE CAMBIO": tipo_camb,
                "MONEDA": row["Moneda"],
                "IMP. NETO GRAVADO": netoG,
                "IMP. NETO NO GRAVADO": netoNG,
                "IMP. OP. EXENTAS": exentas,
                "OTROS TRIBUTOS": otros,
                "IVA": iva,
                "TOTAL": monto
            })

    df_pendientes = pd.DataFrame(pendientes)
    df_resto = pd.DataFrame(resto)

    for d, f_col, n_col in [(df_pendientes, 'EMISION', 'FACTURA/NC'), (df_resto, 'FECHA', 'NUM')]:
        if not d.empty:
            d[f_col] = pd.to_datetime(d[f_col], dayfirst=True, errors='coerce')
            d.sort_values(by=[f_col, n_col], inplace=True)
            d[f_col] = d[f_col].dt.strftime('%d/%m/%Y')

    wb = Workbook()
    ws1 = wb.active
    ws1.title = "PENDIENTES"
    ws1.append(df_pendientes.columns.tolist())
    for fila in df_pendientes.values.tolist(): ws1.append(fila)

    ws2 = wb.create_sheet("RESTO")
    ws2.append(df_resto.columns.tolist())
    for fila in df_resto.values.tolist(): ws2.append(fila)

    wb.save(output_path)
    wb.close()
    
    print(f"✅ Proceso ARCA finalizado: {output_path}")
    return None