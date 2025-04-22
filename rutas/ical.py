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

# Función auxiliar para actualizar la unión de fechas
def actualizar_union_fechas(glamping_id: str):
    glamping = db["glampings"].find_one({"_id": ObjectId(glamping_id)})
    manual = set(glamping.get("fechasReservadasManual", []))
    airbnb = set(glamping.get("fechasReservadasAirbnb", []))
    booking = set(glamping.get("fechasReservadasBooking", []))
    union = list(manual.union(airbnb).union(booking))
    db["glampings"].update_one(
        {"_id": ObjectId(glamping_id)},
        {"$set": {"fechasReservadas": union}}
    )

# Crear el router para la sincronización de iCal
ruta_ical = APIRouter(
    prefix="/ical",
    tags=["iCal Sync"],
    responses={404: {"description": "No encontrado"}},
)

@ruta_ical.get("/exportar/{glamping_id}")
async def exportar_ical(glamping_id: str):
    """
    Genera un archivo iCal con solo las fechas manuales de un glamping.
    """
    try:
        glamping = db["glampings"].find_one({"_id": ObjectId(glamping_id)})
        if not glamping:
            raise HTTPException(status_code=404, detail="Glamping no encontrado")

        nombre_glamping = glamping.get("nombreGlamping", "Glamping")
        calendario = Calendar()

        for fecha in glamping.get("fechasReservadasManual", []):
            try:
                fecha_inicio = datetime.strptime(fecha, "%Y-%m-%d")
                fecha_inicio = ZONA_HORARIA_COLOMBIA.localize(fecha_inicio)
                fecha_fin = fecha_inicio + timedelta(days=1)
                evento = Event()
                evento.name = "Reservado - " + nombre_glamping
                evento.begin = fecha_inicio
                evento.end = fecha_fin
                evento.uid = f"{glamping_id}-{fecha}@glamperos.com"
                calendario.events.add(evento)
            except Exception:
                continue

        return Response(calendario.serialize(), media_type="text/calendar")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al exportar iCal: {str(e)}")

@ruta_ical.post("/importar")
async def importar_ical(glamping_id: str, url_ical: str, source: str = "airbnb"):
    try:
        response = requests.get(url_ical)
        if response.status_code != 200:
            raise HTTPException(status_code=400, detail="No se pudo descargar el calendario iCal")

        calendario = Calendar(response.text)
        fechas_importadas = set()
        for evento in calendario.events:
            inicio = evento.begin.date()
            fin = evento.end.date()
            fecha_actual = inicio
            while fecha_actual < fin:
                fechas_importadas.add(fecha_actual.isoformat())
                fecha_actual += timedelta(days=1)

        fechas_importadas = list(fechas_importadas)
        field = "fechasReservadasAirbnb" if source.lower() == "airbnb" else "fechasReservadasBooking"

        db["glampings"].update_one(
            {"_id": ObjectId(glamping_id)},
            {"$set": {field: fechas_importadas}}
        )

        actualizar_union_fechas(glamping_id)
        glamping = db["glampings"].find_one({"_id": ObjectId(glamping_id)})
        return {"mensaje": "Fechas sincronizadas correctamente", "fechas": glamping.get("fechasReservadas", [])}

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al importar iCal: {str(e)}")

@ruta_ical.post("/sincronizar-todos")
async def sincronizar_todos():
    try:
        glampings = db["glampings"].find({
            "$or": [
                {"urlIcal": {"$nin": [None, "", "Sin url", "sin url", "SIN URL"]}},
                {"urlIcalBooking": {"$nin": [None, "", "Sin url", "sin url", "SIN URL"]}}
            ]
        })

        resultados = []

        for glamping in glampings:
            glamping_id = str(glamping["_id"])
            sources = {
                "airbnb": glamping.get("urlIcal", ""),
                "booking": glamping.get("urlIcalBooking", "")
            }

            for src, urls_str in sources.items():
                if isinstance(urls_str, str) and urls_str.strip().lower() != "sin url":
                    urls = [line.strip() for line in urls_str.splitlines() if line.strip()]
                    fechas_importadas = set()
                    errores = []

                    for url in urls:
                        try:
                            headers = {"User-Agent": "Mozilla/5.0"}
                            response = requests.get(url, headers=headers, timeout=10)
                            if response.status_code != 200:
                                errores.append(f"⛔ URL fallida ({url}): status {response.status_code}")
                                continue
                            calendario = Calendar(response.text)
                            for evento in calendario.events:
                                inicio = evento.begin.date()
                                fin = evento.end.date()
                                fecha_actual = inicio
                                while fecha_actual < fin:
                                    fechas_importadas.add(fecha_actual.isoformat())
                                    fecha_actual += timedelta(days=1)
                        except Exception as err:
                            errores.append(f"⚠️ Error en URL ({url}): {str(err)}")

                    if fechas_importadas:
                        field = "fechasReservadasAirbnb" if src == "airbnb" else "fechasReservadasBooking"
                        db["glampings"].update_one(
                            {"_id": glamping["_id"]},
                            {"$set": {field: list(fechas_importadas)}}
                        )
                        resultados.append({
                            "glamping_id": glamping_id,
                            "source": src,
                            "fechas_importadas": list(fechas_importadas)
                        })
                    else:
                        resultados.append({
                            "glamping_id": glamping_id,
                            "source": src,
                            "error": "No se pudo importar ninguna fecha",
                            "detalles": errores
                        })

            actualizar_union_fechas(glamping_id)

        return {"resultado": resultados}

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"🔥 Error al sincronizar todos: {str(e)}")