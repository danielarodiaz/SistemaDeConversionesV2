import pyodbc
import os
from dotenv import load_dotenv

# Cargamos las variables del archivo .env
load_dotenv()

def conectar_cegid():
    """
    Establece la conexión con la base de datos SQL Server de CEGID.
    Usa variables de entorno para seguridad.
    """
    try:
        # Los datos vienen del .env que crearemos abajo
        server = os.getenv("CEGID_SERVER")
        database = os.getenv("CEGID_DATABASE")
        username = os.getenv("CEGID_USERNAME")
        password = os.getenv("CEGID_PASSWORD")
        driver = '{ODBC Driver 17 for SQL Server}' # Asegúrate de tenerlo instalado

        conn_str = f'DRIVER={driver};SERVER={server};DATABASE={database};UID={username};PWD={password}'
        
        conexion = pyodbc.connect(conn_str, timeout=5)
        return conexion
    except Exception as e:
        print(f"❌ Error crítico de conexión a CEGID: {e}")
        return None