import os
import sys
import socket

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

# ── Auto-detección de entorno ─────────────────────────────────────────────────
# Si el hostname es "DB2" estamos en el servidor físico → Windows Auth / SQLEXPRESS
# En cualquier otro entorno (dev, Docker) → SQL Auth con usuario/contraseña
_HOSTNAME = socket.gethostname().upper()
_IS_SERVER = _HOSTNAME == "DB2"

# DB_AUTH_TYPE: permite sobreescribir via .env si alguna vez cambia el hostname
# Default inteligente: WINDOWS en el servidor, SQL en cualquier otro lado.
DB_AUTH_TYPE = os.getenv("DB_AUTH_TYPE", "WINDOWS" if _IS_SERVER else "SQL")

# Parámetros de conexión (solo usados en modo SQL Auth)
DB_USER = os.getenv("DB_USER", "sa")
DB_PASS = os.getenv("DB_PASSWORD", "")
DB_HOST = os.getenv("DB_HOST", "DB2\\SQLEXPRESS" if _IS_SERVER else "127.0.0.1")
DB_PORT = os.getenv("DB_PORT", "1433")
DB_NAME = os.getenv("DB_NAME", "Conversor_DB")
DB_ENCRYPT = os.getenv("DB_ENCRYPT", "no")

print(f"[DB] Hostname: {_HOSTNAME} | Auth: {DB_AUTH_TYPE} | Host: {DB_HOST} | DB: {DB_NAME}")

# ─────────────────────────────────────────────────────────────────────────────

def get_connection_string(for_pyodbc=False, target_db="master"):
    """
    Construye la cadena de conexión según el tipo de autenticación.
      - WINDOWS: Windows Auth (servidor DB2\\SQLEXPRESS, sin usuario/contraseña)
      - SQL:     SQL Auth     (Docker local, usuario 'sa' + contraseña)
    """
    driver = "{ODBC Driver 17 for SQL Server}"

    if DB_AUTH_TYPE == "WINDOWS":
        if for_pyodbc:
            return (
                f"DRIVER={driver};SERVER={DB_HOST};DATABASE={target_db};"
                f"Trusted_Connection=yes;Encrypt={DB_ENCRYPT};TrustServerCertificate=yes"
            )
        else:
            return (
                f"mssql+pyodbc://{DB_HOST}/{target_db}"
                "?driver=ODBC+Driver+17+for+SQL+Server"
                "&trusted_connection=yes"
                f"&Encrypt={DB_ENCRYPT}"
                "&TrustServerCertificate=yes"
            )
    else:
        # SQL Authentication (Docker / Local)
        if for_pyodbc:
            return (
                f"DRIVER={driver};SERVER={DB_HOST},{DB_PORT};"
                f"UID={DB_USER};PWD={DB_PASS};DATABASE={target_db};"
                f"Encrypt={DB_ENCRYPT};TrustServerCertificate=yes"
            )
        else:
            return (
                f"mssql+pyodbc://{DB_USER}:{DB_PASS}@{DB_HOST}:{DB_PORT}/{target_db}"
                "?driver=ODBC+Driver+17+for+SQL+Server"
                f"&Encrypt={DB_ENCRYPT}"
                "&TrustServerCertificate=yes"
            )


def ensure_database_exists():
    conn_str = get_connection_string(for_pyodbc=True, target_db="master")
    try:
        conn = pyodbc.connect(conn_str, autocommit=True)
        cursor = conn.cursor()
        exists = cursor.execute(
            f"SELECT name FROM sys.databases WHERE name = '{DB_NAME}'"
        ).fetchone()
        if not exists:
            print(f"🛠 Creando base de datos '{DB_NAME}'...")
            cursor.execute(f"CREATE DATABASE [{DB_NAME}]")
            print(f"✅ Base de datos '{DB_NAME}' creada.")
        cursor.close()
        conn.close()
    except Exception as e:
        print(f"❌ Error al asegurar existencia de DB: {e}")
        raise


# Configuración de SQLAlchemy
DATABASE_URL = get_connection_string(for_pyodbc=False, target_db=DB_NAME)
engine = create_engine(DATABASE_URL, echo=False)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def init_db():
    try:
        ensure_database_exists()
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
