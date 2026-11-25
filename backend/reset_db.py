from database import engine
from models import Base

# Esto borrará TODO en Conversor_DB y lo creará de nuevo limpio
Base.metadata.drop_all(bind=engine)
Base.metadata.create_all(bind=engine)
print("✅ Tablas reseteadas.")