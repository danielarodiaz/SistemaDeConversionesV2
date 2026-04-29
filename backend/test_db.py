# Importamos la función init_db desde el archivo database.py
from database import init_db 

if __name__ == "__main__":
    print("Iniciando creación de tablas...")
    # Ahora sí, Python ya sabe qué es init_db
    init_db()