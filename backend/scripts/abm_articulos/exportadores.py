import csv
import os
import zipfile
from datetime import datetime
from decimal import Decimal

try:
    from backend.utils.pedido_helpers import formatear_precio
except ModuleNotFoundError:
    def formatear_precio(valor) -> str:
        return f"{round(float(valor), 2):.2f}".replace(".", ",")


ITEC_HEADER = (
    "CABECERA|Codigo_Articulo|Descripcion_para_la_Compra|Tipo_de_Producto|Desc_Tipo_de_Producto|"
    "Grupo|Desc_Grupo|Grupo_SAP_B1|Desc_Grupo_SAP_B1||||||||||Departamento|Desc_Departamento|"
    "Marca|Desc_Marca|GENERO|Desc_Genero|Silueta|Desc_Silueta|Uso|Desc_Uso|Promo|Desc_Promo|||||||||||||||"
    "Codigo_de_Barra|Talle|Desc_Talle|Valor_Talle|Des._Valor Talle|Color|Des._Color|Valor_Color|"
    "Desc._Valor_Color||||||||Proveedor_Habitual|||||||||||||||||||||CODIGO|NOMBRE|VALOR|CODIGO|VALOR|"
    "CANAL|codigoCapsula|descripcionCapsula|codigoDivision|descripcionDivision|codigoTemporada|descripcionTemporada"
).split("|")

LCOC_HEADER = "CABECERA|PERIODO|tipo|Precio|Cod Articulo".split("|")
LPMC_HEADER = "CABECERA|CODIGO_ARTICULO|PRECIO".split("|")
ITCC_HEADER = (
    "CABECERA|GA2_CODEARTICLE|GA2_LIBREARTB|GA2_ARTICLE|GA2_FAMILLENIV4|GA2_FAMILLENIV5|"
    "GA2_FAMILLENIV6|GA2_LIBREARTC|GA2_LIBREARTD|GA2_FAMILLENIV7"
).split("|")


def _valor(obj, nombre, default=""):
    valor = getattr(obj, nombre, default)
    if valor is None:
        return default
    if isinstance(valor, Decimal):
        return str(valor)
    return str(valor)


def _validar_columnas(header, rows, nombre):
    esperado = len(header)
    for idx, row in enumerate(rows, start=1):
        if len(row) != esperado:
            raise ValueError(
                f"{nombre}: fila {idx} tiene {len(row)} columnas; se esperaban {esperado}"
            )


def fila_itec(articulo):
    row = [
        "ITEC1_",
        _valor(articulo, "codigo"),
        _valor(articulo, "descripcion"),
        _valor(articulo, "tipoProducto"),
        _valor(articulo, "descripcionProducto"),
        "",
        "",
        _valor(articulo, "grupoSAP"),
        _valor(articulo, "descripcionGrupoSAP"),
    ]
    row.extend([""] * 9)
    row.extend([
        "",
        "",
        _valor(articulo, "marca"),
        _valor(articulo, "descripcionMarca"),
        _valor(articulo, "genero"),
        _valor(articulo, "descripcionGenero"),
        _valor(articulo, "silueta"),
        _valor(articulo, "descripcionSilueta"),
        _valor(articulo, "uso"),
        _valor(articulo, "descripcionUso"),
        _valor(articulo, "promo"),
        _valor(articulo, "descripcionPromo"),
    ])
    row.extend([""] * 14)
    row.extend([
        _valor(articulo, "codigoBarra"),
        _valor(articulo, "talle"),
        _valor(articulo, "descripcionTalle"),
        _valor(articulo, "valorTalle"),
        _valor(articulo, "descripcionValorTalle"),
        _valor(articulo, "color"),
        _valor(articulo, "descripcionColor"),
        _valor(articulo, "valor"),
        _valor(articulo, "descripcionValor"),
    ])
    row.extend([""] * 7)
    row.append(_valor(articulo, "nombreProveedor"))
    row.extend([""] * 20)
    row.extend([
        _valor(articulo, "codigoMedida"),
        _valor(articulo, "tipoMedida"),
        _valor(articulo, "medida"),
        _valor(articulo, "codigoGen"),
        _valor(articulo, "genero2"),
        "",
        _valor(articulo, "codigoCapsula"),
        "",
        _valor(articulo, "codigoDivision"),
        "",
        _valor(articulo, "codigoTemporada"),
        "",
    ])
    return row


def fila_comp(complementario, codigo_cruzar):
    return [
        "ITCC1_",
        _valor(complementario, "codigo"),
        _valor(complementario, "codigoEdad"),
        codigo_cruzar or _valor(complementario, "codigoBarra"),
        _valor(complementario, "codigoMaterial"),
        _valor(complementario, "codigoSegmentacionProveedor"),
        _valor(complementario, "codigoSegmentacionMarathon"),
        _valor(complementario, "codigoVidriera"),
        _valor(complementario, "codigoAnio"),
        _valor(complementario, "objetivoGeneral"),
    ]


def _precio(valor):
    if valor is None or str(valor).strip() == "":
        valor = 0
    return formatear_precio(valor)


def escribir_csv(path, header, rows):
    _validar_columnas(header, rows, os.path.basename(path))
    with open(path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.writer(f, delimiter="|", lineterminator="\n")
        writer.writerow(header)
        writer.writerows(rows)


def generar_zip_abm_articulos(articulos, complementarios, precios_compra, precios_venta, codigos_cruzar, output_folder):
    ts_nombre = datetime.now().strftime("%d%m%Y_%H%M")
    ts_zip = datetime.now().strftime("%Y%m%d_%H%M%S")
    base_paths = {
        "articulos": os.path.join(output_folder, f"ART_{ts_nombre}.csv"),
        "compra": os.path.join(output_folder, f"PCO_{ts_nombre}.csv"),
        "venta": os.path.join(output_folder, f"PVE_{ts_nombre}.csv"),
    }

    articulos_rows = [fila_itec(articulo) for articulo in articulos]
    codigos_unicos = list(dict.fromkeys(_valor(articulo, "codigo") for articulo in articulos))
    compra_rows = [
        ["LCOC1_", "PERMA", "LCMAR", _precio(precios_compra.get(codigo)), codigo]
        for codigo in codigos_unicos
    ]
    venta_rows = [
        ["LPMC1_", codigo, _precio(precios_venta.get(codigo))]
        for codigo in codigos_unicos
    ]

    escribir_csv(base_paths["articulos"], ITEC_HEADER, articulos_rows)
    escribir_csv(base_paths["compra"], LCOC_HEADER, compra_rows)
    escribir_csv(base_paths["venta"], LPMC_HEADER, venta_rows)

    zip_filename = f"ABM_ARTICULOS_{ts_zip}.zip"
    zip_path = os.path.join(output_folder, zip_filename)
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for path in base_paths.values():
            zf.write(path, os.path.basename(path))

    for path in base_paths.values():
        if os.path.exists(path):
            os.remove(path)

    return zip_path


def generar_csv_complementario_abm(complementarios, codigos_cruzar, output_folder):
    ts_nombre = datetime.now().strftime("%d%m%Y_%H%M")
    path = os.path.join(output_folder, f"ARTCOMP_{ts_nombre}.csv")
    rows = []
    codigo_actual = None
    representante_padre = None

    def agregar_padre(comp):
        if not comp:
            return
        codigo = _valor(comp, "codigo").strip()
        if not codigo:
            return
        rows.append(fila_comp(comp, codigos_cruzar.get((codigo, "")) or codigo))

    for comp in complementarios:
        codigo = _valor(comp, "codigo").strip()
        if codigo_actual is not None and codigo != codigo_actual:
            agregar_padre(representante_padre)
            representante_padre = None
        codigo_actual = codigo
        representante_padre = representante_padre or comp
        clave = (_valor(comp, "codigo").strip(), _valor(comp, "codigoBarra").strip())
        rows.append(fila_comp(comp, codigos_cruzar.get(clave) or _valor(comp, "codigoBarra")))
    agregar_padre(representante_padre)
    escribir_csv(path, ITCC_HEADER, rows)
    return path
