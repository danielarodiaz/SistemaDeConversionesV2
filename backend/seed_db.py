# backend/seed_db.py
import logging

from database import SessionLocal, init_db
from models import (
    ArticuloGasto,
    MapeoTalle,
    Proveedor,
    Sucursal,
    SucursalVariacion,
    VariacionArticulo,
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def seed_legacy_data(db):
    """Carga proveedores, gastos, talles Crocs y sucursales OCR desde módulos Python legacy."""
    try:
        import gastos_database as gd
        import ocr_database as od
        import prov_database as pd
    except ImportError as exc:
        logger.warning("Datos legacy no disponibles (%s). Se omite esta sección.", exc)
        return

    logger.info("Iniciando carga de Proveedores (legacy)...")

    for cuit, info in gd.PROVEEDORES_DB.items():
        if "opciones" in info:
            for _, sub_info in info["opciones"].items():
                registrar_o_actualizar_prov(
                    db, cuit, sub_info["codProv"], sub_info["razonSocial"], tipo="GASTOS",
                )
        else:
            registrar_o_actualizar_prov(
                db, cuit, info["codProv"], info["razonSocial"], tipo="GASTOS",
            )

    for cuit, info in pd.cuit_proveedores.items():
        registrar_o_actualizar_prov(
            db,
            cuit,
            info["cod_prov"],
            marca=info["marca"],
            pivot=info["pivot"],
            tipo="MERCADERIA",
        )

    logger.info("Iniciando carga de Artículos de Gastos (legacy)...")
    for clave, info in gd.ARTICULOS_DB.items():
        art = db.query(ArticuloGasto).filter_by(clave_busqueda=clave).first()
        if not art:
            art = ArticuloGasto(
                clave_busqueda=clave,
                articulo_sap=info.get("articulo"),
                descripcion_sap=info.get("descripcion"),
                cuenta_contable=info.get("cuenta"),
            )
            db.add(art)
            db.flush()

        if "variaciones" in info:
            for v_text in info["variaciones"]:
                existe = db.query(VariacionArticulo).filter_by(
                    texto_variacion=v_text, articulo_id=art.id,
                ).first()
                if not existe:
                    db.add(VariacionArticulo(texto_variacion=v_text, articulo_id=art.id))

    logger.info("Iniciando carga de Talles Crocs (legacy)...")
    talles_crocs = {
        "C2/3": 19, "C4/5": 21, "C6/7": 23, "C8/9": 25, "C10/11": 27,
        "C12/13": 29, "J1": 31, "J2": 32, "J3": 33, "M3/W5": 35,
        "M4/W6": 36, "M5/W7": 37, "M6/W8": 38, "M7/W9": 39, "M8/W10": 40,
        "M9/W11": 41, "M10/W12": 42, "M11": 43, "M12": 44, "M13": 45,
    }
    for orig, dest in talles_crocs.items():
        existe = db.query(MapeoTalle).filter_by(marca_nombre="CROCS", talle_origen=orig).first()
        if not existe:
            db.add(MapeoTalle(marca_nombre="CROCS", talle_origen=orig, talle_destino=str(dest)))

    logger.info("Iniciando carga de Sucursales OCR (legacy)...")
    for prov, sucursales_dict in od.ocr_database.items():
        for cod_suc, lista_variaciones in sucursales_dict.items():
            sucursal = db.query(Sucursal).filter_by(codigo_sucursal=cod_suc).first()
            if not sucursal:
                sucursal = Sucursal(
                    provincia=prov,
                    codigo_sucursal=cod_suc,
                    nombre_sucursal=lista_variaciones[0],
                )
                db.add(sucursal)
                db.flush()

            for texto in lista_variaciones:
                existe_var = db.query(SucursalVariacion).filter_by(
                    texto_variacion=texto,
                    sucursal_id=sucursal.id,
                ).first()
                if not existe_var:
                    db.add(SucursalVariacion(texto_variacion=texto, sucursal_id=sucursal.id))


def registrar_o_actualizar_prov(db, cuit, cod_prov, razon_social=None, marca=None, pivot=None, tipo="GASTOS"):
    prov = db.query(Proveedor).filter_by(cod_prov=cod_prov).first()

    if not prov:
        db.add(Proveedor(
            cuit=cuit,
            cod_prov=cod_prov,
            razon_social=razon_social,
            marca=marca,
            pivot=pivot,
            tipo=tipo,
        ))
        return

    if razon_social:
        prov.razon_social = razon_social
    if marca:
        prov.marca = marca
    if pivot:
        prov.pivot = pivot
    if cuit:
        prov.cuit = cuit
    if tipo == "MERCADERIA":
        prov.tipo = "MERCADERIA"


def seed_db(create_tables: bool = True):
    if create_tables:
        init_db()

    db = SessionLocal()
    try:
        seed_legacy_data(db)

        from data_migration.seed_csv import seed_csv_data
        seed_csv_data(session=db)

        db.commit()
        logger.info("Proceso de seeding finalizado exitosamente.")
    except Exception as exc:
        db.rollback()
        logger.error("Error crítico en el seeding: %s", exc)
        raise
    finally:
        db.close()


if __name__ == "__main__":
    seed_db()
