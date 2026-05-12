import os
import sys

# Fuerza UTF-8 en la consola de Windows para evitar UnicodeEncodeError con emojis
if sys.stdout and hasattr(sys.stdout, 'reconfigure'):
    try: sys.stdout.reconfigure(encoding='utf-8')
    except Exception: pass
if sys.stderr and hasattr(sys.stderr, 'reconfigure'):
    try: sys.stderr.reconfigure(encoding='utf-8')
    except Exception: pass
import pyodbc
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
try:
    from models import Base
except ModuleNotFoundError:
    from backend.models import Base
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))

# Variables de entorno
USER    = os.getenv("DB_USER", "sa")
PASS    = os.getenv("DB_PASSWORD", "")
HOST    = os.getenv("DB_HOST", "localhost")
PORT    = os.getenv("DB_PORT", "1433")
DB_NAME = os.getenv("DB_NAME", "Conversor_DB")
# Nueva variable para detectar si es Windows Auth (Servidor) o SQL Auth (Docker)
DB_AUTH_TYPE = os.getenv("DB_AUTH_TYPE", "SQL") # 'SQL' o 'WINDOWS'

def get_connection_string(for_pyodbc=False, target_db="master"):
    """
    Construye la cadena de conexión según el tipo de autenticación.
    """
    driver = "{ODBC Driver 17 for SQL Server}"
    
    if DB_AUTH_TYPE == "WINDOWS":
        # Nota: En Windows Auth (SQLEXPRESS), a veces el PORT no es necesario o es dinámico
        # Usamos el HOST directamente (ej. DB2\SQLEXPRESS)
        if for_pyodbc:
            return f"DRIVER={driver};SERVER={HOST};DATABASE={target_db};Trusted_Connection=yes;TrustServerCertificate=yes"
        else:
            # Para SQLAlchemy
            return f"mssql+pyodbc://{HOST}/{target_db}?driver=ODBC+Driver+17+for+SQL+Server&trusted_connection=yes&TrustServerCertificate=yes"
    else:
        # SQL Authentication (Docker / Local)
        if for_pyodbc:
            return f"DRIVER={driver};SERVER={HOST},{PORT};UID={USER};PWD={PASS};DATABASE={target_db};TrustServerCertificate=yes"
        else:
            return f"mssql+pyodbc://{USER}:{PASS}@{HOST}:{PORT}/{target_db}?driver=ODBC+Driver+17+for+SQL+Server&TrustServerCertificate=yes"

def ensure_database_exists():
    conn_str = get_connection_string(for_pyodbc=True, target_db="master")
    try:
        conn = pyodbc.connect(conn_str, autocommit=True)
        cursor = conn.cursor()
        exists = cursor.execute(f"SELECT name FROM sys.databases WHERE name = '{DB_NAME}'").fetchone()
        if not exists:
            print(f"🛠 Creando base de datos '{DB_NAME}'...")
            cursor.execute(f"CREATE DATABASE [{DB_NAME}]") # Corchetes por seguridad
            print(f"✅ Base de datos '{DB_NAME}' creada.")
        cursor.close()
        conn.close()
    except Exception as e:
        print(f"❌ Error al asegurar existencia de DB: {e}")
        raise

# Configuración de SQLAlchemy usando la nueva lógica
DATABASE_URL = get_connection_string(for_pyodbc=False, target_db=DB_NAME)

engine = create_engine(DATABASE_URL, echo=False) 
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def init_db():
    try:
        # Primero aseguramos que la DB lógica existe
        ensure_database_exists()
        # Luego creamos las tablas según los modelos
        Base.metadata.create_all(bind=engine)
        print("✅ Tablas creadas con éxito.")
    except Exception as e:
        print(f"❌ Error al inicializar la base de datos: {e}")

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()