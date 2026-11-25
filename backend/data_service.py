#Este archivo centralizará las consultas. Esto en programación se llama Repository Pattern.
from typing import Dict, List, Optional
from database import SessionLocal
from models import MapeoTalle, Proveedor

def obtener_diccionario_talles(marca: str) -> Dict[str, str]:
    """
    Transforma la tabla de la DB en un diccionario {origen: destino}
    Esto hace que la migración de los scripts viejos sea casi instantánea.
    """
    db = SessionLocal()
    try:
        resultados = db.query(MapeoTalle).filter(MapeoTalle.marca_nombre == marca).all()
        # Convertimos a diccionario: {'M4/W6': '36', 'M5/W7': '37'}
        return {r.talle_origen: r.talle_destino for r in resultados}
    finally:
        db.close()

def obtener_proveedor_por_cuit(cuit: str) -> Optional[Proveedor]:
    db = SessionLocal()
    try:
        return db.query(Proveedor).filter(Proveedor.cuit == cuit).first()
    finally:
        db.close()