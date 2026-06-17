"""
Carga los CSV de data_migration a las tablas definidas en models.py.
"""
import io
import logging
import re
from decimal import Decimal, InvalidOperation
from pathlib import Path

import pandas as pd
from sqlalchemy import text

from database import SessionLocal
from models import (
    Articulo,
    ArticuloComplementario,
    Proveedor,
    TalleMaestro,
    año,
    canal,
    capsula,
    color,
    division,
    edad,
    genero,
    marca,
    markup,
    material,
    objetivoGeneral,
    precioCompra,
    precioVenta,
    promo,
    sap,
    segmentacionMarathon,
    segmentacionProveedor,
    silueta,
    temporada,
    tipoProducto,
    uso,
    vidriera,
)

logger = logging.getLogger(__name__)

DATA_DIR = Path(__file__).resolve().parent
CSV_ENCODINGS = ("utf-8-sig", "utf-8", "cp1252", "latin-1")
MOJIBAKE_RE = re.compile(r"(?:Ã.|Â.|â..|�)")


def _is_phpmyadmin_export(raw_text: str) -> bool:
    """Detecta exports de phpMyAdmin con comillas dobles escapadas dentro de la fila."""
    first_line = next((line.strip() for line in raw_text.splitlines() if line.strip()), "")
    if not (first_line.startswith('"') and first_line.endswith('"')):
        return False
    return '""' in first_line[1:-1]


def _normalize_phpmyadmin_line(line: str) -> str | None:
    line = line.strip()
    if not line:
        return None
    if line.startswith('"') and line.endswith('"'):
        line = line[1:-1]
    return line.replace('""', '"')


def _repair_mojibake(value: str) -> str:
    """Corrige texto UTF-8 que fue interpretado como cp1252/latin-1."""
    if not MOJIBAKE_RE.search(value):
        return value

    candidates = [value]
    for source_encoding in ("cp1252", "latin-1"):
        try:
            candidates.append(value.encode(source_encoding).decode("utf-8"))
        except UnicodeError:
            continue

    return min(candidates, key=lambda candidate: len(MOJIBAKE_RE.findall(candidate)))


def _read_csv(filename: str) -> pd.DataFrame:
    path = DATA_DIR / filename
    if not path.exists():
        logger.warning("Archivo no encontrado: %s", path)
        return pd.DataFrame()

    # Data Engineering Tip: Priorizamos UTF-8 para evitar falsos positivos de doble decodificación
    read_kwargs = {
        "dtype": str, 
        "keep_default_na": False, 
        "on_bad_lines": "skip",  # Si una línea viene deforme del export, la saltea en vez de romper
        "engine": "python"       # Motor ultra-resiliente para strings de phpMyAdmin
    }

    last_error = None
    for encoding in CSV_ENCODINGS:
        try:
            raw_text = path.read_text(encoding=encoding)
        except UnicodeDecodeError as exc:
            last_error = exc
            continue

        try:
            if _is_phpmyadmin_export(raw_text):
                lines = [
                    normalized
                    for line in raw_text.splitlines()
                    if (normalized := _normalize_phpmyadmin_line(line))
                ]
                df = pd.read_csv(io.StringIO("\n".join(lines)), **read_kwargs)
            else:
                df = pd.read_csv(io.StringIO(raw_text), **read_kwargs)

            df.columns = [str(c).strip() for c in df.columns]
            return df
        except pd.errors.ParserError as exc:
            last_error = exc
            logger.warning("Reintentando %s con parser alternativo por error: %s", filename, exc)

            # Fallback robusto: Forzar normalización de líneas phpMyAdmin
            try:
                lines = [
                    normalized
                    for line in raw_text.splitlines()
                    if (normalized := _normalize_phpmyadmin_line(line))
                ]
                df = pd.read_csv(io.StringIO("\n".join(lines)), **read_kwargs)
                df.columns = [str(c).strip() for c in df.columns]
                return df
            except pd.errors.ParserError as fallback_exc:
                last_error = fallback_exc

    raise last_error or FileNotFoundError(path)


def _clean(value):
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    text_value = str(value).strip()
    if text_value.lower() in {"", "nan", "none", "null"}:
        return None
    return _repair_mojibake(text_value)


def _to_int(value):
    cleaned = _clean(value)
    if cleaned is None:
        return None
    return int(float(cleaned))


def _to_decimal(value):
    cleaned = _clean(value)
    if cleaned is None:
        return None
    try:
        return Decimal(cleaned.replace(",", "."))
    except (InvalidOperation, ValueError):
        return None


def _set_identity_insert(session, table_name: str, enabled: bool):
    flag = "ON" if enabled else "OFF"
    session.execute(text(f"SET IDENTITY_INSERT [{table_name}] {flag}"))


def _seed_simple_catalog(session, model, csv_file: str, field_map: dict, identity: bool = True):
    """
    field_map: {atributo_modelo: columna_csv}
    """
    df = _read_csv(csv_file)
    if df.empty:
        logger.info("  %s: sin datos, se omite.", csv_file)
        return 0

    table_name = model.__tablename__
    inserted = 0

    if identity:
        _set_identity_insert(session, table_name, True)

    try:
        for _, row in df.iterrows():
            row_id = _to_int(row.get("id"))
            if row_id is None:
                continue

            if session.get(model, row_id):
                continue

            kwargs = {"id": row_id}
            for model_field, csv_col in field_map.items():
                kwargs[model_field] = _clean(row.get(csv_col))

            session.add(model(**kwargs))
            inserted += 1

        session.flush()
    except Exception:
        session.rollback()
        if identity:
            _set_identity_insert(session, table_name, False)
        raise
    else:
        if identity:
            _set_identity_insert(session, table_name, False)

    logger.info("  %s: %d registros insertados.", csv_file, inserted)
    return inserted


def seed_catalogos(session):
    logger.info("Cargando catálogos ABM...")

    total = 0
    total += _seed_simple_catalog(
        session, año, "anio.csv",
        {"codigoAnio": "codigoAño", "descripcionAño": "descripcionAño"},
    )
    total += _seed_simple_catalog(
        session, canal, "canal.csv",
        {"codigoCanal": "canal", "descripcionCanal": "descripcion"},
    )
    total += _seed_simple_catalog(
        session, capsula, "capsulas.csv",
        {"codigoCapsula": "codigoCapsula", "descripcionCapsula": "descripcionCapsula"},
    )
    total += _seed_simple_catalog(
        session, color, "color.csv",
        {
            "codigoColor": "color",
            "descripcionColor": "descripcionColor",
            "valor": "valor",
            "descripcionValor": "descripcionValor",
        },
    )
    total += _seed_simple_catalog(
        session, division, "division.csv",
        {"codigoDivision": "codigoDivision", "descripcionDivision": "descripcionDivision"},
    )
    total += _seed_simple_catalog(
        session, edad, "edad.csv",
        {"codigoEdad": "codigoEdad", "descripcionEdad": "descripcionEdad"},
    )
    total += _seed_simple_catalog(
        session, genero, "genero.csv",
        {"codigoGenero": "genero", "descripcionGenero": "descripcion"},
    )
    total += _seed_simple_catalog(
        session, material, "material.csv",
        {"codigoMaterial": "codigoMaterial", "descripcionMaterial": "descripcionMaterial"},
    )
    total += _seed_simple_catalog(
        session, objetivoGeneral, "objetivogen.csv",
        {"codigoObjetivoGeneral": "objetivo", "descripcionObjetivoGeneral": "descripcion"},
    )
    total += _seed_simple_catalog(
        session, promo, "promo.csv",
        {"codigoPromo": "codigoPromo", "descripcionPromo": "descripcionPromo"},
    )
    total += _seed_simple_catalog(
        session, sap, "sap.csv",
        {"codigoGrupoSap": "grupoSAP", "descripcionGrupoSap": "descripcion"},
    )
    total += _seed_simple_catalog(
        session, segmentacionMarathon, "segmentacion_marathon.csv",
        {
            "codigoSegmentacionMarathon": "codigoSegmentacion",
            "descripcionSegmentacionMarathon": "descripcionSegmentacion",
        },
    )
    total += _seed_simple_catalog(
        session, segmentacionProveedor, "segmentacion_proveedor.csv",
        {
            "codigoSegmentacionProveedor": "codigoSegmentacion",
            "descripcionSegmentacionProveedor": "descripcionSegmentacion",
        },
    )
    total += _seed_simple_catalog(
        session, silueta, "silueta.csv",
        {"codigoSilueta": "silueta", "descripcionSilueta": "descripcion"},
    )
    total += _seed_simple_catalog(
        session, temporada, "temporada.csv",
        {"codigoTemporada": "codigoTemporada", "descripcionTemporada": "descripcionTemporada"},
    )
    total += _seed_simple_catalog(
        session, tipoProducto, "tipoproducto.csv",
        {"codigoTipoProducto": "tipo", "descripcionTipoProducto": "descripcion"},
    )
    total += _seed_simple_catalog(
        session, uso, "uso.csv",
        {"codigoUso": "uso", "descripcionUso": "descripcion"},
    )
    total += _seed_simple_catalog(
        session, vidriera, "vidriera.csv",
        {"codigoVidriera": "codigoVidriera", "descripcionVidriera": "descripcionVidriera"},
    )

    return total


def _build_marca_lookup(registros_marca):
    """Permite resolver marca por código o por descripción (marckup.csv usa nombres largos)."""
    lookup = {}
    for registro in registros_marca:
        lookup[registro.codigoMarca] = registro.id
        if registro.descripcionMarca:
            lookup[registro.descripcionMarca.upper()] = registro.id
    return lookup


def _resolve_marca_id(codigo_o_nombre, lookup):
    clave = _clean(codigo_o_nombre)
    if not clave:
        return None

    marca_id = lookup.get(clave)
    if marca_id is not None:
        return marca_id

    return lookup.get(clave.upper())


def seed_proveedores(session):
    logger.info("Cargando proveedores...")

    df = _read_csv("proveedor.csv")
    if df.empty:
        logger.info("  proveedor.csv: sin datos, se omite.")
        return 0

    inserted = 0
    seen_codigos = set()
    _set_identity_insert(session, Proveedor.__tablename__, True)
    try:
        for _, row in df.iterrows():
            row_id = _to_int(row.get("id"))
            nombre = _clean(row.get("nombre"))
            if row_id is None or not nombre:
                continue

            nombre_key = nombre.upper()
            if nombre_key in seen_codigos:
                continue
            seen_codigos.add(nombre_key)

            if session.get(Proveedor, row_id):
                continue

            existing = session.query(Proveedor).filter_by(cod_prov=nombre).first()
            if existing:
                continue

            session.add(Proveedor(
                id=row_id,
                cod_prov=nombre,
                razon_social=nombre,
                tipo="MERCADERIA",
            ))
            inserted += 1

        session.flush()
    finally:
        _set_identity_insert(session, Proveedor.__tablename__, False)

    logger.info("  proveedor.csv: %d registros insertados.", inserted)
    return inserted


def seed_marcas_y_markups(session):
    logger.info("Cargando marcas y markups...")

    df_marcas = _read_csv("marca.csv")
    marcas_insertadas = 0

    if not df_marcas.empty:
        _set_identity_insert(session, marca.__tablename__, True)
        try:
            for _, row in df_marcas.iterrows():
                row_id = _to_int(row.get("id"))
                codigo = _clean(row.get("marca"))
                if row_id is None or not codigo:
                    continue

                if session.get(marca, row_id):
                    continue

                session.add(marca(
                    id=row_id,
                    codigoMarca=codigo,
                    descripcionMarca=_clean(row.get("descripcion")),
                ))
                marcas_insertadas += 1

            session.flush()
        finally:
            _set_identity_insert(session, marca.__tablename__, False)

    marca_lookup = _build_marca_lookup(session.query(marca).all())

    df_markups = _read_csv("marckup.csv")
    markups_insertados = 0

    if not df_markups.empty:
        _set_identity_insert(session, markup.__tablename__, True)
        try:
            for _, row in df_markups.iterrows():
                row_id = _to_int(row.get("id"))
                codigo_marca = _clean(row.get("marca"))
                if row_id is None or not codigo_marca:
                    continue

                if session.get(markup, row_id):
                    continue

                marca_id = _resolve_marca_id(codigo_marca, marca_lookup)
                if marca_id is None:
                    logger.warning(
                        "  markup id=%s: marca '%s' no encontrada, se omite.",
                        row_id, codigo_marca,
                    )
                    continue

                session.add(markup(
                    id=row_id,
                    marca_id=marca_id,
                    tipoProducto=_clean(row.get("tipo_prod")),
                    markup=_to_decimal(row.get("marckup")),
                ))
                markups_insertados += 1

            session.flush()
        finally:
            _set_identity_insert(session, markup.__tablename__, False)

    logger.info("  marca.csv: %d registros insertados.", marcas_insertadas)
    logger.info("  marckup.csv: %d registros insertados.", markups_insertados)
    return marcas_insertadas + markups_insertados


def seed_talles(session):
    logger.info("Cargando talles maestros...")

    df = _read_csv("talle.csv")
    if df.empty:
        logger.info("  talle.csv: sin datos, se omite.")
        return 0

    inserted = 0
    for _, row in df.iterrows():
        row_id = _to_int(row.get("id"))
        if row_id is None:
            continue

        if session.get(TalleMaestro, row_id):
            continue

        session.add(TalleMaestro(
            id=row_id,
            codigoBarra=_clean(row.get("codigoBarra")),
            codigoTalle=_clean(row.get("talle")),
            descripcionTalle=_clean(row.get("descripcionTalle")),
            valorTalle=_clean(row.get("valorTalle")),
            descripcionValorTalle=_clean(row.get("descripcionValTalle")),
            codigoMedida=_clean(row.get("codigoMedida")),
            tipoMedida=_clean(row.get("tipoMedida")),
            medida=_clean(row.get("medida")),
            codigoGen=_clean(row.get("codigoGen")),
            genero=_clean(row.get("genero")),
        ))
        inserted += 1

    session.flush()
    logger.info("  talle.csv: %d registros insertados.", inserted)
    return inserted


def seed_articulos(session):
    logger.info("Cargando artículos...")

    df = _read_csv("tabla.csv")
    if df.empty:
        logger.info("  tabla.csv: sin datos, se omite.")
        return 0

    articulo_fields = [
        "codigo", "descripcion", "tipoProducto", "descripcionProducto",
        "grupoSAP", "descripcionGrupoSAP", "marca", "descripcionMarca",
        "genero", "descripcionGenero", "silueta", "descripcionSilueta",
        "uso", "descripcionUso", "codigoBarra", "talle", "descripcionTalle",
        "valorTalle", "descripcionValorTalle", "color", "descripcionColor",
        "valor", "descripcionValor", "nombreProveedor", "codigoMedida",
        "tipoMedida", "medida", "codigoGen", "genero2", "canal",
        "codigoCapsula", "descripcionCapsula", "codigoDivision",
        "descripcionDivision", "codigoTemporada", "descripcionTemporada",
        "grupo", "descripciongrupo",
    ]

    inserted = 0
    for _, row in df.iterrows():
        row_id = _to_int(row.get("id"))
        if row_id is None:
            continue

        if session.get(Articulo, row_id):
            continue

        kwargs = {"id": row_id}
        for field in articulo_fields:
            kwargs[field] = _clean(row.get(field))

        session.add(Articulo(**kwargs))
        inserted += 1

        if inserted % 5000 == 0:
            session.flush()
            logger.info("  tabla.csv: %d registros procesados...", inserted)

    session.flush()
    logger.info("  tabla.csv: %d registros insertados.", inserted)
    return inserted


def seed_articulos_complementarios(session):
    logger.info("Cargando artículos complementarios...")

    df = _read_csv("tablaComplementaria.csv")
    if df.empty:
        logger.info("  tablaComplementaria.csv: sin datos, se omite.")
        return 0

    field_map = {
        "codigo": "codigo",
        "codigoEdad": "codigoEdad",
        "codigoMaterial": "codigoMaterial",
        "codigoSegmentacionProveedor": "codigoSegmentacionProveedor",
        "codigoSegmentacionMarathon": "codigoSegmentacionMarathon",
        "codigoVidriera": "codigoVidriera",
        "codigoAnio": "codigoAnio",
        "codigoBarra": "codigoBarra",
        "codigoCruzar": "codigoCruzar",
        "objetivoGeneral": "objetivo",
    }

    inserted = 0
    for _, row in df.iterrows():
        row_id = _to_int(row.get("id"))
        if row_id is None:
            continue

        if session.get(ArticuloComplementario, row_id):
            continue

        kwargs = {"id": row_id}
        for model_field, csv_col in field_map.items():
            kwargs[model_field] = _clean(row.get(csv_col))

        session.add(ArticuloComplementario(**kwargs))
        inserted += 1

    session.flush()
    logger.info("  tablaComplementaria.csv: %d registros insertados.", inserted)
    return inserted


def seed_precios(session):
    logger.info("Cargando precios...")

    inserted = 0

    df_compra = _read_csv("preciocompra.csv")
    if df_compra.empty:
        logger.info("  preciocompra.csv: sin datos, se omite.")
    else:
        _set_identity_insert(session, precioCompra.__tablename__, True)
        try:
            for _, row in df_compra.iterrows():
                row_id = _to_int(row.get("id"))
                if row_id is None:
                    continue
                if session.get(precioCompra, row_id):
                    continue

                session.add(precioCompra(
                    id=row_id,
                    codigoArticulo=_clean(row.get("codigo")),
                    precioCompra=_to_decimal(row.get("precioCompra")),
                ))
                inserted += 1
            session.flush()
        finally:
            _set_identity_insert(session, precioCompra.__tablename__, False)

        logger.info("  preciocompra.csv: registros insertados.")

    df_venta = _read_csv("precioventa.csv")
    if df_venta.empty:
        logger.info("  precioventa.csv: sin datos, se omite.")
    else:
        _set_identity_insert(session, precioVenta.__tablename__, True)
        try:
            for _, row in df_venta.iterrows():
                row_id = _to_int(row.get("id"))
                if row_id is None:
                    continue
                if session.get(precioVenta, row_id):
                    continue

                session.add(precioVenta(
                    id=row_id,
                    codigoArticulo=_clean(row.get("codigo")),
                    precioVenta=_to_decimal(row.get("precioVenta")),
                ))
                inserted += 1
            session.flush()
        finally:
            _set_identity_insert(session, precioVenta.__tablename__, False)

        logger.info("  precioventa.csv: registros insertados.")

    return inserted


def seed_csv_data(session=None):
    own_session = session is None
    db = session or SessionLocal()

    try:
        seed_proveedores(db)
        seed_catalogos(db)
        seed_marcas_y_markups(db)
        seed_talles(db)
        seed_articulos(db)
        seed_articulos_complementarios(db)
        seed_precios(db)

        if own_session:
            db.commit()
            logger.info("Seeding CSV finalizado correctamente.")
    except Exception:
        if own_session:
            db.rollback()
        raise
    finally:
        if own_session:
            db.close()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    from database import init_db
    init_db()
    seed_csv_data()
