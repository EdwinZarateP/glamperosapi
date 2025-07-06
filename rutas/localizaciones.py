from fastapi import APIRouter, HTTPException, Body
from pymongo import MongoClient
from datetime import datetime
from typing import Optional
import os
import base64

# 🔗 Conexión a la base de datos glamperos
MONGO_URI = os.environ.get("MONGO_URI", "mongodb://localhost:27017")
ConexionMongo = MongoClient(MONGO_URI)
db = ConexionMongo["glamperos"]

# 🔧 Configuración inicial si usas Google Cloud (opcional, si luego subes algo aquí)
credenciales_base64 = os.environ.get("GOOGLE_CLOUD_CREDENTIALS")
if credenciales_base64:
    credenciales_json = base64.b64decode(credenciales_base64).decode("utf-8")
    with open("temp_google_credentials.json", "w") as cred_file:
        cred_file.write(credenciales_json)
    os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = "temp_google_credentials.json"

# 📌 Definir router de localizaciones
ruta_localizaciones = APIRouter(
    prefix="/localizaciones",
    tags=["Localizaciones"],
    responses={404: {"description": "No encontrado"}},
)

@ruta_localizaciones.post("/", status_code=201)
async def guardar_localizacion(
    lat: float = Body(..., embed=True),
    lng: float = Body(..., embed=True),
    user_id: Optional[str] = Body(None, embed=True)
):
    """
    Guarda una localización con latitud y longitud.
    El `user_id` es opcional.
    """
    try:
        nueva_localizacion = {
            "lat": lat,
            "lng": lng,
            "fecha_guardado": datetime.utcnow(),
        }

        if user_id:
            nueva_localizacion["user_id"] = user_id

        resultado = db["localizaciones"].insert_one(nueva_localizacion)

        # Agrega el _id generado como string al response
        nueva_localizacion["_id"] = str(resultado.inserted_id)

        return {
            "mensaje": "Localización guardada correctamente",
            "localizacion": nueva_localizacion
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al guardar localización: {str(e)}")

@ruta_localizaciones.get("/", status_code=200)
async def listar_localizaciones(user_id: Optional[str] = None):
    """
    Lista todas las localizaciones guardadas.
    Si se pasa `user_id`, filtra por ese usuario.
    """
    try:
        filtro = {}
        if user_id:
            filtro["user_id"] = user_id

        localizaciones = list(db["localizaciones"].find(filtro).sort("fecha_guardado", -1))

        # Convertir _id de ObjectId a string
        for loc in localizaciones:
            loc["_id"] = str(loc["_id"])

        return localizaciones

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al obtener localizaciones: {str(e)}")
