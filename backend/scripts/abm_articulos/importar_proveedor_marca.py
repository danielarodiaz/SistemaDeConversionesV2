import argparse
import csv
import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))

from backend.models import Proveedor, ProveedorMarca, marca
from backend.services.unit_of_work import UnitOfWork


def _limpiar(valor):
    return str(valor or "").strip()


def _valor(row, *nombres):
    for nombre in nombres:
        if nombre in row and _limpiar(row[nombre]):
            return _limpiar(row[nombre])
    return ""


def _leer_csv(path):
    with open(path, newline="", encoding="utf-8-sig") as file:
        muestra = file.read(2048)
        file.seek(0)
        dialect = csv.Sniffer().sniff(muestra, delimiters=";,|,\t")
        return list(csv.DictReader(file, dialect=dialect))


def importar_relaciones(path):
    rows = _leer_csv(path)
    if not rows:
        raise ValueError("El CSV no tiene filas.")

    resumen = {
        "creadas": 0,
        "existentes": 0,
        "errores": [],
    }

    with UnitOfWork() as uow:
        for numero, row in enumerate(rows, start=2):
            cod_prov = _valor(row, "cod_prov", "codigoProveedor", "proveedor", "Proveedor")
            codigo_marca = _valor(row, "codigoMarca", "cod_marca", "marca", "Marca")
            if not cod_prov or not codigo_marca:
                resumen["errores"].append(f"Fila {numero}: faltan cod_prov/codigoMarca.")
                continue

            proveedor = (
                uow.session.query(Proveedor)
                .filter(Proveedor.cod_prov == cod_prov)
                .first()
            )
            marca_obj = (
                uow.session.query(marca)
                .filter(marca.codigoMarca == codigo_marca)
                .first()
            )
            if not proveedor:
                resumen["errores"].append(f"Fila {numero}: proveedor no encontrado ({cod_prov}).")
                continue
            if not marca_obj:
                resumen["errores"].append(f"Fila {numero}: marca no encontrada ({codigo_marca}).")
                continue

            existente = (
                uow.session.query(ProveedorMarca)
                .filter(
                    ProveedorMarca.proveedor_id == proveedor.id,
                    ProveedorMarca.marca_id == marca_obj.id,
                )
                .first()
            )
            if existente:
                existente.activo = 1
                resumen["existentes"] += 1
                continue

            uow.session.add(ProveedorMarca(
                proveedor_id=proveedor.id,
                marca_id=marca_obj.id,
                activo=1,
            ))
            resumen["creadas"] += 1

    return resumen


def main():
    parser = argparse.ArgumentParser(description="Importa relaciones proveedor-marca para ABM Articulos.")
    parser.add_argument("csv_path", help="CSV con columnas cod_prov,codigoMarca.")
    args = parser.parse_args()

    resumen = importar_relaciones(args.csv_path)
    print(f"Relaciones creadas: {resumen['creadas']}")
    print(f"Relaciones ya existentes/reactivadas: {resumen['existentes']}")
    if resumen["errores"]:
        print("Errores:")
        for error in resumen["errores"]:
            print(f"- {error}")


if __name__ == "__main__":
    main()
