# Funciones/chat_state.py

from pymongo import MongoClient
from datetime import datetime, timedelta
import os

# 🔗 Conexión a MongoDB (igual que tú)
MONGO_URI = os.environ.get("MONGO_URI", "mongodb://localhost:27017")
ConexionMongo = MongoClient(MONGO_URI)
db = ConexionMongo["glamperos"]

# 📦 Colección para estados de chat
coleccion_chat_states = db["chat_states"]

# (Opcional) Expiración de estado: si alguien vuelve después de mucho tiempo, reiniciar flujo
STATE_TTL_MINUTES = int(os.getenv("WHATSAPP_STATE_TTL_MINUTES", "60"))

def get_state(phone: str):
    """
    Retorna dict: {"state": "...", "context": {...}}
    Si no existe o expiró, retorna MENU.
    """
    doc = coleccion_chat_states.find_one({"phone": phone})
    if not doc:
        return {"state": "MENU", "context": {}}

    updated_at = doc.get("updated_at")
    if updated_at and STATE_TTL_MINUTES > 0:
        if datetime.utcnow() - updated_at > timedelta(minutes=STATE_TTL_MINUTES):
            # expiró: reiniciar
            reset_state(phone)
            return {"state": "MENU", "context": {}}

    return {
        "state": doc.get("state", "MENU"),
        "context": doc.get("context", {}) or {}
    }

def set_state(phone: str, state: str, context: dict = None):
    """
    Guarda estado y contexto.
    """
    coleccion_chat_states.update_one(
        {"phone": phone},
        {
            "$set": {
                "phone": phone,
                "state": state,
                "context": context or {},
                "updated_at": datetime.utcnow(),
            }
        },
        upsert=True
    )

def reset_state(phone: str):
    set_state(phone, "MENU", {})
