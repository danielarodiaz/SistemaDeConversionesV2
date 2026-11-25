import argparse
import csv
import os
from datetime import datetime
from types import SimpleNamespace

from backend.config import OUTPUT_FOLDER
from backend.scripts.abm_articulos.exportadores import ITCC_HEADER, fila_comp


def _limpiar(valor):
    return str(valor or "").strip()


def obtener_barras_cegid(codigo):
    """
    Devuelve las barras existentes en CEGID para un codigo de articulo.
    Se usa solo como ayuda de prueba para simular un complementario real.
    """
    codigo = _limpiar(codigo)
    if not codigo:
        return []

    conexion = None
    try:
        from backend.services.cegid_connector import conectar_cegid

        conexion = conectar_cegid()
        if not conexion:
            return []

        cursor = conexion.cursor()
        cursor.execute(
            """
            SELECT GA_CODEBARRE
            FROM MARAPROD24.dbo.ARTICLE
            WHERE GA_CODEARTICLE = ?
              AND GA_CODEBARRE IS NOT NULL
              AND LTRIM(RTRIM(GA_CODEBARRE)) <> ''
            ORDER BY GA_ARTICLE
            """,
            (codigo,),
        )
        barras = []
        for row in cursor.fetchall():
            barra = _limpiar(row[0])
            if barra and barra not in barras:
                barras.append(barra)
        return barras
    except Exception as exc:
        print(f"No se pudieron obtener barras desde CEGID: {exc}")
        return []
    finally:
        if conexion:
            conexion.close()


def construir_complementarios(codigo, barras, edad, material, seg_proveedor, seg_marathon, vidriera, anio, objetivo):
    codigo = _limpiar(codigo)
    return [
        SimpleNamespace(
            codigo=codigo,
            codigoBarra=_limpiar(barra),
            codigoEdad=_limpiar(edad),
            codigoMaterial=_limpiar(material),
            codigoSegmentacionProveedor=_limpiar(seg_proveedor),
            codigoSegmentacionMarathon=_limpiar(seg_marathon),
            codigoVidriera=_limpiar(vidriera),
            codigoAnio=_limpiar(anio),
            objetivoGeneral=_limpiar(objetivo),
        )
        for barra in barras
    ]


def escribir_artcomp_prueba(path, complementarios, codigos_cruzar):
    rows = []
    for comp in complementarios:
        clave = (_limpiar(comp.codigo), _limpiar(comp.codigoBarra))
        rows.append(fila_comp(comp, codigos_cruzar.get(clave) or comp.codigoBarra))

    if complementarios:
        padre = complementarios[0]
        codigo = _limpiar(padre.codigo)
        rows.append(fila_comp(padre, codigos_cruzar.get((codigo, "")) or codigo))

    with open(path, "w", newline="", encoding="utf-8-sig") as file:
        writer = csv.writer(file, delimiter="|", lineterminator="\n")
        writer.writerow(ITCC_HEADER)
        writer.writerows(rows)
    return path


def generar_artcomp_prueba(complementarios, codigos_cruzar, output_folder=OUTPUT_FOLDER):
    os.makedirs(output_folder, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = os.path.join(output_folder, f"ARTCOMP_TEST_{timestamp}.csv")
    return escribir_artcomp_prueba(path, complementarios, codigos_cruzar)


def _leer_input_prueba(input_path):
    with open(input_path, newline="", encoding="utf-8-sig") as file:
        muestra = file.read(2048)
        file.seek(0)
        dialect = csv.Sniffer().sniff(muestra, delimiters=";,|,\t")
        tiene_header = csv.Sniffer().has_header(muestra)
        if tiene_header:
            reader = csv.DictReader(file, dialect=dialect)
            rows = list(reader)
        else:
            reader = csv.reader(file, dialect=dialect)
            rows = [
                {"codigo": row[0] if len(row) > 0 else "", "codigoBarra": row[1] if len(row) > 1 else ""}
                for row in reader
            ]
    return rows


def procesar(input_path, output_path):
    """
    Procesador de prueba: recibe un CSV con codigo y codigoBarra/barra, cruza contra CEGID
    y genera un ARTCOMP de simulacion en output_path. No toca la base local.
    """
    rows = _leer_input_prueba(input_path)
    if not rows:
        raise ValueError("El archivo de prueba no tiene filas.")

    codigo = _limpiar(rows[0].get("codigo") or rows[0].get("Codigo") or rows[0].get("codigoArticulo"))
    barras = [
        _limpiar(row.get("codigoBarra") or row.get("Codigo Barra") or row.get("barra") or row.get("EAN"))
        for row in rows
    ]
    barras = [barra for barra in barras if barra]
    if not codigo or not barras:
        raise ValueError("El archivo debe tener codigo y al menos un codigoBarra/barra.")

    primera = rows[0]
    complementarios = construir_complementarios(
        codigo=codigo,
        barras=barras,
        edad=primera.get("edad") or primera.get("Edad") or "ADU",
        material=primera.get("material") or primera.get("Material") or "PEN",
        seg_proveedor=primera.get("segProveedor") or primera.get("Segmentacion Proveedor") or "PEN",
        seg_marathon=primera.get("segMarathon") or primera.get("Segmentacion Marathon") or "PEN",
        vidriera=primera.get("vidriera") or primera.get("Vidriera") or "N/A",
        anio=primera.get("anio") or primera.get("Año") or primera.get("Anio") or "26",
        objetivo=primera.get("objetivo") or primera.get("Objetivo Gen") or "N/A",
    )
    pares = [(codigo, barra) for barra in barras] + [(codigo, "")]
    from backend.utils.cegid_utils import obtener_codigos_cruzar_articulos

    codigos_cruzar = obtener_codigos_cruzar_articulos(pares)
    escribir_artcomp_prueba(output_path, complementarios, codigos_cruzar)
    return output_path


def probar_cruce(
    codigo,
    barras,
    usar_barras_cegid=False,
    edad="ADU",
    material="PEN",
    seg_proveedor="PEN",
    seg_marathon="PEN",
    vidriera="N/A",
    anio="26",
    objetivo="N/A",
    generar_csv=True,
):
    codigo = _limpiar(codigo)
    barras = [_limpiar(barra) for barra in barras if _limpiar(barra)]

    if usar_barras_cegid:
        barras = obtener_barras_cegid(codigo)

    if not codigo:
        raise ValueError("Tenes que indicar un codigo de articulo.")
    if not barras:
        raise ValueError("Tenes que indicar al menos una barra o usar --usar-barras-cegid.")

    complementarios = construir_complementarios(
        codigo,
        barras,
        edad,
        material,
        seg_proveedor,
        seg_marathon,
        vidriera,
        anio,
        objetivo,
    )
    pares = [(codigo, barra) for barra in barras] + [(codigo, "")]
    from backend.utils.cegid_utils import obtener_codigos_cruzar_articulos

    codigos_cruzar = obtener_codigos_cruzar_articulos(pares)
    path = generar_artcomp_prueba(complementarios, codigos_cruzar) if generar_csv else None

    resultados = []
    for codigo_par, barra in pares:
        fallback = codigo_par if not barra else barra
        resultados.append({
            "codigo": codigo_par,
            "codigoBarra": barra,
            "ga_article": codigos_cruzar.get((codigo_par, barra)) or fallback,
            "match_cegid": (codigo_par, barra) in codigos_cruzar,
            "tipo": "padre" if not barra else "hijo",
        })

    return {
        "csv": path,
        "resultados": resultados,
        "matches": sum(1 for row in resultados if row["match_cegid"]),
        "fallbacks": sum(1 for row in resultados if not row["match_cegid"]),
    }


def main():
    parser = argparse.ArgumentParser(
        description="Prueba el cruce ABM Articulos contra CEGID y genera un ARTCOMP de simulacion."
    )
    parser.add_argument("--codigo", required=True, help="Codigo de articulo existente en CEGID.")
    parser.add_argument("--barra", action="append", default=[], help="Codigo de barra. Se puede repetir.")
    parser.add_argument("--usar-barras-cegid", action="store_true", help="Toma todas las barras existentes en CEGID para el codigo.")
    parser.add_argument("--edad", default="ADU")
    parser.add_argument("--material", default="PEN")
    parser.add_argument("--seg-proveedor", default="PEN")
    parser.add_argument("--seg-marathon", default="PEN")
    parser.add_argument("--vidriera", default="N/A")
    parser.add_argument("--anio", default="26")
    parser.add_argument("--objetivo", default="N/A")
    parser.add_argument("--sin-csv", action="store_true", help="Solo muestra el cruce, sin generar archivo.")
    args = parser.parse_args()

    resultado = probar_cruce(
        codigo=args.codigo,
        barras=args.barra,
        usar_barras_cegid=args.usar_barras_cegid,
        edad=args.edad,
        material=args.material,
        seg_proveedor=args.seg_proveedor,
        seg_marathon=args.seg_marathon,
        vidriera=args.vidriera,
        anio=args.anio,
        objetivo=args.objetivo,
        generar_csv=not args.sin_csv,
    )

    print("tipo|codigo|codigoBarra|GA_ARTICLE|match_cegid")
    for row in resultado["resultados"]:
        print(
            f"{row['tipo']}|{row['codigo']}|{row['codigoBarra']}|"
            f"{row['ga_article']}|{row['match_cegid']}"
        )
    print(f"Matches CEGID: {resultado['matches']}")
    print(f"Fallbacks: {resultado['fallbacks']}")
    if resultado["csv"]:
        print(f"CSV generado: {resultado['csv']}")


if __name__ == "__main__":
    main()
