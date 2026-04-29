import os

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
UPLOAD_FOLDER = os.path.join(BASE_DIR, "uploads")
OUTPUT_FOLDER = os.path.join(BASE_DIR, "outputs")

# ✅ Clave secreta para sesiones (flash, login, etc.)
SECRET_KEY = os.environ.get("FLASK_SECRET_KEY", "clave_default_123")
