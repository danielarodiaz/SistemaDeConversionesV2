from config import esta_en_render
from backend.services.cegid_connector import conectar_cegid
import pandas as pd
from typing import Dict, List, Tuple

# 🧠 Función que decide qué implementación usar (mock o real)
def obtener_codigo_barra(modelo, talle, color=None):
    """
    Lógica de ruteo que elige entre la implementación mock o real según el entorno.
    """
    if esta_en_render():
        return obtener_codigo_barra_por_talle_mock(modelo, color or "", talle)
    else:
        return obtener_codigo_barra_flexible(modelo, talle, incluir_color=bool(color), color=color)

# 🧪 Mock para Render
def obtener_codigo_barra_por_talle_mock(modelo, color, talle):
    return f"MOCK-{modelo}-{color}-{talle}"

def obtener_codigo_barra_flexible(codigo_articulo, talle, incluir_color=False, color=None):
    """
    Dado un código de artículo y un talle, devuelve el código de barras correspondiente.
    Si `incluir_color` es True, intenta construir el código como modelo-color.
    Si es False, usa el código directamente como GA_CODEARTICLE.
    """
    try:
        conexion = conectar_cegid()
        if not conexion:
            return None

        cursor = conexion.cursor()

        if incluir_color and color:
            codigo_compuesto = f"{codigo_articulo}-{color}"
        else:
            codigo_compuesto = codigo_articulo

        query = """
            SELECT GA_CODEBARRE
            FROM ARTICLE
            INNER JOIN DIMENSION ON GA_CODEDIM1=GDI_CODEDIM AND GA_GRILLEDIM1=GDI_GRILLEDIM
            WHERE GA_CODEARTICLE = ?
            AND GDI_DIMORLI = ?
        """

        cursor.execute(query, (codigo_compuesto, str(talle)))
        result = cursor.fetchone()

        return result[0] if result else None

    except Exception as e:
        print(f"❌ Error obteniendo código de barra en CEGID: {e}")
        return None
    finally:
        if 'conexion' in locals() and conexion:
            conexion.close()


def obtener_precios_cegid_por_cod_prov(cod_prov):
    if esta_en_render():
        return pd.DataFrame(columns=[
            'IDArticulo', 'CodigoArticulo', 'NombreArticulo', 'PrecioCompra', 'PrecioVenta'
        ])
    try:
        conexion = conectar_cegid()
        if not conexion:
            return pd.DataFrame()

        cursor = conexion.cursor()

        # Consulta para obtener todos los artículos y precios del proveedor
        query = '''
            SELECT 
                a.GA_ARTICLE as IDArticulo,
                a.GA_CODEARTICLE as CodigoArticulo,
                a.GA_LIBELLE as NombreArticulo,
                t_costo.GF_PRIXUNITAIRE as PrecioCompra,
                t_venta.GF_PRIXUNITAIRE as PrecioVenta
            FROM ARTICLE a
            INNER JOIN TARIF t_costo ON a.GA_ARTICLE = t_costo.GF_ARTICLE 
                AND t_costo.GF_LIBELLE LIKE '%PRECIOS COSTO MARATHON-PERIODO BASE%'
            INNER JOIN TARIF t_venta ON a.GA_ARTICLE = t_venta.GF_ARTICLE 
                AND t_venta.GF_LIBELLE LIKE '%Precios Marathon-PERIODO BASE%'
            WHERE a.GA_FOURNPRINC = ?
                AND t_costo.GF_PRIXUNITAIRE IS NOT NULL
                AND t_venta.GF_PRIXUNITAIRE IS NOT NULL
        '''
        cursor.execute(query, (cod_prov,))
        resultados = cursor.fetchall()

        if resultados:
            try:
                df = pd.DataFrame({
                    'IDArticulo': [r[0] for r in resultados], 
                    'CodigoArticulo': [r[1] for r in resultados],  
                    'NombreArticulo': [r[2] for r in resultados],
                    'PrecioCompra': [float(r[3]) for r in resultados],
                    'PrecioVenta': [float(r[4]) for r in resultados]
                })
                return df
            except Exception as e:
                raise
        else:
            return pd.DataFrame(columns=['IDArticulo', 'CodigoArticulo', 'NombreArticulo', 'PrecioCompra', 'PrecioVenta'])

    except Exception as e:
        return pd.DataFrame()

    finally:
        if 'conexion' in locals() and conexion:
            conexion.close()


def obtener_precio_venta_y_promo_por_codigo(codigo_articulo):
    """
    Obtiene el precio de venta, el campo PROMO (GA_LIBREART6) y el campo MARCA (GA_LIBREART2) para un código de artículo específico.
    Esta función es específica para el procesador de mayoristas.
    """
    if esta_en_render():
        return {
            'precio_venta': 0.0,
            'promo': ''
        }
    
    try:
        conexion = conectar_cegid()
        if not conexion:
            return {'precio_venta': 0.0, 'promo': ''}

        cursor = conexion.cursor()

        # Consulta para obtener precio de venta y campo PROMO por código de artículo
        query = '''
            SELECT 
                t_venta.GF_PRIXUNITAIRE as PrecioVenta,
                a.GA_LIBREART6 as Promo,
                a.GA_LIBREART2 as Marca
            FROM ARTICLE a
            INNER JOIN TARIF t_venta ON a.GA_ARTICLE = t_venta.GF_ARTICLE 
                AND t_venta.GF_LIBELLE LIKE '%Precios Marathon-PERIODO BASE%'
            WHERE a.GA_CODEARTICLE = ?
                AND t_venta.GF_PRIXUNITAIRE IS NOT NULL
        '''
        
        cursor.execute(query, (codigo_articulo,))
        resultado = cursor.fetchone()
        
        if resultado:
            precio_venta = float(resultado[0]) if resultado[0] else 0.0
            promo = str(resultado[1]) if resultado[1] else ''
            marca = str(resultado[2]) if resultado[2] else ''
            return {
                'precio_venta': precio_venta,
                'promo': promo,
                'marca': marca
            }
        else:
            return {'precio_venta': 0.0, 'promo': '', 'marca': ''}

    except Exception as e:
        return {'precio_venta': 0.0, 'promo': '', 'marca': ''}

    finally:
        if 'conexion' in locals() and conexion:
            conexion.close()


def obtener_costos_por_codigos_barras(codigos_barras: List[str]) -> Dict[str, Tuple[str, float, str]]:
    """
    Dado un listado de códigos de barras, devuelve un diccionario:
      { codigo_barra: (CodigoArticulo, PrecioCompra, Descripcion) }

    - Si está en Render, retorna dict vacío.
    - Omite códigos de barra vacíos o nulos.
    """
    if not codigos_barras:
        return {}

    valores = [str(cb).strip() for cb in codigos_barras if cb is not None and str(cb).strip() != ""]
    valores = list(dict.fromkeys(valores))

    if not valores:
        return {}

    if esta_en_render():
        return {}

    try:
        conexion = conectar_cegid()
        if not conexion:
            return {}

        cursor = conexion.cursor()

        resultados: Dict[str, Tuple[str, float, str]] = {}
        chunk_size = 900
        for i in range(0, len(valores), chunk_size):
            chunk = valores[i:i+chunk_size]
            placeholders = ",".join(["?"] * len(chunk))
            query = f'''
                SELECT 
                    a.GA_CODEBARRE as CodigoBarra,
                    a.GA_CODEARTICLE as CodigoArticulo,
                    t_costo.GF_PRIXUNITAIRE as PrecioCompra,
                    a.GA_LIBELLE as Descripcion
                FROM ARTICLE a
                INNER JOIN ARTICLE a_padre ON a.GA_CODEARTICLE = a_padre.GA_CODEARTICLE 
                    AND LTRIM(SUBSTRING(a_padre.GA_ARTICLE, LEN(a.GA_CODEARTICLE) + 1, LEN(a_padre.GA_ARTICLE))) LIKE 'X%'
                INNER JOIN TARIF t_costo ON a_padre.GA_ARTICLE = t_costo.GF_ARTICLE 
                    AND t_costo.GF_LIBELLE LIKE '%PRECIOS COSTO MARATHON-PERIODO BASE%'
                WHERE a.GA_CODEBARRE IN ({placeholders})
            '''
            cursor.execute(query, chunk)
            rows = cursor.fetchall()

            for r in rows:
                try:
                    codigo_barra = str(r[0]).strip()
                    codigo_articulo = str(r[1]).strip()
                    precio_compra = float(r[2]) if r[2] is not None else None
                    descripcion = str(r[3]).strip() if r[3] is not None else ""
                    if codigo_barra and codigo_articulo and precio_compra is not None:
                        resultados[codigo_barra] = (codigo_articulo, precio_compra, descripcion)
                except Exception:
                    continue

        return resultados

    except Exception:
        return {}
    finally:
        if 'conexion' in locals() and conexion:
            conexion.close()
def obtener_costo_por_modelo(codigo_articulo):
    """Busca el costo base del modelo (sin depender del EAN)"""
    try:
        conexion = conectar_cegid()
        if not conexion: return None
        cursor = conexion.cursor()
        query = '''
            SELECT t_costo.GF_PRIXUNITAIRE
            FROM ARTICLE a
            INNER JOIN TARIF t_costo ON a.GA_ARTICLE = t_costo.GF_ARTICLE 
                AND t_costo.GF_LIBELLE LIKE '%PRECIOS COSTO MARATHON-PERIODO BASE%'
            WHERE a.GA_CODEARTICLE = ?
        '''
        cursor.execute(query, (codigo_articulo,))
        res = cursor.fetchone()
        return float(res[0]) if res else None
    except Exception: return None
    finally:
        if 'conexion' in locals() and conexion: conexion.close()
