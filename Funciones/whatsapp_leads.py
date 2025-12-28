# Funciones/whatsapp_leads.py

from pymongo import MongoClient
from datetime import datetime
import os
from typing import Dict, Any, Optional

MONGO_URI = os.environ.get("MONGO_URI", "mongodb://localhost:27017")
ConexionMongo = MongoClient(MONGO_URI)
db = ConexionMongo["glamperos"]

coleccion_whatsapp_leads = db["whatsapp_leads"]

def guardar_lead(
    phone: str,
    context: Dict[str, Any],
    property_id: Optional[str] = None,
) -> str:
    """
    Guarda un lead final (cuando el usuario ya respondió ciudad + fechas + fuente).
    Retorna el id insertado (string).
    """
    doc = {
        "phone": phone,
        "property_id": property_id or context.get("property_id"),
        "city": context.get("city"),
        "arrival_date": context.get("arrival_date"),
        "departure_date": context.get("departure_date"),
        "source": context.get("source"),
        "created_at": datetime.utcnow(),
        "status": "nuevo",  # luego puedes manejar: nuevo, contactado, cerrado, perdido
        "context": context,  # guardamos todo el contexto por si luego crece
    }

    res = coleccion_whatsapp_leads.insert_one(doc)
    return str(res.inserted_id)
