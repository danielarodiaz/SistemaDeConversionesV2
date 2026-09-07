import unicodedata


def texto_catalogo(item):
    item = item or {}
    return f"{item.get('codigo', '')} {item.get('descripcion', '')} {item.get('label', '')}".upper()


def descripcion_catalogo(item):
    return ((item or {}).get("descripcion") or "").strip().upper()


def codigo_catalogo(item):
    return ((item or {}).get("codigo") or "").strip().upper()


def tipo_prefijo(tipo_sel):
    codigo = codigo_catalogo(tipo_sel)
    descripcion = descripcion_catalogo(tipo_sel)
    return {
        "ACC": "ACC",
        "ACCESORIOS": "ACC",
        "BIC": "BIC",
        "BICICLETAS": "BIC",
        "CAL": "CAL",
        "CALZADO": "CAL",
        "CLU": "CLU",
        "CLUBES": "CLU",
        "IND": "IND",
        "INDUMENTARIA": "IND",
        "MED": "MED",
        "MEDIAS": "MED",
        "VER": "CAL",
        "VERANO": "CAL",
    }.get(codigo) or {
        "ACCESORIOS": "ACC",
        "BICICLETAS": "BIC",
        "CALZADO": "CAL",
        "CLUBES": "CLU",
        "INDUMENTARIA": "IND",
        "MEDIAS": "MED",
        "VERANO": "CAL",
    }.get(descripcion)


def tipo_texto_talle(tipo_sel):
    codigo = codigo_catalogo(tipo_sel)
    descripcion = descripcion_catalogo(tipo_sel)
    return {
        "ACC": "ACCESORIOS",
        "BIC": "BICICLETA",
        "CAL": "CALZADO",
        "CLU": "INDUMENTARIA",
        "IND": "INDUMENTARIA",
        "MED": "MEDIAS",
        "VER": "CALZADO",
    }.get(codigo) or {
        "ACCESORIOS": "ACCESORIOS",
        "BICICLETAS": "BICICLETA",
        "CALZADO": "CALZADO",
        "CLUBES": "INDUMENTARIA",
        "INDUMENTARIA": "INDUMENTARIA",
        "MEDIAS": "MEDIAS",
        "VERANO": "CALZADO",
    }.get(descripcion)


def _contiene(texto, valores):
    return any(valor in texto for valor in valores)


def _normalizar(texto):
    texto = unicodedata.normalize("NFKD", str(texto or "").upper())
    return "".join(char for char in texto if not unicodedata.combining(char))


def _limpiar_espacios(texto):
    return " ".join(str(texto or "").split())


def _coincide_opcion(texto, opcion):
    texto_norm = _normalizar(texto)
    opcion_norm = _normalizar(opcion)
    if " " in opcion_norm:
        return opcion_norm in texto_norm
    return opcion_norm in set(texto_norm.split())


def _tokens_texto(texto):
    texto_norm = _normalizar(texto).replace("/", " ")
    return set(_limpiar_espacios(texto_norm).split())


def _es_tipo(tipo_sel, *valores):
    texto = texto_catalogo(tipo_sel)
    return _contiene(texto, valores)


def _normalizar_edad_para_talle(edad_sel):
    descripcion = descripcion_catalogo(edad_sel)
    if "ADULTO" in descripcion:
        return "ADULTO"
    if "NIÑO" in descripcion or "NINO" in descripcion:
        return "NIÑO"
    if "BEBE" in descripcion:
        return "BEBE"
    return descripcion


def filtrar_edades(tipo_sel, genero_sel, edades):
    if not edades:
        return []

    genero_texto = texto_catalogo(genero_sel)
    if _es_tipo(tipo_sel, "IND", "INDUMENTARIA"):
        permitidos = ["BEBE", "NIÑO", "NINO"]
        if "MUJER" in genero_texto or "FEM" in genero_texto:
            permitidos.append("ADULTO FEMENINO")
        elif "HOMBRE" in genero_texto or "MASC" in genero_texto or "UNISEX" in genero_texto:
            permitidos.append("ADULTO MASCULINO")
        else:
            return edades
    else:
        permitidos = ["ADULTO GENERAL", "BEBE", "NIÑO", "NINO"]

    filtradas = [
        item for item in edades
        if any(_coincide_opcion(texto_catalogo(item), permitido) for permitido in permitidos)
    ]
    return filtradas or edades


def filtrar_siluetas(tipo_sel, siluetas):
    tipo = codigo_catalogo(tipo_sel)
    if not tipo:
        return []
    if _es_tipo(tipo_sel, "CLU", "CLUBES"):
        prefijos = ("IND",)
    elif _es_tipo(tipo_sel, "VER", "VERANO"):
        prefijos = ("CAL",)
    else:
        prefijos = {
            "ACC": ("ACC",),
            "CAL": ("CAL",),
            "IND": ("IND",),
            "MED": ("MED",),
            "BIC": ("BIC",),
        }.get(tipo, (tipo,))
    filtradas = [s for s in siluetas if codigo_catalogo(s).startswith(prefijos)]
    return filtradas or siluetas


def valor_sugerido(genero_sel, edad_sel, valores_genero):
    genero = descripcion_catalogo(genero_sel)
    edad = descripcion_catalogo(edad_sel)
    valor = None

    if genero == "HOMBRE" and ("ADULTO MASCULINO" in edad or "ADULTO GENERAL" in edad):
        valor = "HOMBRE"
    elif genero == "MUJER" and ("ADULTO FEMENINO" in edad or "ADULTO GENERAL" in edad):
        valor = "MUJER"
    elif genero == "UNISEX" and "ADULTO MASCULINO" in edad:
        valor = "HOMBRE"
    elif genero == "UNISEX" and "ADULTO GENERAL" in edad:
        valor = "UNISEX"
    elif genero == "UNISEX" and ("NIÑO" in edad or "NINO" in edad):
        valor = "NIÑO"
    elif genero == "UNISEX" and "BEBE" in edad:
        valor = "BEBE"

    if not valor:
        return None
    return next((item for item in valores_genero if descripcion_catalogo(item) == valor), None)


def _variantes_basicas(texto):
    limpio = _limpiar_espacios(_normalizar(texto))
    if not limpio:
        return set()

    variantes = {limpio}
    palabras = limpio.split()
    if len(palabras) == 1:
        palabra = palabras[0]
        if palabra.endswith("Z"):
            variantes.add(f"{palabra[:-1]}CES")
        elif palabra.endswith(("A", "E", "I", "O", "U")):
            variantes.add(f"{palabra}S")
        elif not palabra.endswith("S"):
            variantes.add(f"{palabra}ES")
        if palabra.endswith("ES"):
            variantes.add(palabra[:-2])
        if palabra.endswith("S"):
            variantes.add(palabra[:-1])
    return {v for v in variantes if v}


def _terminos_silueta_acc(silueta_sel):
    silueta = descripcion_catalogo(silueta_sel)
    alias = {
        "ANTIPARRA": {"ANTIPARRA", "ANTIPARRAS"},
        "CANILLERA": {"CANILLERA", "CANILLERAS"},
        "CONO": {"CONO", "TORTUGA", "TORTUGA CONO"},
        "GORRA": {"GORRA", "GORRAS"},
        "GORRO": {"GORRO", "GORRO NAT"},
        "GRIP": {"GRIP", "CUBRE GRIP"},
        "GUANTE": {"GUANTE", "GUANTES", "GUANTES ARQ", "GUANTES OTROS"},
        "JIBBIT": {"JIBBIT", "JIBBITZ"},
        "MAT YOGA": {"MAT YOGA", "YOGA", "COLCHONETA"},
        "MOCHILA": {"MOCHILA", "MOCHILAS"},
        "PALETA": {"PALETA", "PALETA PADEL"},
        "PELOTA": {"PELOTA", "PELOTAS", "PELOTAS GRAL"},
        "PROTECTOR": {"PROTECTOR", "PROTECTOR BUCAL"},
        "RAQUETA": {"RAQUETA", "RAQUETA TENIS"},
        "RIÑONERA": {"RIÑONERA", "RINONERA", "RIÑONERAS", "RINONERAS"},
        "RODILLERA": {"RODILLERA", "RODILLERAS", "RODILLERA VOLEY"},
        "TOBILLERAS": {"TOBILLERA", "TOBILLERAS"},
        "VENDAS": {"VENDA", "VENDAS"},
        "YOGA MATE": {"YOGA", "MAT YOGA", "COLCHONETA"},
    }
    terminos = set(alias.get(silueta, set()))
    terminos.update(_variantes_basicas(silueta))
    return {_limpiar_espacios(_normalizar(t)) for t in terminos if t}


def _objetivo_contiene_termino(objetivo, termino):
    descripcion = _normalizar(descripcion_catalogo(objetivo))
    if not termino:
        return False
    if " " in termino:
        return termino in descripcion
    return termino in _tokens_texto(descripcion)


def _filtrar_objetivos_por_silueta_acc(objetivos, silueta_sel):
    terminos = _terminos_silueta_acc(silueta_sel)
    if not terminos:
        return objetivos
    filtrados = [
        objetivo for objetivo in objetivos
        if any(_objetivo_contiene_termino(objetivo, termino) for termino in terminos)
    ]
    if filtrados:
        return filtrados
    otros = [
        objetivo for objetivo in objetivos
        if descripcion_catalogo(objetivo) == "ACC OTROS"
    ]
    return otros or objetivos


def _filtrar_objetivos_por_uso_acc(objetivos, uso_sel):
    uso = descripcion_catalogo(uso_sel)
    if not uso:
        return objetivos

    uso_norm = _limpiar_espacios(_normalizar(uso))
    terminos = {uso_norm}
    if uso_norm == "FUTBOL GENERAL":
        terminos.add("FUTBOL")
    elif uso_norm == "TENIS":
        terminos.add("TENIS PADEL")
    elif uso_norm == "PADEL":
        terminos.add("TENIS PADEL")

    filtrados = [
        objetivo for objetivo in objetivos
        if any(_objetivo_contiene_termino(objetivo, termino) for termino in terminos)
    ]
    return filtrados or objetivos


def _objetivos_generales_pelota_acc(objetivos):
    return [
        objetivo for objetivo in objetivos
        if descripcion_catalogo(objetivo) in {"ACC PELOTAS GRAL", "ACC OTROS PELOTAS"}
    ]


def _filtrar_objetivos_pelota_acc(objetivos, uso_sel):
    uso = descripcion_catalogo(uso_sel)
    generales = _objetivos_generales_pelota_acc(objetivos)
    if not uso:
        return generales or objetivos

    uso_norm = _limpiar_espacios(_normalizar(uso))
    if uso_norm == "FUTBOL GENERAL" or uso_norm.startswith("FUTBOL "):
        exactos = [
            objetivo for objetivo in objetivos
            if _objetivo_contiene_termino(objetivo, uso_norm)
        ]
        filtrados = exactos or [
            objetivo for objetivo in objetivos
            if _objetivo_contiene_termino(objetivo, "FUTBOL")
        ]
        return filtrados + [objetivo for objetivo in generales if objetivo not in filtrados]

    exactos = [
        objetivo for objetivo in objetivos
        if _objetivo_contiene_termino(objetivo, uso_norm)
    ]
    return exactos or generales or objetivos


def filtrar_objetivos(tipo_sel, silueta_sel, uso_sel, objetivos):
    prefijo = tipo_prefijo(tipo_sel)
    if prefijo:
        por_tipo = [
            objetivo for objetivo in objetivos
            if descripcion_catalogo(objetivo).startswith(prefijo)
            or codigo_catalogo(objetivo).startswith(prefijo)
        ]
        por_tipo = por_tipo or objetivos
    else:
        por_tipo = [
            objetivo for objetivo in objetivos
            if "N/A" in f"{codigo_catalogo(objetivo)} {descripcion_catalogo(objetivo)}"
        ]
        return por_tipo or objetivos[:1]

    if prefijo != "ACC":
        return por_tipo

    por_silueta = _filtrar_objetivos_por_silueta_acc(por_tipo, silueta_sel)
    if descripcion_catalogo(silueta_sel) == "PELOTA":
        return _filtrar_objetivos_pelota_acc(por_silueta, uso_sel)
    por_uso = _filtrar_objetivos_por_uso_acc(por_silueta, uso_sel)
    return por_uso or por_silueta or por_tipo


def dedupe_descripciones(items):
    seen = set()
    values = []
    for item in items:
        descripcion = _limpiar_espacios((item or {}).get("descripcion"))
        if descripcion and descripcion not in seen:
            values.append(descripcion)
            seen.add(descripcion)
    return sorted(values)


def _tokens_descripcion(item):
    return set(_normalizar(descripcion_catalogo(item)).split())


def _filtrar_talles_por_genero(items, genero_sel):
    genero = descripcion_catalogo(genero_sel)
    if not genero:
        return items

    filtrados = []
    for item in items:
        tokens = _tokens_descripcion(item)
        tiene_hombre = "HOMBRE" in tokens
        tiene_mujer = "MUJER" in tokens
        tiene_unisex = "UNISEX" in tokens

        if genero == "HOMBRE" and not tiene_mujer and not tiene_unisex:
            filtrados.append(item)
        elif genero == "MUJER" and not tiene_hombre and not tiene_unisex:
            filtrados.append(item)
        elif genero == "UNISEX" and not tiene_mujer:
            filtrados.append(item)

    if genero == "UNISEX":
        preferidos = [
            item for item in filtrados
            if "HOMBRE" in _tokens_descripcion(item) or "UNISEX" in _tokens_descripcion(item)
        ]
        return preferidos or filtrados
    return filtrados or items


def _compatible_genero_ind(talle, genero_sel):
    genero = descripcion_catalogo(genero_sel)
    tokens = _tokens_descripcion(talle)
    tiene_hombre = "HOMBRE" in tokens
    tiene_mujer = "MUJER" in tokens
    tiene_unisex = "UNISEX" in tokens

    if genero == "HOMBRE":
        return not tiene_mujer and not tiene_unisex
    if genero == "MUJER":
        return not tiene_hombre and not tiene_unisex
    if genero == "UNISEX":
        return not tiene_mujer
    return True


def _filtrar_talles_indumentaria(candidatos, genero_sel, marca):
    genericos_ind = {"GENERAL", "CINTURA", "NUMERAL"}
    filtrados = []

    for talle in candidatos:
        if not _compatible_genero_ind(talle, genero_sel):
            continue
        descripcion = descripcion_catalogo(talle)
        tokens = _tokens_descripcion(talle)
        if marca and marca in descripcion:
            filtrados.append(talle)
        elif tokens.intersection(genericos_ind):
            filtrados.append(talle)

    return filtrados


def _talle_tiene_edad(talle):
    return bool(_tokens_descripcion(talle).intersection({"ADULTO", "BEBE", "NIÑO", "NINO"}))


def _filtrar_talles_medias(base, edad_sel):
    edad = _normalizar_edad_para_talle(edad_sel)
    if not edad:
        return base
    return [
        talle for talle in base
        if edad in descripcion_catalogo(talle) or not _talle_tiene_edad(talle)
    ]


def _filtrar_talles_accesorios(base, marca):
    if marca == "UNDER ARMOUR":
        return base
    return [
        talle for talle in base
        if "UNDER ARMOUR" not in descripcion_catalogo(talle)
    ]


def _filtrar_talles_generales_calzado(items, genero_sel):
    genero = descripcion_catalogo(genero_sel)
    if genero != "UNISEX":
        return _filtrar_talles_por_genero(items, genero_sel)
    return [
        item for item in items
        if "MUJER" not in _tokens_descripcion(item)
    ]


def filtrar_descripciones_talle(tipo_sel, edad_sel, genero_sel, marca_sel, talles):
    texto_tipo = tipo_texto_talle(tipo_sel)
    talle_unico = [
        t for t in talles
        if descripcion_catalogo(t) == "GENERAL TALLE UNICO"
    ]

    if not texto_tipo:
        return dedupe_descripciones(talle_unico)

    tipo_codigo = tipo_prefijo(tipo_sel)
    incluir_talle_unico = tipo_codigo not in {"CAL", "CLU", "IND", "BIC"}
    base = [t for t in talles if descripcion_catalogo(t).startswith(texto_tipo)]
    if tipo_codigo not in {"ACC", "BIC", "CAL", "CLU", "IND", "MED"}:
        return dedupe_descripciones(talle_unico)

    marca = descripcion_catalogo(marca_sel)
    inicial = list(talle_unico) if incluir_talle_unico else []

    if tipo_codigo == "ACC":
        return dedupe_descripciones(inicial + _filtrar_talles_accesorios(base, marca))

    if tipo_codigo == "MED":
        return dedupe_descripciones(inicial + _filtrar_talles_medias(base, edad_sel))

    if tipo_codigo not in {"CAL", "CLU", "IND", "MED"}:
        return dedupe_descripciones(inicial + base)

    edad = _normalizar_edad_para_talle(edad_sel)
    candidatos = [
        talle for talle in base
        if not edad or edad in descripcion_catalogo(talle)
    ]

    if tipo_codigo in {"CLU", "IND"}:
        filtrados_ind = _filtrar_talles_indumentaria(candidatos, genero_sel, marca)
        return dedupe_descripciones(inicial + (filtrados_ind or _filtrar_talles_por_genero(candidatos or base, genero_sel)))

    con_marca = [
        talle for talle in candidatos
        if marca and marca in descripcion_catalogo(talle)
    ]
    con_marca = _filtrar_talles_por_genero(con_marca, genero_sel)
    if con_marca:
        return dedupe_descripciones(inicial + con_marca)

    generales = [
        talle for talle in candidatos
        if "GENERAL" in _tokens_descripcion(talle)
    ]
    generales = _filtrar_talles_generales_calzado(generales, genero_sel)
    if generales:
        return dedupe_descripciones(inicial + generales)

    return dedupe_descripciones(inicial + _filtrar_talles_por_genero(candidatos or base, genero_sel))
