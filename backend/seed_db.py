# backend/seed_db.py
import logging
from database import SessionLocal
from models import Proveedor, ArticuloGasto, VariacionArticulo, MapeoTalle, Sucursal, SucursalVariacion

# Configuración de logs para ver el progreso en consola
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def seed_db():
    db = SessionLocal()
    try:
        # 1. IMPORTACIÓN DE DICCIONARIOS TEMPORALES
        # Asegúrate de haber copiado estos archivos a la carpeta backend/
        try:
            import gastos_database as gd
            import prov_database as pd
            import ocr_database as od
            # El de talles de Crocs lo integramos directo por ser pequeño, 
            # o puedes importarlo si prefieres.
        except ImportError as e:
            logger.error(f"Falta un archivo de datos: {e}")
            return

        # --- SECCIÓN A: PROVEEDORES (UNIFICACIÓN GASTOS + MERCADERÍA) ---
        logger.info("Iniciando carga de Proveedores...")
        
        # Procesar Gastos
        for cuit, info in gd.PROVEEDORES_DB.items():
            if "opciones" in info:
                for sub_key, sub_info in info["opciones"].items():
                    registrar_o_actualizar_prov(db, cuit, sub_info["codProv"], sub_info["razonSocial"], tipo="GASTOS")
            else:
                registrar_o_actualizar_prov(db, cuit, info["codProv"], info["razonSocial"], tipo="GASTOS")

        # Procesar Mercadería (Si ya existe por CUIT, actualiza marca/pivot)
        for cuit, info in pd.cuit_proveedores.items():
            registrar_o_actualizar_prov(
                db, cuit, info['cod_prov'], 
                marca=info['marca'], 
                pivot=info['pivot'], 
                tipo="MERCADERIA"
            )

        # --- SECCIÓN B: ARTÍCULOS DE GASTOS Y VARIACIONES ---
        logger.info("Iniciando carga de Artículos de Gastos...")
        for clave, info in gd.ARTICULOS_DB.items():
            art = db.query(ArticuloGasto).filter_by(clave_busqueda=clave).first()
            if not art:
                art = ArticuloGasto(
                    clave_busqueda=clave,
                    articulo_sap=info.get("articulo"),
                    descripcion_sap=info.get("descripcion"),
                    cuenta_contable=info.get("cuenta")
                )
                db.add(art)
                db.flush()

            if "variaciones" in info:
                for v_text in info["variaciones"]:
                    if not db.query(VariacionArticulo).filter_by(texto_variacion=v_text, articulo_id=art.id).first():
                        db.add(VariacionArticulo(texto_variacion=v_text, articulo_id=art.id))

        # --- SECCIÓN C: TALLES (CROCS) ---
        logger.info("Iniciando carga de Talles Crocs...")
        TALLES_CROCS = {
            'C2/3': 19, 'C4/5': 21, 'C6/7': 23, 'C8/9': 25, 'C10/11': 27,
            'C12/13': 29, 'J1': 31, 'J2': 32, 'J3': 33, 'M3/W5': 35,
            'M4/W6': 36, 'M5/W7': 37, 'M6/W8': 38, 'M7/W9': 39, 'M8/W10': 40,
            'M9/W11': 41, 'M10/W12': 42, 'M11': 43, 'M12': 44, 'M13': 45,
        }
        for orig, dest in TALLES_CROCS.items():
            if not db.query(MapeoTalle).filter_by(marca_nombre="CROCS", talle_origen=orig).first():
                db.add(MapeoTalle(marca_nombre="CROCS", talle_origen=orig, talle_destino=str(dest)))

        # --- SECCIÓN D: CONFIGURACIÓN OCR ---
        logger.info("Iniciando carga de Sucursales y Variaciones OCR...")
        for prov, sucursales_dict in od.ocr_database.items():
            for cod_suc, lista_variaciones in sucursales_dict.items():
                # 1. Creamos la Sucursal (Entidad Limpia)
                sucursal = db.query(Sucursal).filter_by(codigo_sucursal=cod_suc).first()
                if not sucursal:
                    sucursal = Sucursal(
                        provincia=prov,
                        codigo_sucursal=cod_suc,
                        nombre_sucursal=lista_variaciones[0] # Usamos el primero como oficial
                    )
                    db.add(sucursal)
                    db.flush() # Para obtener el ID

                # 2. Cargamos todas sus variaciones para el matching del OCR
                for texto in lista_variaciones:
                    # Evitamos duplicar la misma variación para la misma sucursal
                    existe_var = db.query(SucursalVariacion).filter_by(
                        texto_variacion=texto, 
                        sucursal_id=sucursal.id
                    ).first()
                    
                    if not existe_var:
                        nueva_var = SucursalVariacion(
                            texto_variacion=texto,
                            sucursal_id=sucursal.id
                        )
                        db.add(nueva_var)

        db.commit()
        logger.info("✅ PROCESO DE SEEDING FINALIZADO EXITOSAMENTE.")

    except Exception as e:
        db.rollback()
        logger.error(f"❌ Error crítico en el seeding: {str(e)}")
    finally:
        db.close()

def registrar_o_actualizar_prov(db, cuit, cod_prov, razon_social=None, marca=None, pivot=None, tipo="GASTOS"):
    # Ahora buscamos por cod_prov porque decidiste que es tu clave única (al igual que en SAP)
    prov = db.query(Proveedor).filter_by(cod_prov=cod_prov).first()
    
    if not prov:
        # Si no existe, lo creamos de cero
        nuevo = Proveedor(
            cuit=cuit, 
            cod_prov=cod_prov, 
            razon_social=razon_social, 
            marca=marca, 
            pivot=pivot, 
            tipo=tipo
        )
        db.add(nuevo)
    else:
        # Si ya existe (mismo código SAP), actualizamos sus datos para que no queden vacíos
        if razon_social: prov.razon_social = razon_social
        if marca: prov.marca = marca
        if pivot: prov.pivot = pivot
        if cuit: prov.cuit = cuit # Aseguramos que el CUIT sea el correcto
        
        # PRIORIDAD: Si el registro viene de mercadería, cambiamos el tipo.
        # Esto es porque un proveedor de mercadería es más relevante en tu sistema.
        if tipo == "MERCADERIA":
            prov.tipo = "MERCADERIA"

if __name__ == "__main__":
    seed_db()