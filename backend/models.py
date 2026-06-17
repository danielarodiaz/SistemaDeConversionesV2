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
    created_at = Column(DateTime, default=datetime.now, nullable=False)

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
    created_at = Column(DateTime, default=datetime.now, nullable=False)
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
    created_at = Column(DateTime, default=datetime.now, nullable=False)

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
    created_at = Column(DateTime, default=datetime.now, nullable=False)

#Tablas de ABM articulos  
class año(Base):
    __tablename__ = 'años'
    id = Column(Integer, primary_key=True, autoincrement=True)
    codigoAnio = Column(String(20), index=True)
    descripcionAño = Column(String(20), index=True)
    created_at = Column(DateTime, default=datetime.now, nullable=False)

class canal(Base):
    __tablename__ = 'canales'
    id = Column(Integer, primary_key=True, autoincrement=True)
    codigoCanal = Column(String(50), index=True)
    descripcionCanal = Column(String(255), index=True)
    created_at = Column(DateTime, default=datetime.now, nullable=False)

class capsula(Base):
    __tablename__ = 'capsulas'
    id = Column(Integer, primary_key=True, autoincrement=True)
    codigoCapsula = Column(String(30), index=True)
    descripcionCapsula = Column(String(30), index=True)
    created_at = Column(DateTime, default=datetime.now, nullable=False)

class color(Base):
    __tablename__ = 'colores'
    id = Column(Integer, primary_key=True, autoincrement=True)
    codigoColor = Column(String(50), index=True)
    descripcionColor = Column(String(255), index=True)
    valor = Column(String(50), index=True)
    descripcionValor = Column(String(255), index=True)
    created_at = Column(DateTime, default=datetime.now, nullable=False)
    
class division(Base):
    __tablename__ = 'divisiones'
    id = Column(Integer, primary_key=True, autoincrement=True)
    codigoDivision = Column(String(50), index=True)
    descripcionDivision = Column(String(30), index=True)
    created_at = Column(DateTime, default=datetime.now, nullable=False)

class edad(Base):
    __tablename__ = 'edades'
    id = Column(Integer, primary_key=True, autoincrement=True)
    codigoEdad = Column(String(50), index=True)
    descripcionEdad = Column(String(30), index=True)
    created_at = Column(DateTime, default=datetime.now, nullable=False)

class genero(Base):
    __tablename__ = 'generos'
    id = Column(Integer, primary_key=True)
    codigoGenero = Column(String(50), index=True)
    descripcionGenero = Column(String(30), index=True)
    created_at = Column(DateTime, default=datetime.now, nullable=False)

class marca(Base):
    __tablename__ = 'marcas'
    id = Column(Integer, primary_key=True, autoincrement=True)
    codigoMarca = Column(String(50), index=True)
    descripcionMarca = Column(String(30), index=True)
    created_at = Column(DateTime, default=datetime.now, nullable=False)
    
class markup(Base):
    __tablename__ = 'markups'
    id = Column(Integer, primary_key=True, autoincrement=True)
    marca_id = Column(Integer, ForeignKey('marcas.id'), nullable=False)
    tipoProducto = Column(String(50), index=True) #calzado, todo, indumentaria, accesorios,etc
    markup = Column(Numeric(18, 4), default=0)
    
class material(Base):
    __tablename__ = 'materiales'
    id = Column(Integer, primary_key=True, autoincrement=True)
    codigoMaterial = Column(String(50), index=True)
    descripcionMaterial = Column(String(30), index=True)
    created_at = Column(DateTime, default=datetime.now, nullable=False)

class objetivoGeneral(Base):
    __tablename__ = 'objetivoGeneral'
    id = Column(Integer, primary_key=True, autoincrement=True)
    codigoObjetivoGeneral = Column(String(50), index=True)
    descripcionObjetivoGeneral = Column(String(50), index=True)
    created_at = Column(DateTime, default=datetime.now, nullable=False)

class precioCompra(Base): #Esta tabla se genera mientras se va creando los articulos
    __tablename__ = 'preciosCompra'
    id = Column(Integer, primary_key=True, autoincrement=True)
    codigoArticulo = Column(String(50), index=True)
    precioCompra = Column(Numeric(18, 4), default=0)
    created_at = Column(DateTime, default=datetime.now, nullable=False)
    
class precioVenta(Base): #Esta tabla se genera mientras se va creando los articulos
    __tablename__ = 'preciosVenta'
    id = Column(Integer, primary_key=True, autoincrement=True)
    codigoArticulo = Column(String(50), index=True)
    precioVenta = Column(Numeric(18, 4), default=0)
    created_at = Column(DateTime, default=datetime.now, nullable=False)
    
class promo(Base):
    __tablename__ = 'promos'
    id = Column(Integer, primary_key=True, autoincrement=True)
    codigoPromo = Column(String(50), index=True)
    descripcionPromo = Column(String(30), index=True)
    created_at = Column(DateTime, default=datetime.now, nullable=False)
    
class sap(Base):
    __tablename__ = 'grupoSap'
    id = Column(Integer, primary_key=True)
    codigoGrupoSap = Column(String(50), index=True)
    descripcionGrupoSap = Column(String(30), index=True)
    created_at = Column(DateTime, default=datetime.now, nullable=False)
    
class segmentacionMarathon(Base):
    __tablename__ = 'segmentacionMarathon'
    id = Column(Integer, primary_key=True)
    codigoSegmentacionMarathon = Column(String(50), index=True)
    descripcionSegmentacionMarathon = Column(String(30), index=True)
    created_at = Column(DateTime, default=datetime.now, nullable=False)
    
class segmentacionProveedor(Base):
    __tablename__ = 'segmentacionProveedor'
    id = Column(Integer, primary_key=True, autoincrement=True)
    codigoSegmentacionProveedor = Column(String(50), index=True)
    descripcionSegmentacionProveedor = Column(String(30), index=True)
    created_at = Column(DateTime, default=datetime.now, nullable=False)

class silueta(Base):
    __tablename__ = 'silueta'
    id = Column(Integer, primary_key=True, autoincrement=True)
    codigoSilueta = Column(String(50), index=True)
    descripcionSilueta = Column(String(30), index=True)
    created_at = Column(DateTime, default=datetime.now, nullable=False)

class Articulo(Base):
    __tablename__ = 'articulos'

    # 0. id original de la base de datos
    id = Column(Integer, primary_key=True, autoincrement=False)
    
    # 1 - 5
    codigo = Column(String(50), index=True, nullable=False)
    descripcion = Column(String(255))
    tipoProducto = Column(String(50))
    descripcionProducto = Column(String(255))
    grupoSAP = Column(String(50))
    
    # 6 - 10
    descripcionGrupoSAP = Column(String(255))
    marca = Column(String(50), index=True)
    descripcionMarca = Column(String(255))
    genero = Column(String(50))
    descripcionGenero = Column(String(255))
    
    # 11 - 15
    silueta = Column(String(50))
    descripcionSilueta = Column(String(255))
    uso = Column(String(50))
    descripcionUso = Column(String(255))
    codigoBarra = Column(String(50), index=True) # EAN / UPC
    
    # 16 - 20
    talle = Column(String(50))
    descripcionTalle = Column(String(255))
    valorTalle = Column(String(50))
    descripcionValorTalle = Column(String(255))
    color = Column(String(50))
    
    # 21 - 25
    descripcionColor = Column(String(255))
    valor = Column(String(50))
    descripcionValor = Column(String(255))
    nombreProveedor = Column(String(255), index=True)
    codigoMedida = Column(String(50))
    
    # 26 - 30
    tipoMedida = Column(String(100))
    medida = Column(String(50))
    codigoGen = Column(String(50))
    genero2 = Column(String(50))
    canal = Column(String(50))
    
    # 31 - 35
    codigoCapsula = Column(String(50))
    descripcionCapsula = Column(String(255))
    codigoDivision = Column(String(50))
    descripcionDivision = Column(String(255))
    codigoTemporada = Column(String(50))
    
    # 36 - 38
    descripcionTemporada = Column(String(255))
    grupo = Column(String(50))
    descripciongrupo = Column(String(255))
    
    # Control interno de base de datos
    created_at = Column(DateTime, default=datetime.now, nullable=False)
    
class ArticuloComplementario(Base):
    __tablename__ = 'articulosComplementarios'
    id = Column(Integer, primary_key=True)
    codigo = Column(String(50), index=True)
    codigoEdad = Column(String(50), index=True)
    codigoMaterial = Column(String(50), index=True)
    codigoSegmentacionProveedor = Column(String(50), index=True)
    codigoSegmentacionMarathon = Column(String(50), index=True)
    codigoVidriera = Column(String(50), index=True)
    codigoAnio = Column(String(50), index=True)
    codigoBarra = Column(String(50), index=True)
    codigoCruzar = Column(String(50), index=True)
    objetivoGeneral = Column(String(50), index=True)
    created_at = Column(DateTime, default=datetime.now, nullable=False)

class TalleMaestro(Base):
    __tablename__ = 'talles'

    id = Column(Integer, primary_key=True, autoincrement=False) # Mantenemos el ID viejo para no romper relaciones históricas
    codigoBarra = Column(String(50), nullable=True)
    codigoTalle = Column(String(50), nullable=True, index=True) # ej: 'A01', 'UNI'. Agregamos índice para búsquedas rápidas
    descripcionTalle = Column(String(150), nullable=True)
    valorTalle = Column(String(50), nullable=True) # ej: 'S', 'M', 'L'
    descripcionValorTalle = Column(String(150), nullable=True)
    codigoMedida = Column(String(50), nullable=True)
    tipoMedida = Column(String(100), nullable=True)
    medida = Column(String(50), nullable=True)
    codigoGen = Column(String(20), nullable=True)
    genero = Column(String(50), nullable=True)
    created_at = Column(DateTime, default=datetime.now, nullable=False)

class temporada(Base):
    __tablename__ = 'temporadas'
    id = Column(Integer, primary_key=True, autoincrement=True)
    codigoTemporada = Column(String(50), index=True)
    descripcionTemporada = Column(String(30), index=True)
    created_at = Column(DateTime, default=datetime.now, nullable=False)
    
class tipoProducto(Base):
    __tablename__ = 'tipoProductos'
    id = Column(Integer, primary_key=True, autoincrement=True)
    codigoTipoProducto = Column(String(50), index=True)
    descripcionTipoProducto = Column(String(30), index=True)
    created_at = Column(DateTime, default=datetime.now, nullable=False)

class uso(Base):
    __tablename__ = 'usos'
    id = Column(Integer, primary_key=True, autoincrement=True)
    codigoUso = Column(String(50), index=True)
    descripcionUso = Column(String(30), index=True)
    created_at = Column(DateTime, default=datetime.now, nullable=False)

class vidriera(Base):
    __tablename__ = 'vidriera'
    id = Column(Integer, primary_key=True, autoincrement=True)
    codigoVidriera = Column(String(50), index=True)
    descripcionVidriera = Column(String(30), index=True)
    created_at = Column(DateTime, default=datetime.now, nullable=False)
    