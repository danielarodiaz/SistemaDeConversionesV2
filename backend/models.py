from sqlalchemy import (
    Column,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship
from sqlalchemy.ext.declarative import declarative_base
from datetime import datetime

Base = declarative_base()

class Proveedor(Base):
    __tablename__ = 'proveedores'
    id = Column(Integer, primary_key=True)
    cuit = Column(String(20), index=True)
    cod_prov = Column(String(50), unique=True, index=True)     
    razon_social = Column(String(255))
    marca = Column(String(100))       
    pivot = Column(String(100))        
    tipo = Column(String(50))         

class ArticuloGasto(Base):
    __tablename__ = 'articulos_gastos'
    id = Column(Integer, primary_key=True)
    clave_busqueda = Column(String(50)) 
    articulo_sap = Column(String(50))   
    descripcion_sap = Column(String(255))
    cuenta_contable = Column(String(50))
    
    # Relación para buscar variaciones (ej: 'AGUA LOCALES' -> 'AGUA')
    variaciones = relationship("VariacionArticulo", back_populates="articulo")

class VariacionArticulo(Base):
    __tablename__ = 'articulos_gastos_variaciones'
    id = Column(Integer, primary_key=True)
    texto_variacion = Column(String(100), index=True)
    articulo_id = Column(Integer, ForeignKey('articulos_gastos.id'))
    articulo = relationship("ArticuloGasto", back_populates="variaciones")

class MapeoTalle(Base):
    __tablename__ = 'mapeo_talles'
    id = Column(Integer, primary_key=True)
    # Cambiamos 'sistema' por una relación opcional al proveedor
    proveedor_id = Column(Integer, ForeignKey('proveedores.id'), nullable=True)
    marca_nombre = Column(String(50), index=True) # Ej: 'CROCS', 'TOPPER'
    talle_origen = Column(String(50), nullable=False)
    talle_destino = Column(String(50), nullable=False) # String es más flexible que Integer

class Sucursal(Base):
    __tablename__ = 'sucursales'
    id = Column(Integer, primary_key=True)
    provincia = Column(String(10), index=True)      
    codigo_sucursal = Column(String(20), unique=True, index=True) 
    nombre_sucursal = Column(String(255))           
    
    # Relación con sus variaciones
    variaciones = relationship("SucursalVariacion", back_populates="sucursal", cascade="all, delete-orphan")

class SucursalVariacion(Base):
    __tablename__ = 'sucursales_variaciones'
    id = Column(Integer, primary_key=True)
    texto_variacion = Column(String(255), index=True) 
    sucursal_id = Column(Integer, ForeignKey('sucursales.id'))
    
    sucursal = relationship("Sucursal", back_populates="variaciones")


class AuditoriaProveedor(Base):
    __tablename__ = 'auditoria_proveedores'

    id = Column(Integer, primary_key=True)
    cod_prov = Column(String(50), index=True, nullable=False)
    razon_social = Column(String(255))
    marca = Column(String(100), index=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    documentos = relationship("AuditoriaDocumento", back_populates="proveedor")


class AuditoriaDocumento(Base):
    __tablename__ = 'auditoria_documentos'
    __table_args__ = (
        UniqueConstraint('origen', 'codigo_documento', name='uq_auditoria_documento_origen_codigo'),
    )

    id = Column(Integer, primary_key=True)
    origen = Column(String(50), nullable=False, index=True)  # PROPUESTA, PEDIDO, NOTIFICACION, RECEPCION
    codigo_documento = Column(String(100), nullable=False, index=True)
    documento_relacionado = Column(String(100), index=True)
    cegid_naturaleza = Column(String(10), index=True)
    cegid_souche = Column(String(20), index=True)
    cegid_numero = Column(String(50), index=True)
    cegid_indice = Column(String(20), default='0')
    ref_interna = Column(String(100), index=True)
    ref_externa = Column(String(100), index=True)
    ref_siguiente = Column(String(150), index=True)
    proveedor_id = Column(Integer, ForeignKey('auditoria_proveedores.id'), nullable=True)
    deposito = Column(String(50), index=True)
    fecha_documento = Column(DateTime, index=True)
    fecha_entrega_prevista = Column(DateTime, index=True)
    estado = Column(String(50), default='PENDIENTE', index=True)
    moneda = Column(String(10))
    total_cantidad = Column(Numeric(18, 4), default=0)
    total_importe = Column(Numeric(18, 4), default=0)
    metadata_json = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    proveedor = relationship("AuditoriaProveedor", back_populates="documentos")
    lineas = relationship(
        "AuditoriaDocumentoLinea",
        back_populates="documento",
        cascade="all, delete-orphan",
    )


class AuditoriaDocumentoLinea(Base):
    __tablename__ = 'auditoria_documento_lineas'

    id = Column(Integer, primary_key=True)
    documento_id = Column(Integer, ForeignKey('auditoria_documentos.id'), nullable=False, index=True)
    numero_linea = Column(String(50), index=True)
    numero_orden = Column(String(50), index=True)
    ean = Column(String(50), index=True)
    codigo_articulo = Column(String(100), index=True)
    descripcion = Column(String(255))
    talle = Column(String(50))
    color = Column(String(100))
    deposito = Column(String(50), index=True)
    marca = Column(String(100), index=True)
    genero = Column(String(50), index=True)
    cantidad = Column(Numeric(18, 4), default=0)
    cantidad_conciliada = Column(Numeric(18, 4), default=0)
    precio_unitario = Column(Numeric(18, 4))
    importe = Column(Numeric(18, 4))
    estado = Column(String(50), default='PENDIENTE', index=True)
    pieza_precedente = Column(String(150), index=True)
    pieza_origen = Column(String(150), index=True)
    linea_precedente_key = Column(String(150), index=True)
    linea_origen_key = Column(String(150), index=True)
    metadata_json = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    documento = relationship("AuditoriaDocumento", back_populates="lineas")


class AuditoriaMatch(Base):
    __tablename__ = 'auditoria_matches'

    id = Column(Integer, primary_key=True)
    propuesta_linea_id = Column(Integer, ForeignKey('auditoria_documento_lineas.id'), nullable=True, index=True)
    pedido_linea_id = Column(Integer, ForeignKey('auditoria_documento_lineas.id'), nullable=True, index=True)
    notificacion_linea_id = Column(Integer, ForeignKey('auditoria_documento_lineas.id'), nullable=True, index=True)
    recepcion_linea_id = Column(Integer, ForeignKey('auditoria_documento_lineas.id'), nullable=True, index=True)
    ean = Column(String(50), index=True)
    cantidad_pedida = Column(Numeric(18, 4), default=0)
    cantidad_facturada = Column(Numeric(18, 4), default=0)
    cantidad_notificada = Column(Numeric(18, 4), default=0)
    cantidad_recibida = Column(Numeric(18, 4), default=0)
    estado = Column(String(50), default='PENDIENTE', index=True)
    regla = Column(String(100))
    confianza = Column(Numeric(5, 2))
    observacion = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
