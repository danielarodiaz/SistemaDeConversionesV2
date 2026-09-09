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


def _tokens_catalogo(item):
    return _tokens_texto(descripcion_catalogo(item))


def _es_tipo(tipo_sel, *valores):
    texto = texto_catalogo(tipo_sel)
    return _contiene(texto, valores)


def _normalizar_edad_para_talle(edad_sel):
    descripcion = descripcion_catalogo(edad_sel)
    tokens = _tokens_catalogo(edad_sel)
    if "ADULTO" in descripcion:
        return "ADULTO"
    if tokens.intersection({"NIÑO", "NINO"}):
        return "NIÑO"
    if "BEBE" in tokens:
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


def filtrar_presentaciones(tipo_sel, presentaciones):
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
    filtradas = [p for p in presentaciones if codigo_catalogo(p).startswith(prefijos)]
    return filtradas or presentaciones


def filtrar_siluetas(tipo_sel, siluetas):
    return filtrar_presentaciones(tipo_sel, siluetas)


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


def _subtipo_na(subtipos):
    return next((item for item in subtipos if codigo_catalogo(item) == "N/A"), None)


def _subtipos_por_descripcion(subtipos, descripciones):
    descripciones_norm = {_limpiar_espacios(_normalizar(desc)) for desc in descripciones}
    return [
        item for item in subtipos
        if _limpiar_espacios(_normalizar(descripcion_catalogo(item))) in descripciones_norm
    ]


def filtrar_subtipos(presentacion_sel, uso_sel, subtipos):
    if not subtipos:
        return []

    na = _subtipo_na(subtipos)
    presentacion = _limpiar_espacios(_normalizar(descripcion_catalogo(presentacion_sel)))
    uso = _limpiar_espacios(_normalizar(descripcion_catalogo(uso_sel)))

    reglas_por_presentacion = {
        "CALZA": {"CORTA", "BIKER", "7/8", "LARGA"},
        "CROPTOP": {"CROP", "CON TAZA", "SIN TAZA"},
        "TOP": {"CON TAZA", "SIN TAZA", "REGULAR"},
        "REMERA": {"CROP", "REGULAR", "OVERSIZE"},
    }
    descripciones = reglas_por_presentacion.get(presentacion)

    if presentacion == "SHORT":
        if uso in {"RUNNING", "TRAIL"} or uso.startswith("RUN") or uso.startswith("TRAI"):
            descripciones = {"3 IN", "5 IN"}
        elif uso == "LIFESTYLE":
            descripciones = {"REGULAR"}
        else:
            descripciones = set()

    filtrados = _subtipos_por_descripcion(subtipos, descripciones or set())
    resultado = []
    if na:
        resultado.append(na)
    resultado.extend(item for item in filtrados if item is not na)
    return resultado or ([na] if na else [])


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


def _terminos_presentacion_acc(presentacion_sel):
    presentacion = descripcion_catalogo(presentacion_sel)
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
    terminos = set(alias.get(presentacion, set()))
    terminos.update(_variantes_basicas(presentacion))
    return {_limpiar_espacios(_normalizar(t)) for t in terminos if t}


def _objetivo_contiene_termino(objetivo, termino):
    descripcion = _normalizar(descripcion_catalogo(objetivo))
    termino_norm = _limpiar_espacios(_normalizar(termino))
    if not termino_norm:
        return False
    if " " in termino_norm:
        return termino_norm in descripcion
    return termino_norm in _tokens_texto(descripcion)


def _filtrar_objetivos_por_presentacion_acc(objetivos, presentacion_sel):
    terminos = _terminos_presentacion_acc(presentacion_sel)
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


def _edad_objetivo_cal(edad_sel):
    edad = descripcion_catalogo(edad_sel)
    tokens = _tokens_catalogo(edad_sel)
    if tokens.intersection({"NIÑO", "NINO", "BEBE"}):
        return "NIÑO"
    if "ADULTO" in edad:
        return "ADULTO"
    return ""


def _filtrar_objetivos_por_edad_cal(objetivos, edad_sel):
    edad = _edad_objetivo_cal(edad_sel)
    if not edad:
        return objetivos
    filtrados = [
        objetivo for objetivo in objetivos
        if _objetivo_contiene_termino(objetivo, edad)
    ]
    return filtrados or objetivos


def _terminos_uso_cal(uso_sel):
    uso = _limpiar_espacios(_normalizar(descripcion_catalogo(uso_sel)))
    return {
        "BASQUET": {"BASQUET"},
        "CICLISMO": {"CICLISMO"},
        "FUTBOL 11": {"FUTB CAMPO", "FUTB SALON", "FUTB TURF"},
        "FUTBOL GENERAL": {"FUTB CAMPO", "FUTB SALON", "FUTB TURF"},
        "FUTBOL 5": {"FUTB CAMPO", "FUTB SALON", "FUTB TURF"},
        "FUTSAL": {"FUTB SALON"},
        "GOLF": {"GOLF"},
        "HOCKEY": {"HOCKEY"},
        "LIFESTYLE": {"MODA"},
        "MODA": {"MODA"},
        "RUGBY": {"RUGBY"},
        "RUNNING": {"RUNN"},
        "TRAIL": {"TRAIL"},
        "TRAINING": {"TRAIN"},
        "TENIS": {"TENIS"},
        "PADEL": {"TENIS"},
        "OUTDOOR": {"TRAIL"},
    }.get(uso, set())


def _es_tipo_verano(tipo_sel):
    return _es_tipo(tipo_sel, "VER", "VERANO")


def _presentacion_prioriza_verano(presentacion_sel):
    presentacion = descripcion_catalogo(presentacion_sel)
    return presentacion in {"OJOTAS", "SANDALIA"}


def _filtrar_objetivos_por_terminos(objetivos, terminos):
    if not terminos:
        return objetivos
    filtrados = _objetivos_con_terminos(objetivos, terminos)
    return filtrados or objetivos


def _objetivos_con_terminos(objetivos, terminos):
    return [
        objetivo for objetivo in objetivos
        if any(_objetivo_contiene_termino(objetivo, termino) for termino in terminos)
    ]


def _filtrar_objetivos_cal(tipo_sel, presentacion_sel, uso_sel, edad_sel, objetivos):
    por_edad = _filtrar_objetivos_por_edad_cal(objetivos, edad_sel)
    if _es_tipo_verano(tipo_sel) or _presentacion_prioriza_verano(presentacion_sel):
        verano = _objetivos_con_terminos(por_edad, {"VERA"})
        return verano or por_edad

    por_uso = _objetivos_con_terminos(por_edad, _terminos_uso_cal(uso_sel))
    return por_uso or por_edad


def _terminos_genero_ind(genero_sel, edad_sel):
    edad = descripcion_catalogo(edad_sel)
    genero = descripcion_catalogo(genero_sel)
    edad_tokens = _tokens_catalogo(edad_sel)
    if edad_tokens.intersection({"NIÑO", "NINO", "BEBE"}):
        return {"NIÑ", "NIÑO", "NINO"}
    if "MUJER" in genero or "FEMENINO" in edad:
        return {"MUJ"}
    if "HOMBRE" in genero or "MASCULINO" in edad or "UNISEX" in genero:
        return {"HOMB", "HOM"}
    return set()


def _filtrar_objetivos_por_genero_ind(objetivos, genero_sel, edad_sel):
    terminos = _terminos_genero_ind(genero_sel, edad_sel)
    if not terminos:
        return objetivos
    filtrados = _objetivos_con_terminos(objetivos, terminos)
    return filtrados or objetivos


def _terminos_presentacion_ind(presentacion_sel):
    presentacion = descripcion_catalogo(presentacion_sel)
    alias = {
        "BERMUDA": {"BERMU", "BERMUDA"},
        "BOXER": {"BOXER"},
        "BUZO": {"BUZO"},
        "CALZA": {"CALZA"},
        "CAMISA": {"CAMISA"},
        "CAMISETA": {"REME"},
        "CAMPERA": {"CAMPE", "CAMPERA"},
        "CHALECO": {"OTROS"},
        "CHOMBA": {"CHOMBA"},
        "CONJUNTO": {"CONJUNTO"},
        "HOODIE": {"HOODIE"},
        "JEANS": {"JEANS"},
        "JERSEY": {"JERSEY"},
        "MALLA": {"MALLA"},
        "MUSCULOSA": {"MUSC", "MUSCULOSA"},
        "PANTALON": {"PANT", "PANTALON"},
        "PECHERA": {"OTROS"},
        "POLLERA": {"POLLERA"},
        "REMERA": {"REME"},
        "REMERA TERMICA": {"REME TERMICA"},
        "SHORT": {"SHORT"},
        "TOP": {"TOP"},
        "VARIOS": {"OTROS"},
    }
    terminos = set(alias.get(presentacion, set()))
    terminos.update(_variantes_basicas(presentacion))
    return {_limpiar_espacios(_normalizar(t)) for t in terminos if t}


def _terminos_uso_ind(uso_sel):
    uso = _limpiar_espacios(_normalizar(descripcion_catalogo(uso_sel)))
    return {
        "CICLISMO": {"CICL"},
        "FUTBOL 11": {"FUTB"},
        "FUTBOL GENERAL": {"FUTB"},
        "FUTBOL 5": {"FUTB"},
        "FUTSAL": {"FUTB"},
        "LIFESTYLE": {"MOD"},
        "MODA": {"MOD"},
        "RUNNING": {"TRAI"},
        "TRAINING": {"TRAI"},
        "TRAIL": {"TRAI"},
        "VOLEY": {"TRAI"},
        "BASQUET": {"TRAI"},
        "TENIS": {"TRAI"},
        "PADEL": {"TRAI"},
        "NATACION": {"TRAI"},
    }.get(uso, set())


def _objetivos_otros_ind(objetivos, genero_sel, edad_sel):
    terminos_genero = _terminos_genero_ind(genero_sel, edad_sel)
    otros = [
        objetivo for objetivo in objetivos
        if _objetivo_contiene_termino(objetivo, "OTROS")
        and (not terminos_genero or any(_objetivo_contiene_termino(objetivo, termino) for termino in terminos_genero))
    ]
    return otros


def _filtrar_objetivos_ind(presentacion_sel, uso_sel, genero_sel, edad_sel, objetivos):
    por_genero = _filtrar_objetivos_por_genero_ind(objetivos, genero_sel, edad_sel)
    terminos_presentacion = _terminos_presentacion_ind(presentacion_sel)
    por_presentacion = _objetivos_con_terminos(por_genero, terminos_presentacion)
    por_uso_y_presentacion = _objetivos_con_terminos(por_presentacion, _terminos_uso_ind(uso_sel))
    if por_uso_y_presentacion:
        return por_uso_y_presentacion
    if por_presentacion:
        return por_presentacion
    if terminos_presentacion:
        otros = _objetivos_otros_ind(por_genero, genero_sel, edad_sel)
        if otros:
            return otros

    por_uso = _objetivos_con_terminos(por_genero, _terminos_uso_ind(uso_sel))
    if por_uso:
        return por_uso

    otros = _objetivos_otros_ind(por_genero, genero_sel, edad_sel)
    return otros or por_genero


def filtrar_objetivos(tipo_sel, presentacion_sel, uso_sel, objetivos, edad_sel=None, genero_sel=None):
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

    if prefijo == "CAL":
        return _filtrar_objetivos_cal(tipo_sel, presentacion_sel, uso_sel, edad_sel, por_tipo)

    if prefijo == "IND":
        return _filtrar_objetivos_ind(presentacion_sel, uso_sel, genero_sel, edad_sel, por_tipo)

    if prefijo != "ACC":
        return por_tipo

    por_presentacion = _filtrar_objetivos_por_presentacion_acc(por_tipo, presentacion_sel)
    if descripcion_catalogo(presentacion_sel) == "PELOTA":
        return _filtrar_objetivos_pelota_acc(por_presentacion, uso_sel)
    por_uso = _filtrar_objetivos_por_uso_acc(por_presentacion, uso_sel)
    return por_uso or por_presentacion or por_tipo


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
