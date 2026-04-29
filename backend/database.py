import os
import pyodbc
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from models import Base
from dotenv import load_dotenv

# Carga el archivo .env ubicado en el mismo directorio
load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))

USER    = os.getenv("DB_USER", "sa")
PASS    = os.getenv("DB_PASSWORD", "")
HOST    = os.getenv("DB_HOST", "localhost")
PORT    = os.getenv("DB_PORT", "1433")
DB_NAME = os.getenv("DB_NAME", "Conversor_DB")

# 1. Función para asegurar que la DB existe en SQL Server
def ensure_database_exists():
    # Conexión inicial a 'master' (siempre existe en SQL Server)
    conn_str = f'DRIVER={{ODBC Driver 17 for SQL Server}};SERVER={HOST},{PORT};UID={USER};PWD={PASS};DATABASE=master'
    try:
        # Usamos autocommit=True porque CREATE DATABASE no puede ejecutarse en una transacción
        conn = pyodbc.connect(conn_str, autocommit=True)
        cursor = conn.cursor()
        
        # Verificamos si existe la DB
        exists = cursor.execute(f"SELECT name FROM sys.databases WHERE name = '{DB_NAME}'").fetchone()
        if not exists:
            print(f"🛠 Creando base de datos '{DB_NAME}'...")
            cursor.execute(f"CREATE DATABASE {DB_NAME}")
            print(f"✅ Base de datos '{DB_NAME}' creada.")
        
        cursor.close()
        conn.close()
    except Exception as e:
        print(f"❌ Error al conectar a SQL Server: {e}")
        raise

# 2. Configuración de SQLAlchemy
DATABASE_URL = f"mssql+pyodbc://{USER}:{PASS}@{HOST}:{PORT}/{DB_NAME}?driver=ODBC+Driver+17+for+SQL+Server"

# Creamos el engine
engine = create_engine(DATABASE_URL, echo=False) 

# Session factory
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