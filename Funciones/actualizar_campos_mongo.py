from dotenv import load_dotenv
import os
from pymongo import MongoClient

# 🔄 Cargar variables desde .env
load_dotenv()

# ✅ Ahora sí tomará el valor desde tu archivo .env
MONGO_URI = os.environ.get("MONGO_URI")
client = MongoClient(MONGO_URI)
db = client["glamperos"]

# Actualizar todos los documentos
resultado = db["glampings"].update_many(
    {},
    {
        "$set": {
            "decoracion_sencilla": "",
            "valor_decoracion_sencilla": 0,
            "decoracion_especial": "",
            "valor_decoracion_especial": 0
        }
    }
)

print(f"✅ Documentos modificados: {resultado.modified_count}")
