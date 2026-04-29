import os
import zipfile
import pandas as pd
from typing import List, Dict, Tuple, Optional
from backend.utils.cegid_utils import obtener_costos_por_codigos_barras


def _normalizar_precio(valor) -> Optional[float]:
    if valor is None:
        return None
    s = str(valor).strip()
    if s == "":
        return None
    s = s.replace("$", "").replace(" ", "")
    s = s.replace(",", ".")
    try:
        return float(s)
    except Exception:
        return None


def _procesar_df_para_cb_precio(df: pd.DataFrame) -> List[Dict[str, float]]:
    filas: List[Dict[str, float]] = []
    df = df.copy()
    df.columns = [str(c).strip().upper() for c in df.columns]

    posibles_cb = ["CODIGO BARRAS", "CODIGO_BARRAS", "EAN", "EAN/GTIN", "COD BARRAS"]
    posibles_precio = ["PRECIO", "PRECIO UNITARIO", "UNIT PRICE", "FAB", "PRECIO TRAS EL DESCUENTO"]

    col_cb = next((c for c in posibles_cb if c in df.columns), None)
    col_precio = next((c for c in posibles_precio if c in df.columns), None)
    if not col_cb or not col_precio:
        return filas

    for i, (_, r) in enumerate(df.iterrows()):
        codigo_barras = str(r[col_cb]).strip() if pd.notna(r[col_cb]) else ""
        precio_raw = r[col_precio]
        precio_val = _normalizar_precio(precio_raw)
        if not codigo_barras:
            continue
        if precio_val is None:
            continue
        filas.append({"CODIGO BARRAS": codigo_barras, "PRECIO": precio_val})
    return filas


def extraer_filas_cb_precio_desde_salida(path_salida: str) -> List[Dict[str, float]]:
    filas: List[Dict[str, float]] = []
    if isinstance(path_salida, str) and path_salida.endswith('.zip') and os.path.exists(path_salida):
        with zipfile.ZipFile(path_salida, 'r') as zf:
            for info in zf.infolist():
                if info.filename.lower().endswith('.csv'):
                    with zf.open(info) as f:
                        try:
                            df = pd.read_csv(f, sep='|', dtype=str, encoding='utf-8')
                        except Exception:
                            f.seek(0)
                            df = pd.read_csv(f, sep='|', dtype=str, encoding='latin1')
                        filas.extend(_procesar_df_para_cb_precio(df))
    else:
        if os.path.exists(path_salida) and path_salida.lower().endswith('.csv'):
            try:
                df = pd.read_csv(path_salida, sep='|', dtype=str, encoding='utf-8')
            except Exception:
                df = pd.read_csv(path_salida, sep='|', dtype=str, encoding='latin1')
            filas.extend(_procesar_df_para_cb_precio(df))
    return filas


def generar_xlsx_diferencias(diff_rows: List[Dict[str, float]], destino_path: str) -> None:
    cols = ["CODIGO ARTICULO", "DESCRIPCION", "PRECIO CEGID", "PRECIO PROVEEDOR"]
    df = pd.DataFrame(diff_rows, columns=cols)
    with pd.ExcelWriter(destino_path, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='DIFERENCIAS')


def controlar_precios_y_empacar(output_path: str, now_str: str, output_folder: str, tipo: str, zip_path_or_none: Optional[str] = None) -> Optional[Tuple[str, str]]:
    """
    Corre control de precios para salidas de tipo pedido/propuesta.

    Retorna:
      - ("zip", nombre_zip) si se generó o actualizó un ZIP con diferencias
      - None si no hubo diferencias o no se pudo consultar CEGID
    """
    if tipo not in ("pedido", "propuesta"):
        return None

    path_lectura = zip_path_or_none if (zip_path_or_none and os.path.exists(zip_path_or_none)) else output_path

    filas = extraer_filas_cb_precio_desde_salida(path_lectura)
    if not filas:
        return None

    codigos_barras = [f["CODIGO BARRAS"] for f in filas]
    costos_por_cb = obtener_costos_por_codigos_barras(codigos_barras)
    if not costos_por_cb:
        return None

    diferencias: List[Dict[str, float]] = []
    vistos_articulos: set = set()
    for i, fila in enumerate(filas):
        cb = fila["CODIGO BARRAS"]
        precio_prov = fila["PRECIO"]
        datos = costos_por_cb.get(cb)
        if not datos:
            continue
        codigo_articulo, precio_cegid, descripcion = datos if len(datos) == 3 else (datos[0], datos[1], "")
        if precio_cegid is None:
            continue
        if codigo_articulo in vistos_articulos:
            continue
        if precio_prov != float(precio_cegid):
            vistos_articulos.add(codigo_articulo)
            diferencias.append({
                "CODIGO ARTICULO": codigo_articulo,
                "DESCRIPCION": descripcion,
                "PRECIO CEGID": round(float(precio_cegid), 2),
                "PRECIO PROVEEDOR": round(float(precio_prov), 2)
            })

    if not diferencias:
        return None

    # Generar XLSX de diferencias
    diff_name = f"PRECIOS_DIFERENTES_{now_str}.xlsx"
    diff_path = os.path.join(output_folder, diff_name)
    generar_xlsx_diferencias(diferencias, diff_path)

    # Generar PC_*.csv deduplicado por artículo
    pc_name = f"PC_{now_str}.csv"
    pc_path = os.path.join(output_folder, pc_name)
    pc_cols = ["Cabecera", "PERIODO", "tipo", "Precio", "Cod Articulo"]
    pc_rows = []
    vistos_pc: set = set()
    for d in diferencias:
        cod = d["CODIGO ARTICULO"]
        if cod in vistos_pc:
            continue
        vistos_pc.add(cod)
        pc_rows.append({
            "Cabecera": "LCOC1_",
            "PERIODO": "PERMA",
            "tipo": "LCMAR",
            "Precio": d["PRECIO PROVEEDOR"],
            "Cod Articulo": cod,
        })
    pd.DataFrame(pc_rows, columns=pc_cols).to_csv(pc_path, index=False, sep='|', encoding='utf-8-sig')

    # Empaquetar en ZIP (agregar a existente o crear uno nuevo)
    if path_lectura.endswith('.zip') and os.path.exists(path_lectura):
        with zipfile.ZipFile(path_lectura, 'a') as zf:
            zf.write(diff_path, arcname=os.path.basename(diff_path))
            zf.write(pc_path, arcname=os.path.basename(pc_path))
        try:
            os.remove(diff_path)
            os.remove(pc_path)
        except Exception:
            pass
        return ("zip", os.path.basename(path_lectura))
    else:
        zip_name = os.path.basename(output_path).replace('.csv', '.zip')
        zip_path = os.path.join(output_folder, zip_name)
        with zipfile.ZipFile(zip_path, 'w') as zf:
            if os.path.exists(output_path):
                zf.write(output_path, arcname=os.path.basename(output_path))
            zf.write(diff_path, arcname=os.path.basename(diff_path))
            zf.write(pc_path, arcname=os.path.basename(pc_path))
        try:
            os.remove(diff_path)
            os.remove(pc_path)
        except Exception:
            pass
        return ("zip", os.path.basename(zip_path))


