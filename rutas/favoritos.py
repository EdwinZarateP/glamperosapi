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

# Crear el router para favoritos
ruta_favoritos = APIRouter(
    prefix="/favoritos",
    tags=["Favoritos"],
    responses={status.HTTP_404_NOT_FOUND: {"message": "No encontrado"}},
)

# Modelo de datos para favoritos
class Favorito(BaseModel):
    usuario_id: str
    glamping_id: str
    fecha_agregado: datetime = datetime.utcnow()

# Modelo para formatear el favorito
def modelo_favorito(favorito) -> dict:
    return {
        "id": str(favorito["_id"]),
        "usuario_id": favorito["usuario_id"],
        "glamping_id": favorito["glamping_id"],
        "fecha_agregado": favorito["fecha_agregado"],
    }

# Endpoint para agregar un favorito
@ruta_favoritos.post("/", response_model=dict)
async def agregar_favorito(favorito: Favorito):
    # Verificar si ya existe el favorito
    existe = db.favoritos.find_one({
        "usuario_id": favorito.usuario_id,
        "glamping_id": favorito.glamping_id,
    })
    if existe:
        raise HTTPException(status_code=400, detail="El favorito ya existe")

    # Agregar el favorito
    nuevo_favorito = favorito.dict()
    resultado = db.favoritos.insert_one(nuevo_favorito)
    nuevo_favorito["_id"] = str(resultado.inserted_id)
    return {"mensaje": "Favorito agregado", "favorito": modelo_favorito(nuevo_favorito)}

# Endpoint para listar favoritos de un usuario
@ruta_favoritos.get("/{usuario_id}", response_model=List[dict])
async def listar_favoritos(usuario_id: str):
    favoritos = list(db.favoritos.find({"usuario_id": usuario_id}))
    if not favoritos:
        raise HTTPException(status_code=404, detail="No se encontraron favoritos para este usuario")
    return [modelo_favorito(f) for f in favoritos]

# Endpoint para eliminar un favorito
@ruta_favoritos.delete("/{favorito_id}", response_model=dict)
async def eliminar_favorito(favorito_id: str):
    resultado = db.favoritos.delete_one({"_id": ObjectId(favorito_id)})
    if resultado.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Favorito no encontrado")
    return {"mensaje": "Favorito eliminado"}

# Endpoint para buscar un favorito
@ruta_favoritos.get("/buscar", response_model=dict)
async def buscar_favorito(usuario_id: str, glamping_id: str):
    favorito = db.favoritos.find_one({"usuario_id": usuario_id, "glamping_id": glamping_id})
    if not favorito:
        raise HTTPException(status_code=404, detail="Favorito no encontrado")
    return modelo_favorito(favorito)
