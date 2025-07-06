# rutas/ruta_visitas.py

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from pymongo import MongoClient
from datetime import datetime
from typing import Optional, List
from bson import ObjectId
import os

# 🔗 Conexión a MongoDB
MONGO_URI = os.environ.get("MONGO_URI", "mongodb://localhost:27017")
ConexionMongo = MongoClient(MONGO_URI)
db = ConexionMongo["glamperos"]

# 📦 Colección visitas
coleccion_visitas = db["visitas"]

# ⚙️ Crear router visitas
ruta_visitas = APIRouter(
    prefix="/visitas",
    tags=["Visitas"],
    responses={404: {"description": "No encontrado"}},
)

# 📝 Modelo de la visita
class Visita(BaseModel):
    glamping_id: str
    fecha: Optional[datetime] = None
    user_id: Optional[str] = "no_identificado"

# ➕ Endpoint para registrar visita
@ruta_visitas.post("/", status_code=201)
async def registrar_visita(visita: Visita):
    """
    Registra una visita a un glamping.
    - glamping_id (obligatorio)
    - fecha (opcional, default hoy)
    - user_id (opcional, default 'no_identificado')
    """
    try:
        # ✅ Validar que el glamping existe
        if not db["glampings"].find_one({"_id": ObjectId(visita.glamping_id)}):
            raise HTTPException(status_code=404, detail="Glamping no encontrado")

        # 🗓️ Usar fecha actual si no la envían
        fecha = visita.fecha or datetime.utcnow()

        # 📥 Crear documento de visita (guardando glamping_id como string)
        doc = {
            "glamping_id": visita.glamping_id,
            "fecha": fecha,
            "user_id": visita.user_id,
            "creado": datetime.utcnow()
        }

        resultado = coleccion_visitas.insert_one(doc)

        return {
            "mensaje": "Visita registrada correctamente",
            "id_visita": str(resultado.inserted_id)
        }

    except HTTPException as he:
        raise he
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error interno: {str(e)}")

# 🔍 Endpoint para listar visitas (opcionalmente filtradas por glamping_id)
@ruta_visitas.get("/", status_code=200)
async def listar_visitas(glamping_id: Optional[str] = Query(None)):
    """
    Devuelve un listado de visitas.
    - glamping_id (opcional): filtra por glamping específico
    """
    try:
        filtro = {}
        if glamping_id:
            filtro["glamping_id"] = glamping_id

        visitas = list(coleccion_visitas.find(filtro).sort("fecha", -1))
        
        # Convertir ObjectId y datetime a string para el response
        for v in visitas:
            v["_id"] = str(v["_id"])
            v["fecha"] = v["fecha"].isoformat()
            v["creado"] = v["creado"].isoformat()

        return visitas

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al listar visitas: {str(e)}")

# 📊 Endpoint de informe: conteo de visitas por glamping
@ruta_visitas.get("/informe/conteo", status_code=200)
async def conteo_visitas():
    """
    Devuelve el conteo total de visitas agrupadas por glamping_id.
    """
    try:
        pipeline = [
            {
                "$group": {
                    "_id": "$glamping_id",
                    "total_visitas": {"$sum": 1}
                }
            },
            {
                "$sort": {"total_visitas": -1}
            }
        ]

        resultados = list(coleccion_visitas.aggregate(pipeline))

        # Renombrar _id a glamping_id en el resultado
        informe = [
            {"glamping_id": r["_id"], "total_visitas": r["total_visitas"]}
            for r in resultados
        ]

        return informe

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al generar informe: {str(e)}")
