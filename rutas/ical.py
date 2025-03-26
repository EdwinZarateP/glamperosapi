from fastapi import APIRouter, HTTPException, Response
from pymongo import MongoClient
from bson.objectid import ObjectId
import os
from ics import Calendar, Event
from datetime import datetime, timedelta
from pytz import timezone
import requests

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

@ruta_ical.post("/importar")
async def importar_ical(glamping_id: str, url_ical: str):
    """
    Importa un archivo iCal desde Airbnb y actualiza las fechas reservadas en MongoDB.
    """
    try:
        # Descargar el archivo iCal desde la URL proporcionada
        response = requests.get(url_ical)
        if response.status_code != 200:
            raise HTTPException(status_code=400, detail="No se pudo descargar el calendario iCal")

        # Parsear el archivo iCal
        calendario = Calendar(response.text)
        fechas_reservadas = set()

        for evento in calendario.events:
            fecha_reserva = evento.begin.date().isoformat()  # Convertir a YYYY-MM-DD
            fechas_reservadas.add(fecha_reserva)

        # Actualizar la base de datos con las nuevas fechas
        db["glampings"].update_one(
            {"_id": ObjectId(glamping_id)},
            {"$addToSet": {"fechasReservadas": {"$each": list(fechas_reservadas)}}}
        )

        return {"mensaje": "Fechas sincronizadas correctamente", "fechas": list(fechas_reservadas)}

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al importar iCal: {str(e)}")



# Recorre todos los glampings que tienen URL iCal y actualiza sus fechas reservadas desde Airbnb.
@ruta_ical.post("/sincronizar-todos")
async def sincronizar_todos():

    try:
        glampings = db["glampings"].find({"urlIcal": {"$type": "string", "$ne": ""}})
        resultados = []

        for glamping in glampings:
            glamping_id = str(glamping["_id"])
            try:
                response = requests.get(glamping["urlIcal"])
                if response.status_code != 200:
                    resultados.append({"glamping_id": glamping_id, "error": "No se pudo descargar el calendario"})
                    continue

                calendario = Calendar(response.text)
                fechas_reservadas = set(event.begin.date().isoformat() for event in calendario.events)

                db["glampings"].update_one(
                    {"_id": glamping["_id"]},
                    {"$addToSet": {"fechasReservadas": {"$each": list(fechas_reservadas)}}}
                )

                resultados.append({"glamping_id": glamping_id, "fechas_agregadas": list(fechas_reservadas)})

            except Exception as e:
                resultados.append({"glamping_id": glamping_id, "error": str(e)})

        return {"resultado": resultados}

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al sincronizar todos: {str(e)}")
