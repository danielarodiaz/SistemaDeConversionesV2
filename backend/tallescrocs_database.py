# Base de datos de talles de Crocs
# Mapeo de código de talle de Crocs a talle numérico para búsqueda en CEGID

TALLES_CROCS = {
    'C2/3': 19,
    'C4/5': 21,
    'C6/7': 23,
    'C8/9': 25,
    'C10/11': 27,
    'C12/13': 29,
    'J1': 31,
    'J2': 32,
    'J3': 33,
    'M3/W5': 35,
    'M4/W6': 36,
    'M5/W7': 37,
    'M6/W8': 38,
    'M7/W9': 39,
    'M8/W10': 40,
    'M9/W11': 41,
    'M10/W12': 42,
    'M11': 43,
    'M12': 44,
    'M13': 45,
}

def obtener_talle_numerico_crocs(codigo_talle):
    """
    Convierte un código de talle de Crocs a su equivalente numérico para búsqueda en CEGID.
    
    Args:
        codigo_talle: Código de talle de Crocs (ej: 'C2/3', 'J1', 'M3/W5', etc.)
    
    Returns:
        int: Talle numérico correspondiente, o None si no se encuentra
    """
    codigo_talle = str(codigo_talle).strip().upper()
    return TALLES_CROCS.get(codigo_talle)

def obtener_lista_talles_crocs():
    """
    Retorna la lista completa de códigos de talles de Crocs disponibles.
    
    Returns:
        list: Lista de códigos de talles
    """
    return list(TALLES_CROCS.keys())

