import os
import sys
from typing import Any, Dict

import pymysql


MYSQL_CREDENTIALS: Dict[str, Any] = {
    "host": os.getenv("LEGACY_MYSQL_HOST", ""),
    "port": int(os.getenv("LEGACY_MYSQL_PORT", "3306")),
    "user": os.getenv("LEGACY_MYSQL_USER", ""),
    "password": os.getenv("LEGACY_MYSQL_PASSWORD", ""),
    "database": os.getenv("LEGACY_MYSQL_DATABASE", ""),
    "charset": "utf8mb4",
    "connect_timeout": 15,
}


def probar_conexion_y_esquema() -> None:
    """
    Realiza un sanity check contra la base MySQL legacy.
    Las credenciales deben venir por variables de entorno LEGACY_MYSQL_*.
    """
    connection = None
    print(" [INFO] Intentando establecer conexion con el servidor MySQL...")

    try:
        connection = pymysql.connect(**MYSQL_CREDENTIALS)
        print(" [EXITO] Conexion establecida correctamente con el servidor.")

        with connection.cursor() as cursor:
            cursor.execute("SHOW TABLES;")
            tablas = cursor.fetchall()

            print(f"\n=== TABLAS DETECTADAS EN LA BASE DE DATOS LEGACY ({len(tablas)}) ===")
            for idx, tabla in enumerate(tablas, start=1):
                nombre_tabla = tabla[0]
                conteo_str = ""
                if nombre_tabla.lower() in ["talle", "talles", "articulo", "articulos"]:
                    try:
                        with connection.cursor() as count_cursor:
                            count_cursor.execute(f"SELECT COUNT(*) FROM `{nombre_tabla}`")
                            registros = count_cursor.fetchone()[0]
                            conteo_str = f" -> ({registros} registros detectados)"
                    except Exception:
                        conteo_str = " -> (Error al leer filas/sin permisos)"

                print(f" {idx}. {nombre_tabla}{conteo_str}")
            print("==================================================================\n")

    except pymysql.MySQLError as err:
        print(f"\n[ERROR DE BASE DE DATOS]: Codigo {err.args[0]} - {err.args[1]}", file=sys.stderr)
        print("Revisa host, puerto, usuario, password y nombre de base.", file=sys.stderr)

    except Exception as e:
        print(f"\n[ERROR DE RED O SISTEMA]: {e}", file=sys.stderr)

    finally:
        if connection and connection.open:
            connection.close()
            print(" [INFO] Conexion cerrada limpiamente. Recursos liberados.")


if __name__ == "__main__":
    probar_conexion_y_esquema()
