import os
from functools import lru_cache

from sqlalchemy import func

from backend.config import OUTPUT_FOLDER
from backend.models import (
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
from backend.scripts.abm_articulos.exportadores import generar_csv_complementario_abm, generar_zip_abm_articulos
from backend.services.unit_of_work import UnitOfWork
from backend.utils.cegid_utils import obtener_codigos_cruzar_articulos


CATALOGOS = {
    "anios": (año, "codigoAnio", "descripcionAño"),
    "canales": (canal, "codigoCanal", "descripcionCanal"),
    "capsulas": (capsula, "codigoCapsula", "descripcionCapsula"),
    "colores": (color, "codigoColor", "descripcionColor"),
    "divisiones": (division, "codigoDivision", "descripcionDivision"),
    "edades": (edad, "codigoEdad", "descripcionEdad"),
    "generos": (genero, "codigoGenero", "descripcionGenero"),
    "marcas": (marca, "codigoMarca", "descripcionMarca"),
    "materiales": (material, "codigoMaterial", "descripcionMaterial"),
    "objetivos": (objetivoGeneral, "codigoObjetivoGeneral", "descripcionObjetivoGeneral"),
    "promos": (promo, "codigoPromo", "descripcionPromo"),
    "sap": (sap, "codigoGrupoSap", "descripcionGrupoSap"),
    "segmentaciones_marathon": (
        segmentacionMarathon,
        "codigoSegmentacionMarathon",
        "descripcionSegmentacionMarathon",
    ),
    "segmentaciones_proveedor": (
        segmentacionProveedor,
        "codigoSegmentacionProveedor",
        "descripcionSegmentacionProveedor",
    ),
    "siluetas": (silueta, "codigoSilueta", "descripcionSilueta"),
    "temporadas": (temporada, "codigoTemporada", "descripcionTemporada"),
    "tipos_producto": (tipoProducto, "codigoTipoProducto", "descripcionTipoProducto"),
    "usos": (uso, "codigoUso", "descripcionUso"),
    "vidrieras": (vidriera, "codigoVidriera", "descripcionVidriera"),
}


def _catalog_item(row, codigo_attr, descripcion_attr):
    codigo = getattr(row, codigo_attr, "") or ""
    descripcion = getattr(row, descripcion_attr, "") or ""
    item = {
        "id": row.id,
        "codigo": str(codigo),
        "descripcion": str(descripcion),
        "label": f"{codigo} - {descripcion}".strip(" -"),
    }
    if isinstance(row, color):
        item["valor"] = row.valor or ""
        item["descripcionValor"] = row.descripcionValor or ""
        item["label"] = f"{codigo} - {descripcion} / {row.valor or ''}".strip(" /")
    return item


def _tipo_markup(tipo_codigo):
    tipo = str(tipo_codigo or "").strip().lower()
    if tipo == "cal":
        return "cal"
    if tipo == "ind":
        return "ind"
    return "resto"


@lru_cache(maxsize=1)
def obtener_catalogos():
    with UnitOfWork() as uow:
        data = {}
        for nombre, (model, codigo_attr, descripcion_attr) in CATALOGOS.items():
            rows = uow.session.query(model).order_by(getattr(model, codigo_attr)).all()
            data[nombre] = [_catalog_item(row, codigo_attr, descripcion_attr) for row in rows]

        proveedores = uow.session.query(Proveedor).order_by(Proveedor.razon_social).all()
        data["proveedores"] = [
            {
                "id": p.id,
                "codigo": p.cod_prov or "",
                "descripcion": p.razon_social or p.marca or "",
                "label": f"{p.cod_prov or ''} - {p.razon_social or p.marca or ''}".strip(" -"),
            }
            for p in proveedores
        ]

        talles = uow.session.query(TalleMaestro).order_by(TalleMaestro.codigoTalle, TalleMaestro.valorTalle).all()
        data["talles"] = [
            {
                "id": t.id,
                "codigo": t.codigoTalle or "",
                "descripcion": t.descripcionTalle or "",
                "codigoBarra": t.codigoBarra or "",
                "valorTalle": t.valorTalle or "",
                "descripcionValorTalle": t.descripcionValorTalle or "",
                "codigoMedida": t.codigoMedida or "",
                "tipoMedida": t.tipoMedida or "",
                "medida": t.medida or "",
                "codigoGen": t.codigoGen or "",
                "genero": t.genero or "",
                "label": f"{t.codigoTalle or ''} - {t.valorTalle or ''} - {t.descripcionTalle or ''}".strip(" -"),
            }
            for t in talles
        ]
        data["markups"] = [
            {
                "marca_id": m.marca_id,
                "tipo": str(m.tipoProducto or "").strip().lower(),
                "tipo_normalizado": _tipo_markup(m.tipoProducto),
                "markup": float(m.markup or 0),
            }
            for m in uow.session.query(markup).all()
        ]

        return data


def _get(dct, key, default=""):
    value = dct.get(key, default)
    return default if value is None else value


def _next_articulo_id(session):
    actual = session.query(func.max(Articulo.id)).scalar()
    return int(actual or 0) + 1


def crear_borrador(payload):
    base = payload.get("base") or {}
    comp = payload.get("complementario") or {}
    talles = payload.get("talles") or []
    precios = payload.get("precios") or {}
    if not talles:
        raise ValueError("Selecciona al menos un talle.")
    if not _get(base, "codigo"):
        raise ValueError("El codigo del articulo es obligatorio.")
    if float(precios.get("precioVenta") or 0) <= float(precios.get("precioCompra") or 0):
        raise ValueError("El precio de venta debe ser mayor al precio de compra.")

    with UnitOfWork() as uow:
        next_id = _next_articulo_id(uow.session)
        creados = []
        for talle in talles:
            codigo_barra = _get(talle, "codigoBarra") or f"{_get(base, 'codigo')}-{_get(talle, 'valorTalle') or _get(talle, 'codigo')}"
            articulo = Articulo(
                id=next_id,
                codigo=_get(base, "codigo"),
                descripcion=_get(base, "descripcion"),
                tipoProducto=_get(base, "tipoProducto"),
                descripcionProducto=_get(base, "descripcionProducto"),
                grupo=_get(base, "grupo"),
                descripciongrupo=_get(base, "descripcionGrupo"),
                grupoSAP=_get(base, "grupoSAP"),
                descripcionGrupoSAP=_get(base, "descripcionGrupoSAP"),
                marca=_get(base, "marca"),
                descripcionMarca=_get(base, "descripcionMarca"),
                genero=_get(base, "genero"),
                descripcionGenero=_get(base, "descripcionGenero"),
                silueta=_get(base, "silueta"),
                descripcionSilueta=_get(base, "descripcionSilueta"),
                uso=_get(base, "uso"),
                descripcionUso=_get(base, "descripcionUso"),
                promo=_get(base, "promo"),
                descripcionPromo=_get(base, "descripcionPromo"),
                codigoBarra=codigo_barra,
                talle=_get(talle, "codigo"),
                descripcionTalle=_get(talle, "descripcion"),
                valorTalle=_get(talle, "valorTalle"),
                descripcionValorTalle=_get(talle, "descripcionValorTalle"),
                color=_get(base, "color"),
                descripcionColor=_get(base, "descripcionColor"),
                valor=_get(base, "valorColor"),
                descripcionValor=_get(base, "descripcionValorColor"),
                nombreProveedor=_get(base, "nombreProveedor"),
                codigoMedida=_get(talle, "codigoMedida"),
                tipoMedida=_get(talle, "tipoMedida"),
                medida=_get(talle, "medida"),
                codigoGen=_get(base, "codigoGen") or _get(talle, "codigoGen"),
                genero2=_get(base, "genero2") or _get(talle, "genero"),
                canal=_get(base, "canal"),
                codigoCapsula=_get(base, "codigoCapsula"),
                descripcionCapsula=_get(base, "descripcionCapsula"),
                codigoDivision=_get(base, "codigoDivision"),
                descripcionDivision=_get(base, "descripcionDivision"),
                codigoTemporada=_get(base, "codigoTemporada"),
                descripcionTemporada=_get(base, "descripcionTemporada"),
                sector="base",
                estado="borrador",
            )
            complementario = ArticuloComplementario(
                codigo=articulo.codigo,
                codigoEdad=_get(comp, "codigoEdad"),
                codigoMaterial=_get(comp, "codigoMaterial"),
                codigoSegmentacionProveedor=_get(comp, "codigoSegmentacionProveedor"),
                codigoSegmentacionMarathon=_get(comp, "codigoSegmentacionMarathon"),
                codigoVidriera=_get(comp, "codigoVidriera"),
                codigoAnio=_get(comp, "codigoAnio"),
                codigoBarra=codigo_barra,
                codigoCruzar=codigo_barra,
                objetivoGeneral=_get(comp, "objetivoGeneral"),
                sector="base",
                estado="borrador",
            )
            uow.session.add(articulo)
            uow.session.add(complementario)
            creados.append(articulo)
            next_id += 1

        if "precioCompra" in precios:
            uow.session.add(precioCompra(codigoArticulo=_get(base, "codigo"), precioCompra=precios.get("precioCompra") or 0))
        if "precioVenta" in precios:
            uow.session.add(precioVenta(codigoArticulo=_get(base, "codigo"), precioVenta=precios.get("precioVenta") or 0))

        uow.session.flush()
        return {"items": [_serializar_articulo(a) for a in creados], "created": len(creados)}


def _serializar_articulo(articulo):
    return {
        "id": articulo.id,
        "Código de Barra": articulo.codigoBarra,
        "Codigo": articulo.codigo,
        "Descripción": articulo.descripcion,
        "Tipo de producto": articulo.tipoProducto,
        "Desc Tipo de Producto": articulo.descripcionProducto,
        "Grupo": articulo.grupo,
        "Desc Grupo": articulo.descripciongrupo,
        "Grupo SAP B1": articulo.grupoSAP,
        "Desc Grupo SAP B1": articulo.descripcionGrupoSAP,
        "Departamento": "",
        "Desc Departamento": "",
        "Marca": articulo.marca,
        "Desc Marca": articulo.descripcionMarca,
        "Genero": articulo.genero,
        "Desc Genero": articulo.descripcionGenero,
        "Silueta": articulo.silueta,
        "Desc Silueta": articulo.descripcionSilueta,
        "Uso": articulo.uso,
        "Desc Uso": articulo.descripcionUso,
        "Talle": articulo.talle,
        "Desc. Talle": articulo.descripcionTalle,
        "Valor Talle": articulo.valorTalle,
        "Des. Valor Talle": articulo.descripcionValorTalle,
        "Color": articulo.color,
        "Des. Color Talle": articulo.descripcionColor,
        "Valor Color": articulo.valor,
        "Desc. Valor Color": articulo.descripcionValor,
        "Proveedor Habitual": articulo.nombreProveedor,
        "Codigo Medida": articulo.codigoMedida,
        "Nombre": articulo.tipoMedida,
        "Valor": articulo.medida,
        "Codigo Genero": articulo.codigoGen,
        "Valor Genero": articulo.genero2,
        "Canal": articulo.canal,
    }


def listar_borradores():
    with UnitOfWork() as uow:
        rows = (
            uow.session.query(Articulo)
            .filter(Articulo.sector == "base", Articulo.estado == "borrador")
            .order_by(Articulo.created_at.desc(), Articulo.id.desc())
            .all()
        )
        return [_serializar_articulo(row) for row in rows]


def eliminar_borrador(articulo_id):
    with UnitOfWork() as uow:
        articulo = (
            uow.session.query(Articulo)
            .filter(Articulo.id == articulo_id, Articulo.sector == "base", Articulo.estado == "borrador")
            .one_or_none()
        )
        if not articulo:
            return False
        (
            uow.session.query(ArticuloComplementario)
            .filter(
                ArticuloComplementario.codigo == articulo.codigo,
                ArticuloComplementario.codigoBarra == articulo.codigoBarra,
                ArticuloComplementario.sector == "base",
                ArticuloComplementario.estado == "borrador",
            )
            .delete(synchronize_session=False)
        )
        uow.session.delete(articulo)
        return True


def eliminar_borradores(articulo_ids):
    borrador_ids = [int(i) for i in (articulo_ids or []) if i is not None]
    if not borrador_ids:
        return 0

    eliminados = 0
    with UnitOfWork() as uow:
        articulos = (
            uow.session.query(Articulo)
            .filter(Articulo.id.in_(borrador_ids), Articulo.sector == "base", Articulo.estado == "borrador")
            .all()
        )
        for articulo in articulos:
            (
                uow.session.query(ArticuloComplementario)
                .filter(
                    ArticuloComplementario.codigo == articulo.codigo,
                    ArticuloComplementario.codigoBarra == articulo.codigoBarra,
                    ArticuloComplementario.sector == "base",
                    ArticuloComplementario.estado == "borrador",
                )
                .delete(synchronize_session=False)
            )
            uow.session.delete(articulo)
            eliminados += 1
    return eliminados


def _precio_map(session, model, campo):
    rows = session.query(model).all()
    data = {}
    for row in rows:
        codigo = str(row.codigoArticulo or "")
        if codigo:
            data[codigo] = getattr(row, campo)
    return data


def exportar_borradores():
    os.makedirs(OUTPUT_FOLDER, exist_ok=True)
    with UnitOfWork() as uow:
        articulos = (
            uow.session.query(Articulo)
            .filter(Articulo.sector == "base", Articulo.estado == "borrador")
            .order_by(Articulo.codigo, Articulo.id)
            .all()
        )
        if not articulos:
            raise ValueError("No hay borradores pendientes para exportar.")

        complementarios = (
            uow.session.query(ArticuloComplementario)
            .filter(ArticuloComplementario.sector == "base", ArticuloComplementario.estado == "borrador")
            .order_by(ArticuloComplementario.codigo, ArticuloComplementario.id)
            .all()
        )
        precios_compra = _precio_map(uow.session, precioCompra, "precioCompra")
        precios_venta = _precio_map(uow.session, precioVenta, "precioVenta")
        zip_path = generar_zip_abm_articulos(
            articulos,
            complementarios,
            precios_compra,
            precios_venta,
            {},
            OUTPUT_FOLDER,
        )

        for articulo in articulos:
            articulo.estado = "exportado"
        for comp in complementarios:
            comp.estado = "exportado"

        return {
            "filename": os.path.basename(zip_path),
            "exported": len(articulos),
            "fallbacks": 0,
        }


def _serializar_complementario(comp):
    return {
        "id": comp.id,
        "ID Articulo": comp.codigoCruzar or "",
        "Codigo Articulo": comp.codigo,
        "Codigo Barra": comp.codigoBarra,
        "Edad": comp.codigoEdad,
        "Material": comp.codigoMaterial,
        "Segmentacion Proveedor": comp.codigoSegmentacionProveedor,
        "Segmentacion Marathon": comp.codigoSegmentacionMarathon,
        "Vidriera": comp.codigoVidriera,
        "Año": comp.codigoAnio,
        "Objetivo Gen": comp.objetivoGeneral,
    }


def listar_complementarios():
    with UnitOfWork() as uow:
        rows = (
            uow.session.query(ArticuloComplementario)
            .filter(ArticuloComplementario.sector == "base", ArticuloComplementario.estado == "exportado")
            .order_by(ArticuloComplementario.codigo, ArticuloComplementario.id)
            .all()
        )
        return [_serializar_complementario(row) for row in rows]


def actualizar_complementario(comp_id, payload):
    campos = {
        "Edad": "codigoEdad",
        "Material": "codigoMaterial",
        "Segmentacion Proveedor": "codigoSegmentacionProveedor",
        "Segmentacion Marathon": "codigoSegmentacionMarathon",
        "Vidriera": "codigoVidriera",
        "Año": "codigoAnio",
        "Objetivo Gen": "objetivoGeneral",
        "ID Articulo": "codigoCruzar",
    }
    with UnitOfWork() as uow:
        comp = uow.session.get(ArticuloComplementario, int(comp_id))
        if not comp or comp.sector != "base" or comp.estado != "exportado":
            return None
        for externo, interno in campos.items():
            if externo in payload:
                setattr(comp, interno, payload.get(externo) or "")
        uow.session.flush()
        return _serializar_complementario(comp)


def eliminar_complementarios(comp_ids=None, borrar_todo=False):
    with UnitOfWork() as uow:
        query = uow.session.query(ArticuloComplementario).filter(
            ArticuloComplementario.sector == "base",
            ArticuloComplementario.estado == "exportado",
        )
        if not borrar_todo:
            ids = [int(i) for i in (comp_ids or []) if i is not None]
            if not ids:
                return 0
            query = query.filter(ArticuloComplementario.id.in_(ids))
        deleted = query.delete(synchronize_session=False)
        return deleted


def exportar_complementarios(comp_ids=None):
    os.makedirs(OUTPUT_FOLDER, exist_ok=True)
    with UnitOfWork() as uow:
        query = uow.session.query(ArticuloComplementario).filter(
            ArticuloComplementario.sector == "base",
            ArticuloComplementario.estado == "exportado",
        )
        ids = [int(i) for i in (comp_ids or []) if i is not None]
        if ids:
            query = query.filter(ArticuloComplementario.id.in_(ids))
        complementarios = query.order_by(ArticuloComplementario.codigo, ArticuloComplementario.id).all()
        if not complementarios:
            raise ValueError("No hay complementarios para exportar.")

        pares = [(c.codigo, c.codigoBarra) for c in complementarios]
        codigos_cruzar = obtener_codigos_cruzar_articulos(pares)
        fallbacks = len(pares) - len(codigos_cruzar)
        if fallbacks:
            print(f"ABM Articulos Complementario: {fallbacks} cruce(s) sin match CEGID; se usa codigoBarra como fallback.")
        for comp in complementarios:
            clave = (str(comp.codigo or "").strip(), str(comp.codigoBarra or "").strip())
            comp.codigoCruzar = codigos_cruzar.get(clave) or comp.codigoBarra
        path = generar_csv_complementario_abm(complementarios, codigos_cruzar, OUTPUT_FOLDER)
        return {
            "filename": os.path.basename(path),
            "exported": len(complementarios),
            "fallbacks": fallbacks,
        }
