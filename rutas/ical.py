from fastapi import APIRouter, HTTPException, Response
from pymongo import MongoClient
from bson.objectid import ObjectId
import os
from ics import Calendar, Event

# Conexión a MongoDB usando variables de entorno
MONGO_URI = os.environ.get("MONGO_URI", "mongodb://localhost:27017")
ConexionMongo = MongoClient(MONGO_URI)
db = ConexionMongo["glamperos"]

# Crear el router para la sincronización de iCal
ruta_ical = APIRouter(
    prefix="/ical",
    tags=["iCal Sync"],
    responses={404: {"description": "No encontrado"}},
)

@ruta_ical.get("/exportar/{glamping_id}")
async def exportar_ical(glamping_id: str):
    """
    Genera un archivo iCal con las fechas reservadas de un glamping.
    """
    try:
        # Obtener el glamping de la BD
        glamping = db["glampings"].find_one({"_id": ObjectId(glamping_id)})
        if not glamping:
            raise HTTPException(status_code=404, detail="Glamping no encontrado")

        # Crear un calendario iCal
        calendario = Calendar()
        for fecha in glamping.get("fechasReservadas", []):
            evento = Event()
            evento.name = "Reservado"
            evento.begin = fecha  # Formato YYYY-MM-DD
            evento.duration = {"days": 1}
            calendario.events.add(evento)

        # Devolver el archivo iCal
        return Response(str(calendario), media_type="text/calendar")

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al exportar iCal: {str(e)}")
