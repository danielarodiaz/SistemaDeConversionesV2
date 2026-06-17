import pymysql
import sys
from typing import Dict, Any

# =========================================================================
# PARAMETRIZACIÓN SEGURA
# Modifica estos valores con las credenciales reales de tu phpMyAdmin viejo.
# =========================================================================
MYSQL_CREDENTIALS: Dict[str, Any] = {
    "host": "srv501.hstgr.io",                 # El nombre de host oficial de Hostinger
    "port": 3306,                              # Puerto estándar de MySQL
    "user": "root",              # Tu usuario (con la 'ó' si así figura en el panel)
    "password": "marathon123A",            # La contraseña de esa base de datos en Hostinger
    "database": "u188743961_marathon" ,     # El nombre de la base de datos
    "charset": "utf8mb4",
    "connect_timeout": 15                      # Le damos 15 segundos por la latencia de internet
}

def probar_conexion_y_esquema() -> None:
    """
    Realiza un Sanity Check contra la base de datos de origen (MySQL).
    Verifica la conexión, lista las tablas disponibles y hace un conteo inicial.
    """
    connection = None
    print(" [INFO] Intentando establecer conexión con el servidor MySQL...")
    
    try:
        # Intentamos abrir el socket de conexión
        connection = pymysql.connect(**MYSQL_CREDENTIALS)
        
        print(" [ÉXITO] ¡Conexión establecida correctamente con el servidor!")
        
        with connection.cursor() as cursor:
            # Consulta estándar ANSI SQL para listar las tablas de la base de datos actual
            cursor.execute("SHOW TABLES;")
            tablas = cursor.fetchall()
            
            print(f"\n=== TABLAS DETECTADAS EN LA BASE DE DATOS VIEJA ({len(tablas)}) ===")
            for idx, tabla in enumerate(tablas, start=1):
                # El resultado viene como una tupla, tomamos el primer elemento
                nombre_tabla = tabla[0]
                
                # Para hacer la prueba más interesante, si encuentra la tabla de talles o artículos,
                # hace un conteo rápido de registros para verificar permisos de lectura (SELECT).
                conteo_str = ""
                if nombre_tabla.lower() in ["talle", "talles", "articulo", "articulos"]:
                    try:
                        # Creamos un cursor secundario rápido para no interferir con el bucle principal
                        with connection.cursor() as count_cursor:
                            count_cursor.execute(f"SELECT COUNT(*) FROM `{nombre_tabla}`")
                            registros = count_cursor.fetchone()[0]
                            conteo_str = f" -> ({registros} registros detectados)"
                    except Exception:
                        conteo_str = " -> (Error al leer filas/sin permisos)"
                
                print(f" {idx}. {nombre_tabla}{conteo_str}")
            print("==================================================================\n")
            
    except pymysql.MySQLError as err:
        # Capturamos errores específicos del motor de MySQL (Permisos, Base no existe, etc.)
        print(f"\n❌ [ERROR DE BASE DE DATOS]: Código {err.args[0]} - {err.args[1]}", file=sys.stderr)
        print("Revisa que el Host, Puerto, Usuario, Contraseña y el Nombre de la Base sean correctos.", file=sys.stderr)
        
    except Exception as e:
        # Capturamos cualquier otro error de red o de sistema operativo (Network Unreachable, etc.)
        print(f"\n❌ [ERROR DE RED O SISTEMA]: {e}", file=sys.stderr)
        
    finally:
        # Bloque crítico: Pase lo que pase, el socket de red debe cerrarse
        if connection and connection.open:
            connection.close()
            print(" [INFO] Conexión cerrada limpiamente. Recursos liberados.")

if __name__ == "__main__":
    probar_conexion_y_esquema()