from fastapi import APIRouter, HTTPException, Depends, status
from pymongo import MongoClient
from bson import ObjectId
from typing import List
from pydantic import BaseModel
from datetime import datetime
import os

# Configuración de la base de datos
MONGO_URI = os.environ.get("MONGO_URI", "mongodb://localhost:27017")
ConexionMongo = MongoClient(MONGO_URI)
db = ConexionMongo["glamperos"]

# Crear el router para evaluaciones
ruta_evaluaciones = APIRouter(
    prefix="/evaluaciones",
    tags=["Evaluaciones"],
    responses={status.HTTP_404_NOT_FOUND: {"message": "No encontrado"}},
)

# Modelo de datos para evaluaciones
class Evaluacion(BaseModel):
    usuario_id: str
    glamping_id: str
    fecha_agregado: datetime = datetime.utcnow()
    calificacion: float  # Campo numérico para calificación
    comentario: str  # Campo de texto para comentarios

# Modelo para formatear la evaluación
def modelo_evaluacion(evaluacion) -> dict:
    return {
        "id": str(evaluacion["_id"]),
        "usuario_id": evaluacion["usuario_id"],
        "glamping_id": evaluacion["glamping_id"],
        "fecha_agregado": evaluacion["fecha_agregado"],
        "calificacion": evaluacion["calificacion"],
        "comentario": evaluacion["comentario"],
    }

# Endpoint para agregar una evaluación
@ruta_evaluaciones.post("/", response_model=dict)
async def agregar_evaluacion(evaluacion: Evaluacion):
    # Agregar la evaluación directamente sin verificar si ya existe
    nueva_evaluacion = evaluacion.model_dump()
    resultado = db.evaluaciones.insert_one(nueva_evaluacion)
    nueva_evaluacion["_id"] = str(resultado.inserted_id)
    return {"mensaje": "Evaluación agregada", "evaluacion": modelo_evaluacion(nueva_evaluacion)}

# Endpoint para listar evaluaciones de un glamping
@ruta_evaluaciones.get("/glamping/{glamping_id}", response_model=List[dict])
async def listar_evaluaciones_glamping(glamping_id: str):
    evaluaciones = list(db.evaluaciones.find({"glamping_id": glamping_id}))
    if not evaluaciones:
        raise HTTPException(status_code=404, detail="No se encontraron evaluaciones para este glamping")
    return [modelo_evaluacion(evaluacion) for evaluacion in evaluaciones]

# Endpoint para eliminar una evaluación
@ruta_evaluaciones.delete("/", response_model=dict)
async def eliminar_evaluacion(usuario_id: str, glamping_id: str):
    resultado = db.evaluaciones.delete_one({"usuario_id": usuario_id, "glamping_id": glamping_id})
    if resultado.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Evaluación no encontrada")
    return {"mensaje": "Evaluación eliminada"}

# Endpoint para buscar una evaluación
@ruta_evaluaciones.get("/buscar", response_model=dict)
async def buscar_evaluacion(usuario_id: str, glamping_id: str):
    evaluacion = db.evaluaciones.find_one({"usuario_id": usuario_id, "glamping_id": glamping_id})
    if evaluacion:
        return {"evaluacion_existe": True, "evaluacion": modelo_evaluacion(evaluacion)}
    else:
        return {"evaluacion_existe": False}
