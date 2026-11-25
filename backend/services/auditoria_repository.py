from decimal import Decimal

try:
    from backend.models import (
        AuditoriaDocumento,
        AuditoriaDocumentoLinea,
        AuditoriaProveedor,
    )
except ModuleNotFoundError:
    from models import (
        AuditoriaDocumento,
        AuditoriaDocumentoLinea,
        AuditoriaProveedor,
    )
 
def decimal_to_float(value):
    if value is None:
        return 0.0
    # Mantenemos el objeto Decimal si viene de la DB para evitar micro-errores de redondeo
    if isinstance(value, Decimal):
        return value  
    return value

class AuditoriaRepository:
    def __init__(self, session):
        self.session = session

    def get_or_create_proveedor(self, cod_prov, razon_social=None, marca=None):
        proveedor = (
            self.session.query(AuditoriaProveedor)
            .filter(AuditoriaProveedor.cod_prov == cod_prov)
            .first()
        )
        if proveedor:
            if razon_social:
                proveedor.razon_social = razon_social
            if marca:
                proveedor.marca = marca
            return proveedor

        proveedor = AuditoriaProveedor(
            cod_prov=cod_prov,
            razon_social=razon_social,
            marca=marca,
        )
        self.session.add(proveedor)
        self.session.flush()
        return proveedor

    def upsert_documento(self, data, lineas=None):
        documento = (
            self.session.query(AuditoriaDocumento)
            .filter(
                AuditoriaDocumento.origen == data["origen"],
                AuditoriaDocumento.codigo_documento == data["codigo_documento"],
            )
            .first()
        )

        if not documento:
            documento = AuditoriaDocumento(
                origen=data["origen"],
                codigo_documento=data["codigo_documento"],
            )
            self.session.add(documento)

        for campo in (
            "documento_relacionado",
            "cegid_naturaleza",
            "cegid_souche",
            "cegid_numero",
            "cegid_indice",
            "ref_interna",
            "ref_externa",
            "ref_siguiente",
            "proveedor_id",
            "deposito",
            "fecha_documento",
            "fecha_entrega_prevista",
            "estado",
            "moneda",
            "total_cantidad",
            "total_importe",
            "metadata_json",
        ):
            if campo in data:
                setattr(documento, campo, data[campo])

        self.session.flush()

        if lineas is not None:
            self.session.query(AuditoriaDocumentoLinea).filter(
                AuditoriaDocumentoLinea.documento_id == documento.id
            ).delete(synchronize_session=False)
            self.session.flush()
            objetos = [
                AuditoriaDocumentoLinea(documento_id=documento.id, **linea)
                for linea in lineas
            ]
            if objetos:
                self.session.bulk_save_objects(objetos)

        return documento

    def eliminar_documentos_por_ventana(self, desde=None, hasta=None, souche=None, origenes=None):
        query = self.session.query(AuditoriaDocumento)
        if origenes:
            query = query.filter(AuditoriaDocumento.origen.in_(origenes))
        if desde:
            query = query.filter(AuditoriaDocumento.fecha_documento >= desde)
        if hasta:
            query = query.filter(AuditoriaDocumento.fecha_documento < hasta)
        if souche:
            query = query.filter(AuditoriaDocumento.cegid_souche == souche)

        documentos = query.all()
        ids = [doc.id for doc in documentos]
        if not ids:
            return 0

        self.session.query(AuditoriaDocumentoLinea).filter(
            AuditoriaDocumentoLinea.documento_id.in_(ids)
        ).delete(synchronize_session=False)
        query.delete(synchronize_session=False)
        return len(ids)

    def listar_documentos(self, origen=None, proveedor=None, estado=None, limit=200):
        query = self.session.query(AuditoriaDocumento)
        if origen:
            query = query.filter(AuditoriaDocumento.origen == origen)
        if estado:
            query = query.filter(AuditoriaDocumento.estado == estado)
        if proveedor:
            query = query.join(AuditoriaProveedor).filter(
                AuditoriaProveedor.cod_prov == proveedor
            )
        return (
            query.order_by(AuditoriaDocumento.fecha_documento.desc(), AuditoriaDocumento.id.desc())
            .limit(limit)
            .all()
        )

    def listar_lineas_por_ean(self, ean):
        return (
            self.session.query(AuditoriaDocumentoLinea)
            .join(AuditoriaDocumento)
            .filter(AuditoriaDocumentoLinea.ean == ean)
            .order_by(AuditoriaDocumento.fecha_documento.asc(), AuditoriaDocumento.id.asc())
            .all()
        )
