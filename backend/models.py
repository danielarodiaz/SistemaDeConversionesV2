from sqlalchemy import Column, Integer, String, ForeignKey, Table, true
from sqlalchemy.orm import relationship
from sqlalchemy.ext.declarative import declarative_base

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