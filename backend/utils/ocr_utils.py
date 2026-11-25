import re
try:
    from data.ocr_database import ocr_database
except ModuleNotFoundError:
    from backend.data.ocr_database import ocr_database

# 🔁 Mapeo de variantes a nombre base
remitente_map = {
    "GRUPO 7": ["GRUPO 7", "GRUPPO 7 SA", "GRUPO7", "GRUPPO 7 S.A.","GRUPPO 7 S.A","GRUPPO 7 S.A FABRICA DE MADIA","GRUPPO 7 S.A. FABRICA DE MADIA"],
    "BESTSOX": ["BESTSOX", "BEST SOX SA", "BEST SOC", "BEST SOC SA", "BEST SOX", "BESTO SOX SA","BEST SOX S.A."],
    "KENYAN": ["KENYAN", "KENIA", "KENYAN SA"],
    "DISTRINANDO": ["DISTRINANDO"],
    "KOKUEN": ["KOKUEN"],
    #Agregar más proveedores
}

def remitente_es_excepcion(remitente_raw):
    for variantes in remitente_map.values():
        for variante in variantes:
            if variante in remitente_raw:
                return True
    return False

# 📍 Conflictos conocidos con calle + número de puerta
ocr_conflictos_con_puerta = {
    "TUC": {
        "SAN MARTIN": {
            "variantes": ["GRAL JOSE DE SAN MARTIN", "SAN MARTIN", "S MARTIN"],
            "puertas": {
                "1234": "240201",
                "1399": "240202"
            }
        }
    },
    "SFE": {
        "SAN LUIS": {
            "variantes": ["SAN LUIS", "S LUIS"],
            "puertas": {
                "1330": "200102",
                "1261": "200103"
            }
        }
    }
}

# 🧠 Excepciones OCR basadas en coincidencias parciales
ocr_excepciones_especificas = [
    {
        "dom_keywords": ["25 DE MAYO", "SAN MARTIN"],
        "loc_keywords": ["TINOGASTA", "CATAMARCA", "TINOGASTA-CATAMARCA", "BELEN-CATAMARCA", "BELEN CATAMARCA"],
        "code": "240001"
    },
    {
        "dom_keywords": ["GRAL SAN MARTIN S/N"],
        "loc_keywords": ["LA COCHA TUC"],
        "code": "240001"
    },
        {
        "dom_keywords": ["GORRITI"],
        "loc_keywords": ["GUEMES SALTA"],
        "code": "240001"
    },
    {
        "dom_keywords": ["SAN MARTIN"],
        "loc_keywords": ["CAFAYATE "],
        "code": "240001"
    },
    # {
    #     "dom_keywords": ["ALBERDI"],
    #     "loc_keywords": ["CORDOBA"],
    #     "code": "999999"
    # },
]

def is_within_tolerance(actual, expected, tolerance=30):
    """Verifica si un número está dentro de un rango de tolerancia"""
    try:
        actual = int(actual)
        expected = int(expected)
        
        # Caso especial: si el actual termina en ceros y el esperado no
        # Ejemplo: 13990 vs 1399 → 13990/10 = 1399
        if actual % 10 == 0 and actual // 10 == expected:
            return True
            
        # Caso especial: si el esperado termina en ceros y el actual no
        # Ejemplo: 1399 vs 13990 → 1399*10 = 13990
        if expected % 10 == 0 and expected // 10 == actual:
            return True
            
        return abs(actual - expected) <= tolerance
    except (ValueError, TypeError):
        return False

def calcular_ocr_code(destinatario, localidad, domicilio, remitente="", puerta=""):
    destinatario_raw = str(destinatario).upper()
    domicilio_raw = re.sub(r'\s+', ' ', str(domicilio).upper().strip())  # Normalizar espacios múltiples
    localidad_raw = str(localidad).upper()
    remitente_raw = str(remitente).upper()
    puerta_raw = str(puerta).strip().upper()
    direccion_completa  = f"{domicilio_raw} {puerta_raw}".strip()
    
    print("🔍 === INICIO DEBUG OCR ===")
    print(f"📥 Datos: Dest='{destinatario_raw}' | Dom='{domicilio_raw}' | Loc='{localidad_raw}' | Rem='{remitente_raw}' | Pta='{puerta_raw}'")
    
    # 1️⃣ Número de 6 dígitos en destinatario
    match = re.search(r"\d{6}", destinatario_raw)
    if match:
        code = match.group(0)
        print(f"✅ Código 6 dígitos encontrado: {code}")
        for provincia_data in ocr_database.values():
            if code in provincia_data:
                return f"{code}-1"
        print(f"❌ Código {code} NO encontrado en BD")
    
    # 2️⃣ Verificar si es remitente de excepción
    es_excepcion = remitente_es_excepcion(remitente_raw)
    print(f"📋 Es excepción: {es_excepcion}")

    # 3️⃣ MARATHON o BLANCO, pero ignorar si el remitente es de excepción
    if ("MARATHON" in destinatario_raw or "BLANCO" in destinatario_raw) and not es_excepcion:
        print(f"✅ MARATHON/BLANCO detectado → 240001-1")
        return "240001-1"

    # 4️⃣ Inferencia por provincia
    provincia = ""
    if any (p in localidad_raw for p in ["ROSARIO","ROSARIO (CAPITAL)"]):
        provincia = "SFE"
    elif any(p in localidad_raw for p in ["SALTA", "JVG","J V GONZALEZ SALTA", "GUEMES", "TARTAGAL SALTA", "METAN", "METAN SALTA","TARTAGAL","J V GONZALEZ","SALTA (CAPITAL)","JOAQUIN V. GONZALEZ"]):
        provincia = "SAL"
    elif any(p in localidad_raw for p in ["TUCUMAN","TUCUAMN","TUUCMAN","S M DE TUCUMAN","S.M TUCUMAN","SAN MIGUEL DE TUCUMA","TAFI VIEJO","T VIEJO TUCUMAN", "CONCEPCION", "YERBA","YERBA BUENA","Y BUENA TUCUMAN","YERBA BUENA TUC", "AGUILARES", "MONTEROS", "CONCEPCION TUCUMAN", "MONMTEROS TUCUMAN","AGUILARES TUCUMAN","CONCEP TUCUMAN","MONTEROS TUCUMAN"]):
        provincia = "TUC"
    elif any(p in localidad_raw for p in ["LIB GRAL SAN MARTIN","LIB GRAL S MARTIN","LESDEMA JUJUY", "JUJUY", "LEDESMA-JUJUY","LDOR. GRAL. SAN MART","L GRAL SAN MARTIN"]):
        provincia = "JUJ"
    elif any(p in localidad_raw for p in ["BS AS", "BUENOS AIRES", "BS. AS."]):
        provincia = "BAS"
        
    print(f"🏛️ Provincia detectada: {provincia}")

    # 5️⃣ Excepciones específicas por coincidencia parcial (PRIORITARIAS)
    for regla in ocr_excepciones_especificas:
        if any(keyword in domicilio_raw for keyword in regla["dom_keywords"]) and \
           any(keyword in localidad_raw for keyword in regla["loc_keywords"]):
            print(f"✅ Excepción específica: {regla['code']}")
            return f"{regla['code']}-1"

    # 6️⃣ Buscar coincidencia en base provincial, considerando conflicto con puerta si aplica
    if provincia and provincia in ocr_database:
        provincia_conflicto = ocr_conflictos_con_puerta.get(provincia, {})

        for code, keywords in ocr_database[provincia].items():
            for keyword in keywords:
                # Limpiar espacios extra en la comparación
                keyword_clean = re.sub(r'\s+', ' ', keyword.strip())
                domicilio_clean = domicilio_raw.strip()
                
                if keyword_clean in domicilio_clean:
                    print(f"✅ Coincidencia: '{keyword_clean}' en '{domicilio_clean}' → {code}")
                    conflicto_encontrado = False
                    for calle_base, reglas in provincia_conflicto.items():
                        variantes = reglas.get("variantes", [])
                        puertas_dict = reglas.get("puertas", {})

                        for var in variantes:
                            if keyword_clean == re.sub(r'\s+', ' ', var.strip()):
                                print(f"🚨 Conflicto detectado: '{keyword_clean}' → verificar puerta")
                                conflicto_encontrado = True
                                
                                # Verificar cada puerta en el diccionario con tolerancia
                                for puerta_esperada, codigo_esperado in puertas_dict.items():
                                    if is_within_tolerance(puerta_raw.lstrip("0"), puerta_esperada):
                                        print(f"✅ Puerta {puerta_raw} ≈ {puerta_esperada} → {codigo_esperado}")
                                        if codigo_esperado == code:
                                            return f"{code}-1"
                                
                        if conflicto_encontrado:
                            continue  # hay conflicto pero no coincidió puerta → seguir buscando

                    if not conflicto_encontrado:
                        return f"{code}-1"

                
    # 7️⃣ Buscar en toda la base si no se encontró antes
    for prov_data in ocr_database.values():
        for code, keywords in prov_data.items():
            for keyword in keywords:
                keyword_clean = re.sub(r'\s+', ' ', keyword.strip())
                domicilio_clean = domicilio_raw.strip()
                if keyword_clean in domicilio_clean:
                    print(f"✅ Coincidencia en toda BD: {code}")
                    return f"{code}-1"

    # 8️⃣ Fallback por defecto
    print(f"❌ No se encontró coincidencia → 240001-1")
    return "240001-1"
