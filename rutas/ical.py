from fastapi import APIRouter, HTTPException, Response
from pymongo import MongoClient
from bson.objectid import ObjectId
import os
from ics import Calendar, Event
from datetime import datetime, timedelta
from pytz import timezone

# Conexión a MongoDB usando variables de entorno
MONGO_URI = os.environ.get("MONGO_URI", "mongodb://localhost:27017")
ConexionMongo = MongoClient(MONGO_URI)
db = ConexionMongo["glamperos"]

# Definir la zona horaria de Colombia
ZONA_HORARIA_COLOMBIA = timezone("America/Bogota")

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

        # Obtener el nombre del glamping para personalizar el UID
        nombre_glamping = glamping.get("nombreGlamping", "Glamping")

        # Crear un calendario iCal
        calendario = Calendar()
        for fecha in glamping.get("fechasReservadas", []):
            try:
                fecha_inicio = datetime.strptime(fecha, "%Y-%m-%d")
                fecha_inicio = ZONA_HORARIA_COLOMBIA.localize(fecha_inicio)
                fecha_fin = fecha_inicio + timedelta(days=1)  # Duración de 1 día

                evento = Event()
                evento.name = "Reservado - " + nombre_glamping
                evento.begin = fecha_inicio
                evento.end = fecha_fin
                evento.uid = f"{glamping_id}-{fecha}@glamperos.com"

                calendario.events.add(evento)
            except Exception as e:
                continue  # Ignorar fechas mal formateadas

        # Devolver el archivo iCal
        return Response(str(calendario), media_type="text/calendar")

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al exportar iCal: {str(e)}")
