from sqlalchemy import func

from backend.models import Proveedor, ProveedorMarca, marca, objetivoGeneral
from backend.services.unit_of_work import UnitOfWork
from backend.scripts.abm_articulos.service import obtener_catalogos


MODULOS = {"proveedores", "marcas", "proveedor-marca", "objetivos"}


def _limpiar(valor):
    return str(valor or "").strip()


def _normalizar(valor):
    return _limpiar(valor).upper()


def _clear_catalogos():
    obtener_catalogos.cache_clear()


def _serializar_proveedor(row):
    return {
        "id": row.id,
        "codigo": row.cod_prov or "",
        "descripcion": row.razon_social or "",
        "cuit": row.cuit or "",
        "marca": row.marca or "",
        "pivot": row.pivot or "",
        "tipo": row.tipo or "",
    }


def _serializar_marca(row):
    return {
        "id": row.id,
        "codigo": row.codigoMarca or "",
        "descripcion": row.descripcionMarca or "",
    }


def _serializar_relacion_resumen(row):
    proveedor = row.proveedor
    marca_obj = row.marca
    return {
        "id": row.id,
        "cod_prov": proveedor.cod_prov if proveedor else "",
        "proveedor": proveedor.razon_social if proveedor else "",
        "codigoMarca": marca_obj.codigoMarca if marca_obj else "",
        "marca": marca_obj.descripcionMarca if marca_obj else "",
    }


def _serializar_objetivo(row):
    return {
        "id": row.id,
        "codigo": row.codigoObjetivoGeneral or "",
        "descripcion": row.descripcionObjetivoGeneral or "",
    }


def _serializar_relacion(row):
    return {
        "id": row.id,
        "codigo": row.proveedor.cod_prov if row.proveedor else "",
        "descripcion": row.marca.descripcionMarca if row.marca else "",
        "cod_prov": row.proveedor.cod_prov if row.proveedor else "",
        "codigoMarca": row.marca.codigoMarca if row.marca else "",
        "proveedor": row.proveedor.razon_social if row.proveedor else "",
        "marca": row.marca.descripcionMarca if row.marca else "",
        "activo": row.activo,
    }


def listar_config(modulo):
    if modulo not in MODULOS:
        raise ValueError("Modulo de configuracion no valido.")

    with UnitOfWork() as uow:
        if modulo == "proveedores":
            rows = (
                uow.session.query(Proveedor)
                .filter(func.upper(func.ltrim(func.rtrim(func.coalesce(Proveedor.tipo, "")))) == "MERCADERIA")
                .order_by(Proveedor.cod_prov)
                .all()
            )
            items = [_serializar_proveedor(row) for row in rows]
            relaciones_por_proveedor = {item["id"]: [] for item in items}
            if relaciones_por_proveedor:
                relaciones = (
                    uow.session.query(ProveedorMarca)
                    .join(Proveedor, Proveedor.id == ProveedorMarca.proveedor_id)
                    .join(marca, marca.id == ProveedorMarca.marca_id)
                    .filter(ProveedorMarca.proveedor_id.in_(list(relaciones_por_proveedor.keys())))
                    .order_by(Proveedor.cod_prov, marca.codigoMarca)
                    .all()
                )
                for rel in relaciones:
                    relaciones_por_proveedor.setdefault(rel.proveedor_id, []).append(_serializar_relacion_resumen(rel))
            for item in items:
                relaciones = relaciones_por_proveedor.get(item["id"], [])
                item["relaciones"] = relaciones
                item["relaciones_count"] = len(relaciones)
            return items
        if modulo == "marcas":
            rows = uow.session.query(marca).order_by(marca.codigoMarca).all()
            items = [_serializar_marca(row) for row in rows]
            relaciones_por_marca = {item["id"]: [] for item in items}
            if relaciones_por_marca:
                relaciones = (
                    uow.session.query(ProveedorMarca)
                    .join(Proveedor, Proveedor.id == ProveedorMarca.proveedor_id)
                    .join(marca, marca.id == ProveedorMarca.marca_id)
                    .filter(ProveedorMarca.marca_id.in_(list(relaciones_por_marca.keys())))
                    .order_by(marca.codigoMarca, Proveedor.cod_prov)
                    .all()
                )
                for rel in relaciones:
                    relaciones_por_marca.setdefault(rel.marca_id, []).append(_serializar_relacion_resumen(rel))
            for item in items:
                relaciones = relaciones_por_marca.get(item["id"], [])
                item["relaciones"] = relaciones
                item["relaciones_count"] = len(relaciones)
            return items
        if modulo == "objetivos":
            rows = uow.session.query(objetivoGeneral).order_by(objetivoGeneral.codigoObjetivoGeneral).all()
            return [_serializar_objetivo(row) for row in rows]

        rows = (
            uow.session.query(ProveedorMarca)
            .join(Proveedor, Proveedor.id == ProveedorMarca.proveedor_id)
            .join(marca, marca.id == ProveedorMarca.marca_id)
            .order_by(Proveedor.cod_prov, marca.codigoMarca)
            .all()
        )
        return [_serializar_relacion(row) for row in rows]


def crear_config(modulo, payload):
    if modulo not in MODULOS:
        raise ValueError("Modulo de configuracion no valido.")

    with UnitOfWork() as uow:
        if modulo == "proveedores":
            cuit = _limpiar(payload.get("cuit"))
            if not cuit.isdigit() or len(cuit) != 11:
                raise ValueError("El CUIT debe tener 11 digitos y no llevar guion.")
            cod_prov = _normalizar(payload.get("cod_prov") or payload.get("codigo"))
            if not cod_prov:
                raise ValueError("El codigo de proveedor es obligatorio.")
            if uow.session.query(Proveedor).filter(Proveedor.cod_prov == cod_prov).first():
                raise ValueError("Ya existe un proveedor con ese codigo.")
            row = Proveedor(
                cuit=cuit,
                cod_prov=cod_prov,
                razon_social=_limpiar(payload.get("razon_social") or payload.get("descripcion")),
                marca=_limpiar(payload.get("marca")),
                pivot=_limpiar(payload.get("pivot")),
                tipo="MERCADERIA",
            )
            uow.session.add(row)
            uow.session.flush()
            _clear_catalogos()
            return _serializar_proveedor(row)

        if modulo == "marcas":
            codigo = _normalizar(payload.get("codigoMarca") or payload.get("codigo"))
            descripcion = _limpiar(payload.get("descripcionMarca") or payload.get("descripcion"))
            if not codigo or not descripcion:
                raise ValueError("Codigo y descripcion de marca son obligatorios.")
            if uow.session.query(marca).filter(marca.codigoMarca == codigo).first():
                raise ValueError("Ya existe una marca con ese codigo.")
            row = marca(codigoMarca=codigo, descripcionMarca=descripcion)
            uow.session.add(row)
            uow.session.flush()
            _clear_catalogos()
            return _serializar_marca(row)

        if modulo == "objetivos":
            codigo = _normalizar(payload.get("codigoObjetivoGeneral") or payload.get("codigo"))
            descripcion = _limpiar(payload.get("descripcionObjetivoGeneral") or payload.get("descripcion"))
            if not codigo or not descripcion:
                raise ValueError("Codigo y descripcion de objetivo son obligatorios.")
            if uow.session.query(objetivoGeneral).filter(objetivoGeneral.codigoObjetivoGeneral == codigo).first():
                raise ValueError("Ya existe un objetivo general con ese codigo.")
            row = objetivoGeneral(codigoObjetivoGeneral=codigo, descripcionObjetivoGeneral=descripcion)
            uow.session.add(row)
            uow.session.flush()
            _clear_catalogos()
            return _serializar_objetivo(row)

        cod_prov = _normalizar(payload.get("cod_prov") or payload.get("codigoProveedor"))
        codigo_marca = _normalizar(payload.get("codigoMarca") or payload.get("cod_marca"))
        proveedor = uow.session.query(Proveedor).filter(Proveedor.cod_prov == cod_prov).first()
        marca_obj = uow.session.query(marca).filter(marca.codigoMarca == codigo_marca).first()
        if not proveedor:
            raise ValueError("Proveedor no encontrado.")
        if not marca_obj:
            raise ValueError("Marca no encontrada.")
        existente = (
            uow.session.query(ProveedorMarca)
            .filter(ProveedorMarca.proveedor_id == proveedor.id, ProveedorMarca.marca_id == marca_obj.id)
            .first()
        )
        if existente:
            existente.activo = 1
            row = existente
        else:
            row = ProveedorMarca(proveedor_id=proveedor.id, marca_id=marca_obj.id, activo=1)
            uow.session.add(row)
        uow.session.flush()
        _clear_catalogos()
        return _serializar_relacion(row)


def actualizar_config(modulo, item_id, payload):
    if modulo not in MODULOS:
        raise ValueError("Modulo de configuracion no valido.")

    with UnitOfWork() as uow:
        if modulo == "proveedores":
            row = uow.session.get(Proveedor, int(item_id))
            if not row:
                return None
            cuit = _limpiar(payload.get("cuit", row.cuit))
            if not cuit.isdigit() or len(cuit) != 11:
                raise ValueError("El CUIT debe tener 11 digitos y no llevar guion.")
            cod_prov = _normalizar(payload.get("cod_prov") or payload.get("codigo") or row.cod_prov)
            duplicado = uow.session.query(Proveedor).filter(Proveedor.cod_prov == cod_prov, Proveedor.id != row.id).first()
            if duplicado:
                raise ValueError("Ya existe otro proveedor con ese codigo.")
            row.cuit = cuit
            row.cod_prov = cod_prov
            row.razon_social = _limpiar(payload.get("razon_social") or payload.get("descripcion") or row.razon_social)
            row.marca = _limpiar(payload.get("marca", row.marca))
            row.pivot = _limpiar(payload.get("pivot", row.pivot))
            row.tipo = "MERCADERIA"
            uow.session.flush()
            _clear_catalogos()
            return _serializar_proveedor(row)

        if modulo == "marcas":
            row = uow.session.get(marca, int(item_id))
            if not row:
                return None
            codigo = _normalizar(payload.get("codigoMarca") or payload.get("codigo") or row.codigoMarca)
            duplicado = uow.session.query(marca).filter(marca.codigoMarca == codigo, marca.id != row.id).first()
            if duplicado:
                raise ValueError("Ya existe otra marca con ese codigo.")
            row.codigoMarca = codigo
            row.descripcionMarca = _limpiar(payload.get("descripcionMarca") or payload.get("descripcion") or row.descripcionMarca)
            uow.session.flush()
            _clear_catalogos()
            return _serializar_marca(row)

        if modulo == "objetivos":
            row = uow.session.get(objetivoGeneral, int(item_id))
            if not row:
                return None
            codigo = _normalizar(payload.get("codigoObjetivoGeneral") or payload.get("codigo") or row.codigoObjetivoGeneral)
            duplicado = (
                uow.session.query(objetivoGeneral)
                .filter(objetivoGeneral.codigoObjetivoGeneral == codigo, objetivoGeneral.id != row.id)
                .first()
            )
            if duplicado:
                raise ValueError("Ya existe otro objetivo general con ese codigo.")
            row.codigoObjetivoGeneral = codigo
            row.descripcionObjetivoGeneral = _limpiar(
                payload.get("descripcionObjetivoGeneral") or payload.get("descripcion") or row.descripcionObjetivoGeneral
            )
            uow.session.flush()
            _clear_catalogos()
            return _serializar_objetivo(row)

        row = uow.session.get(ProveedorMarca, int(item_id))
        if not row:
            return None
        cod_prov = _normalizar(payload.get("cod_prov") or row.proveedor.cod_prov)
        codigo_marca = _normalizar(payload.get("codigoMarca") or row.marca.codigoMarca)
        proveedor = uow.session.query(Proveedor).filter(Proveedor.cod_prov == cod_prov).first()
        marca_obj = uow.session.query(marca).filter(marca.codigoMarca == codigo_marca).first()
        if not proveedor:
            raise ValueError("Proveedor no encontrado.")
        if not marca_obj:
            raise ValueError("Marca no encontrada.")
        duplicado = (
            uow.session.query(ProveedorMarca)
            .filter(
                ProveedorMarca.proveedor_id == proveedor.id,
                ProveedorMarca.marca_id == marca_obj.id,
                ProveedorMarca.id != row.id,
            )
            .first()
        )
        if duplicado:
            raise ValueError("Ya existe esa relacion proveedor-marca.")
        row.proveedor_id = proveedor.id
        row.marca_id = marca_obj.id
        row.activo = 1
        uow.session.flush()
        _clear_catalogos()
        return _serializar_relacion(row)


def eliminar_config(modulo, item_id):
    if modulo not in MODULOS:
        raise ValueError("Modulo de configuracion no valido.")

    with UnitOfWork() as uow:
        if modulo == "proveedores":
            row = uow.session.get(Proveedor, int(item_id))
        elif modulo == "marcas":
            row = uow.session.get(marca, int(item_id))
        elif modulo == "proveedor-marca":
            row = uow.session.get(ProveedorMarca, int(item_id))
        else:
            row = uow.session.get(objetivoGeneral, int(item_id))
        if not row:
            return None

        relaciones_eliminadas = []
        if modulo == "proveedores":
            relaciones = (
                uow.session.query(ProveedorMarca)
                .filter(ProveedorMarca.proveedor_id == row.id)
                .all()
            )
            relaciones_eliminadas = [_serializar_relacion_resumen(rel) for rel in relaciones]
            for rel in relaciones:
                uow.session.delete(rel)
        elif modulo == "marcas":
            relaciones = (
                uow.session.query(ProveedorMarca)
                .filter(ProveedorMarca.marca_id == row.id)
                .all()
            )
            relaciones_eliminadas = [_serializar_relacion_resumen(rel) for rel in relaciones]
            for rel in relaciones:
                uow.session.delete(rel)

        uow.session.delete(row)
        _clear_catalogos()
        return {
            "deleted": True,
            "relaciones_eliminadas": relaciones_eliminadas,
            "relaciones_eliminadas_count": len(relaciones_eliminadas),
        }
