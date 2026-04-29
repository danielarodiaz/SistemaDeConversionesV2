import pandas as pd
from backend.utils.cegid_utils import obtener_costos_por_codigos_barras, obtener_costo_por_modelo

class CegidValidator:
    @staticmethod
    def auditar_items(lista_articulos):
        resultados = {
            "existentes": [],      
            "faltantes": [],       
            "actualizar_ean": [],  
            "cambios_precio": [],  
            "total_items": len(lista_articulos)
        }
        
        # 1. Consulta masiva por EANs
        codigos_barras = [str(a['barras']).strip() for a in lista_articulos if a.get('barras') and not str(a.get('barras')).startswith('FALTA')]
        maestro_cegid = obtener_costos_por_codigos_barras(codigos_barras)
        
        # Diccionarios para evitar duplicados en el reporte visual
        faltantes_unicos = {}     # Llave: "{articulo}_{talle}"
        actualizar_ean_unicos = {} # Llave: "{articulo}_{barras}" → evita EANs repetidos
        cambios_unicos = {}        # Llave: articulo
        # Artículos confirmados como existentes en CEGID (por EAN o por modelo).
        # Si un artículo ya está aquí NO debe aparecer en faltantes.
        articulos_existentes = set()

        for art in lista_articulos:
            cb = str(art.get('barras', '')).strip()
            cod_art = str(art.get('articulo', '')).strip()
            precio_prov = round(float(art.get('precio_prov', 0)), 2)
            
            # --- PUNTO 3: Limpieza de talle para ordenamiento ---
            talle_raw = str(art.get('detalles', {}).get('Size', '')).strip()
            talle_clean = talle_raw.replace('-', '.5') if talle_raw.endswith('-') else talle_raw
            
            info_cegid = maestro_cegid.get(cb)
            
            if info_cegid:
                articulos_existentes.add(cod_art)  # EAN confirmado → artículo existe
                _, precio_cegid, desc_cegid = info_cegid
                # --- PUNTO 5: Agrupar cambios de precio por Artículo ---
                if round(float(precio_cegid), 2) != precio_prov:
                    if cod_art not in cambios_unicos:
                        variacion = ((precio_prov - precio_cegid) / precio_cegid * 100) if precio_cegid > 0 else 100
                        cambios_unicos[cod_art] = {
                            "articulo_cegid": cod_art,
                            "descripcion": desc_cegid,
                            "precio_cegid": round(float(precio_cegid), 2),
                            "precio_prov": precio_prov,
                            "variacion_porcentaje": round(variacion, 2)
                        }
            else:
                costo_modelo = obtener_costo_por_modelo(cod_art)
                if costo_modelo is not None:
                    articulos_existentes.add(cod_art)  # Modelo confirmado → artículo existe
                    # --- PUNTO 4: Mensaje dinámico con talle (sin duplicados) ---
                    clave_ean = f"{cod_art}_{cb}"
                    if clave_ean not in actualizar_ean_unicos:
                        actualizar_ean_unicos[clave_ean] = {
                            "articulo": cod_art,
                            "barras": cb,
                            "mensaje": f"Falta EAN: talle {talle_clean}"
                        }
                    # También verificar precio aunque falte EAN
                    if round(float(costo_modelo), 2) != precio_prov:
                        if cod_art not in cambios_unicos:
                            cambios_unicos[cod_art] = {
                                "articulo_cegid": cod_art,
                                "descripcion": "Modelo detectado",
                                "precio_cegid": round(float(costo_modelo), 2),
                                "precio_prov": precio_prov,
                                "variacion_porcentaje": 0
                            }
                else:
                    # Solo agregar a faltantes si NO fue confirmado como existente
                    # en ninguna otra fila (evita que un artículo aparezca en ambas listas)
                    if cod_art not in articulos_existentes:
                        clave_faltante = f"{cod_art}_{talle_clean}"
                        if clave_faltante not in faltantes_unicos:
                            detalles = art.get("detalles", {}).copy()
                            detalles["Size"] = talle_clean
                            faltantes_unicos[clave_faltante] = detalles

        # Convertimos diccionarios a listas
        resultados["faltantes"] = list(faltantes_unicos.values())
        resultados["actualizar_ean"] = list(actualizar_ean_unicos.values())
        resultados["cambios_precio"] = list(cambios_unicos.values())

        return resultados