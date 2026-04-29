from data.gastos_database import PROVEEDORES_DB, ARTICULOS_DB
from datetime import datetime, timedelta
import re
import pandas as pd


def _normalizar_texto(valor):
    """
    Normaliza texto para comparaciones (mayúsculas, sin espacios extra).
    """
    if not valor:
        return ""
    valor_str = str(valor).strip().upper()
    return " ".join(valor_str.split())


def obtener_codprov_por_cuit_y_proveedor(cuit_input, proveedor_input):
    """
    Busca el código de proveedor. Si el CUIT es el compartido (20222222223),
    decide basándose exclusivamente en el texto de la columna PROVEEDOR.
    """
    if not proveedor_input:
        return None
        
    proveedor_norm = _normalizar_texto(proveedor_input)
    cuit_str = str(cuit_input).strip() if cuit_input and not pd.isna(cuit_input) else ""

    # CASO ESPECIAL: CUIT COMPARTIDO
    if cuit_str == "20222222223":
        if "TIQUEB" in proveedor_norm:
            return "TIQUEB"
        if "TIQUEX" in proveedor_norm:
            return "TIQUEX"
        # Si por alguna razón el CUIT es ese pero no dice TIQUEB/X, 
        # intentamos buscar en las opciones de la DB por las dudas
    
    # BUSQUEDA ESTÁNDAR EN DB
    entry = PROVEEDORES_DB.get(cuit_str)
    if entry:
        # Si tiene opciones (como el caso del CUIT compartido)
        if "opciones" in entry:
            for clave_opcion, data in entry["opciones"].items():
                # Si el nombre del proveedor contiene la clave (ej: "TIQUEB" está en "TIQUEB SALTA")
                if _normalizar_texto(clave_opcion) in proveedor_norm:
                    return data.get("codProv")
        else:
            return entry.get("codProv")

    # FALLBACK FINAL: Búsqueda por palabra clave aunque el CUIT no coincida
    if "TIQUEB" in proveedor_norm:
        return "TIQUEB"
    if "TIQUEX" in proveedor_norm:
        return "TIQUEX"

    return None

# Reglas de comentarios que afectan los valores de artículo, descripción, cuenta y OCR
# Estas reglas se aplican cuando un comentario específico está presente
# Estructura similar a GASTOS_DB con variaciones para evitar duplicación
COMENTARIOS_RULES = {
    "APERTURA CONTABLE MARKETING": {
        "tipo": "ocr_especial",
        "ocr_code": "249913-1",
        "ocr_code2_source": "SUCURSAL",  # OcrCode2 viene de la columna SUCURSAL
        # Mantiene artículo, descripción y cuenta base
        "variaciones": [
            "APERTURA CONTABLE MARKETING",
            "APERTURA MARKETING",
            "MARKETING APERTURA",
        ],
    },
    "APERTURA CONTABLE SUPERVISION": {
        "tipo": "ocr_especial",
        "ocr_code": "249907-1",
        "ocr_code2_source": "SUCURSAL",  # OcrCode2 viene de la columna SUCURSAL
        # Mantiene artículo, descripción y cuenta base
        "variaciones": [
            "APERTURA CONTABLE SUPERVISION",
            "APERTURA SUPERVISION",
            "SUPERVISION APERTURA",
        ],
    },
    "ATENCION TECNICA IMPRESORA": {
        "tipo": "articulo_alternativo",
        "articulo_alternativo": "INFORMATICA LOCALES",
        # Usa artículo, descripción y cuenta de INFORMATICA LOCALES
        "variaciones": [
            "ATENCION TECNICA IMPRESORA",
            "TECNICA IMPRESORA",
            "MANTENIMIENTO IMPRESORA",
            "REPARACION IMPRESORA",
            "ATENCION IMPRESORA",
        ],
    },
    "SERVICIO DE TELEFONIA E INTERNET": {
        "tipo": "articulo_especifico",
        "articulo": "359",
        "descripcion": "SERVICIO TELEFONIA e INTERNET",
        "cuenta": "5.4.010.17.001",
        # Mantiene código de proveedor base
        "variaciones": [
            "SERVICIO DE TELEFONIA E INTERNET",
            "SERVICIO TELEFONIA E INTERNET",
            "TELEFONIA E INTERNET",
            "SERVICIO TELEFONIA",
            "TELEFONIA INTERNET",
            "SERVICIO DE TELEFONIA",
            "en art debe usarse SERVICIO DE TELEFONIA E INTERNET",
            "en art debe usarse SERVICIO TELEFONIA E INTERNET",
        ],
    },
}


def buscar_regla_comentario(comentario_input):
    """
    Busca si un comentario tiene reglas especiales que afecten los valores.
    Primero busca en las variaciones de cada regla, luego busca si alguna regla
    está contenida en el comentario.
    
    Args:
        comentario_input: Texto del comentario
    
    Returns:
        dict: Regla encontrada (sin las variaciones) o None si no hay regla especial
    """
    if not comentario_input:
        return None
    
    comentario_normalizado = _normalizar_texto(comentario_input)
    
    # Buscar coincidencia exacta en las claves principales primero
    if comentario_normalizado in COMENTARIOS_RULES:
        regla = COMENTARIOS_RULES[comentario_normalizado].copy()
        # Remover variaciones del resultado (no son necesarias para el procesamiento)
        regla.pop("variaciones", None)
        return regla
    
    # Buscar en las variaciones de cada regla
    for regla_key, regla_value in COMENTARIOS_RULES.items():
        variaciones = regla_value.get("variaciones", [])
        for variacion in variaciones:
            variacion_norm = _normalizar_texto(variacion)
            # Si la variación coincide exactamente o está contenida en el comentario
            if variacion_norm == comentario_normalizado or variacion_norm in comentario_normalizado:
                regla = regla_value.copy()
                # Remover variaciones del resultado
                regla.pop("variaciones", None)
                return regla
    
    # Buscar si alguna regla clave está contenida en el comentario (fallback)
    for regla_key, regla_value in COMENTARIOS_RULES.items():
        regla_key_norm = _normalizar_texto(regla_key)
        # Si la regla está contenida en el comentario
        if regla_key_norm in comentario_normalizado:
            regla = regla_value.copy()
            # Remover variaciones del resultado
            regla.pop("variaciones", None)
            return regla
    
    return None


def _buscar_articulo_por_comentario(comentario_input):
    """
    Busca en ARTICULOS_DB a partir del comentario usando claves y variaciones.
    """
    if not comentario_input:
        return None

    comentario_norm = _normalizar_texto(comentario_input)

    # Buscar coincidencia exacta con la clave principal
    if comentario_norm in ARTICULOS_DB:
        return ARTICULOS_DB[comentario_norm]

    # Buscar en variaciones
    for key, entry in ARTICULOS_DB.items():
        variaciones = entry.get("variaciones", [])
        for variacion in variaciones:
            variacion_norm = _normalizar_texto(variacion)
            if (
                comentario_norm == variacion_norm
                or comentario_norm in variacion_norm
                or variacion_norm in comentario_norm
            ):
                return entry

    return None


def obtener_valores_por_comentario(comentario_input, sucursal=None):
    """
    Obtiene valores priorizando REGLAS ESPECIALES sobre la base general.
    """
    # 1. Normalización inicial
    comentario_str = str(comentario_input).strip() if comentario_input else ""
    
    # 2. PRIORIDAD 1: Buscar en COMENTARIOS_RULES (Reglas específicas)
    regla = buscar_regla_comentario(comentario_str)
    
    resultado = {
        "articulo": None,
        "descripcion": None,
        "cuenta": None,
        "ocr_code": None,
        "ocr_code2": None,
    }

    if regla:
        tipo_regla = regla.get("tipo")
        
        if tipo_regla == "articulo_especifico":
            resultado["articulo"] = regla.get("articulo")
            resultado["descripcion"] = regla.get("descripcion")
            resultado["cuenta"] = regla.get("cuenta")
            return resultado # Retorno inmediato, ya encontramos la regla maestra

        elif tipo_regla == "articulo_alternativo":
            articulo_alt_key = regla.get("articulo_alternativo")
            articulo_alt_data = ARTICULOS_DB.get(articulo_alt_key)
            if articulo_alt_data:
                resultado["articulo"] = articulo_alt_data["articulo"]
                resultado["descripcion"] = articulo_alt_data["descripcion"]
                resultado["cuenta"] = articulo_alt_data["cuenta"]
                return resultado

        elif tipo_regla == "ocr_especial":
            # Si es OCR especial, primero necesitamos los datos base del artículo
            articulo_base = _buscar_articulo_por_comentario(comentario_str)
            if articulo_base:
                resultado["articulo"] = articulo_base["articulo"]
                resultado["descripcion"] = articulo_base["descripcion"]
                resultado["cuenta"] = articulo_base["cuenta"]
            
            resultado["ocr_code"] = regla.get("ocr_code")
            if regla.get("ocr_code2_source") == "SUCURSAL" and sucursal:
                resultado["ocr_code2"] = f"{str(sucursal).strip().zfill(6)}-2"
            return resultado

    # 3. PRIORIDAD 2: Si no hubo regla específica, buscar en ARTICULOS_DB (Base general)
    articulo_data = _buscar_articulo_por_comentario(comentario_str)
    if articulo_data:
        resultado["articulo"] = articulo_data["articulo"]
        resultado["descripcion"] = articulo_data["descripcion"]
        resultado["cuenta"] = articulo_data["cuenta"]
        return resultado

    return None # Si no encontró nada en ninguna parte


def convertir_fecha_formato(fecha_input):
    """
    Convierte una fecha al formato YYYYMMDD (ej: 20260105).
    Acepta varios formatos de entrada comunes de Excel.
    
    Args:
        fecha_input: Fecha en cualquier formato (datetime, string, Timestamp de pandas, etc.)
    
    Returns:
        str: Fecha en formato YYYYMMDD o None si no se puede convertir
    """
    if fecha_input is None or (isinstance(fecha_input, str) and not fecha_input.strip()):
        return None
    
    # Si es Timestamp de pandas
    try:
        import pandas as pd
        if isinstance(fecha_input, pd.Timestamp):
            return fecha_input.strftime("%Y%m%d")
    except:
        pass
    
    # Si es datetime de Python
    if isinstance(fecha_input, datetime):
        try:
            return fecha_input.strftime("%Y%m%d")
        except:
            pass
    
    # Si es string
    if isinstance(fecha_input, str):
        fecha_str = str(fecha_input).strip()
        # Si ya está en formato YYYYMMDD (8 dígitos)
        if len(fecha_str) == 8 and fecha_str.isdigit():
            return fecha_str
        
        # Intentar parsear como datetime
        try:
            # Intentar varios formatos comunes
            formatos = [
                "%Y-%m-%d",
                "%d/%m/%Y",
                "%d-%m-%Y",
                "%Y/%m/%d",
                "%d.%m.%Y",
                "%Y-%m-%d %H:%M:%S",
                "%d/%m/%Y %H:%M:%S",
            ]
            
            for formato in formatos:
                try:
                    dt = datetime.strptime(fecha_str, formato)
                    return dt.strftime("%Y%m%d")
                except ValueError:
                    continue
            
            # Si es un número (días desde 1900-01-01, formato Excel)
            if fecha_str.replace(".", "").replace("-", "").isdigit():
                try:
                    # Excel cuenta días desde 1900-01-01
                    dias_excel = float(fecha_str)
                    fecha_base = datetime(1900, 1, 1)
                    # Excel tiene un bug: cuenta 1900 como año bisiesto
                    dias_calcular = int(dias_excel) - 2
                    if dias_excel > 59:
                        dias_calcular -= 1
                    fecha_resultado = fecha_base + timedelta(days=dias_calcular)
                    return fecha_resultado.strftime("%Y%m%d")
                except:
                    pass
        except:
            pass
    
    # Si tiene método strftime (otros tipos de datetime)
    if hasattr(fecha_input, 'strftime'):
        try:
            return fecha_input.strftime("%Y%m%d")
        except:
            pass
    
    # Si tiene método to_pydatetime (Timestamp de pandas)
    if hasattr(fecha_input, 'to_pydatetime'):
        try:
            dt = fecha_input.to_pydatetime()
            return dt.strftime("%Y%m%d")
        except:
            pass
    
    return None
