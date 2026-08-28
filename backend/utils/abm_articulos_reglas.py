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
    generales = _filtrar_talles_por_genero(generales, genero_sel)
    if generales:
        return dedupe_descripciones(inicial + generales)

    return dedupe_descripciones(inicial + _filtrar_talles_por_genero(candidatos or base, genero_sel))
