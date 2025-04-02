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
    """
    Lee los campos de fechas separadas (manual, Airbnb y Booking)
    y actualiza 'fechasReservadas' con la unión de todas.
    """
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
    Genera un archivo iCal con las fechas reservadas (unión de todas las fuentes) de un glamping.
    """
    try:
        glamping = db["glampings"].find_one({"_id": ObjectId(glamping_id)})
        if not glamping:
            raise HTTPException(status_code=404, detail="Glamping no encontrado")
        nombre_glamping = glamping.get("nombreGlamping", "Glamping")
        calendario = Calendar()
        # Se exportan las fechas unidas
        for fecha in glamping.get("fechasReservadas", []):
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
            except Exception as e:
                continue  # Ignorar fechas mal formateadas
        return Response(str(calendario), media_type="text/calendar")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al exportar iCal: {str(e)}")

@ruta_ical.post("/importar")
async def importar_ical(glamping_id: str, url_ical: str, source: str = "airbnb"):
    """
    Importa un archivo iCal desde Airbnb o Booking y actualiza las fechas en MongoDB.
    Recorre cada evento (desde DTSTART hasta DTEND, sin incluir DTEND) para capturar todos los días bloqueados.
    Guarda los días importados en 'fechasReservadasAirbnb' (si source == "airbnb") o en 'fechasReservadasBooking',
    y luego actualiza 'fechasReservadas' con la unión.
    """
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
        # Determinar el campo según la fuente
        field = "fechasReservadasAirbnb" if source.lower() == "airbnb" else "fechasReservadasBooking"
        db["glampings"].update_one(
            {"_id": ObjectId(glamping_id)},
            {"$set": {field: fechas_importadas}}
        )
        # Actualiza la unión de fechas
        actualizar_union_fechas(glamping_id)
        glamping = db["glampings"].find_one({"_id": ObjectId(glamping_id)})
        return {"mensaje": "Fechas sincronizadas correctamente", "fechas": glamping.get("fechasReservadas", [])}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al importar iCal: {str(e)}")

@ruta_ical.post("/sincronizar-todos")
async def sincronizar_todos():
    """
    Recorre todos los glampings que tienen URL iCal o URL iCal Booking y actualiza sus fechas reservadas.
    Se actualizan los campos 'fechasReservadasAirbnb' y 'fechasReservadasBooking' según corresponda,
    y luego se recalcula la unión en 'fechasReservadas'.
    """
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
            # Procesar cada fuente por separado
            sources = {"airbnb": glamping.get("urlIcal", ""), "booking": glamping.get("urlIcalBooking", "")}
            for src, urls_str in sources.items():
                if isinstance(urls_str, str) and urls_str.strip() and urls_str.strip().lower() != "sin url":
                    urls = [line.strip() for line in urls_str.splitlines() if line.strip()]
                    fechas_importadas = set()
                    errores = []
                    for url in urls:
                        try:
                            headers = {
                                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
                            }
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
            # Actualizar la unión de fechas luego de procesar ambas fuentes
            actualizar_union_fechas(glamping_id)
        return {"resultado": resultados}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"🔥 Error al sincronizar todos: {str(e)}")
