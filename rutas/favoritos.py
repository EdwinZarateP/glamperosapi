from fastapi import APIRouter, HTTPException, status, Query
from pymongo import MongoClient
from pydantic import BaseModel
from datetime import datetime, timezone
from typing import List
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
    fecha_agregado: datetime = datetime.now(timezone.utc)

# Modelo para formatear el favorito
def modelo_favorito(favorito) -> dict:
    return {
        "id": str(favorito["_id"]),
        "usuario_id": favorito["usuario_id"],
        "glamping_id": favorito["glamping_id"],
        "fecha_agregado": favorito["fecha_agregado"],
    }

# ✅ Endpoint para agregar un favorito (evita duplicados)
@ruta_favoritos.post("/", response_model=dict)
async def agregar_favorito(favorito: Favorito):
    existe = db.favoritos.find_one({"usuario_id": favorito.usuario_id, "glamping_id": favorito.glamping_id})
    
    if existe:
        return {"mensaje": "El favorito ya estaba guardado", "favorito": modelo_favorito(existe)}

    nuevo_favorito = favorito.model_dump()
    resultado = db.favoritos.insert_one(nuevo_favorito)
    nuevo_favorito["_id"] = str(resultado.inserted_id)
    
    return {"mensaje": "Favorito agregado", "favorito": modelo_favorito(nuevo_favorito)}

# ✅ Endpoint para listar los favoritos de un usuario
@ruta_favoritos.get("/{usuario_id}", response_model=List[str])  
async def listar_favoritos(usuario_id: str):
    favoritos = db.favoritos.find({"usuario_id": usuario_id})
    glampings_ids = [favorito["glamping_id"] for favorito in favoritos]
    
    if not glampings_ids:
        raise HTTPException(status_code=404, detail="No se encontraron favoritos para este usuario")
    
    return glampings_ids

# ✅ Endpoint para eliminar un favorito (ahora usa Query correctamente)
@ruta_favoritos.delete("/", response_model=dict)
async def eliminar_favorito(usuario_id: str = Query(...), glamping_id: str = Query(...)):
    resultado = db.favoritos.delete_one({"usuario_id": usuario_id, "glamping_id": glamping_id})
    
    if resultado.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Favorito no encontrado")
    
    return {"mensaje": "Favorito eliminado"}

# # ✅ Endpoint para verificar si un favorito existe (optimizado con count_documents)
# @ruta_favoritos.get("/buscar", response_model=dict)
# async def buscar_favorito(usuario_id: str, glamping_id: str):
#     print(f"🧪 Buscando favorito con usuario_id: '{usuario_id}' y glamping_id: '{glamping_id}'")
#     existe = db.favoritos.count_documents({"usuario_id": usuario_id, "glamping_id": glamping_id}) > 0
#     return {"favorito_existe": existe}

# ✅ Endpoint para verificar si un favorito existe (con debug y limpieza)
@ruta_favoritos.get("/buscar", response_model=dict)
async def buscar_favorito(usuario_id: str, glamping_id: str):
    # Limpieza de espacios invisibles
    usuario_id = usuario_id.strip()
    glamping_id = glamping_id.strip()

    print(f"🧪 Verificando favorito con:\n- usuario_id: '{usuario_id}'\n- glamping_id: '{glamping_id}'")

    # Buscar directamente el documento
    favorito = db.favoritos.find_one({
        "usuario_id": usuario_id,
        "glamping_id": glamping_id
    })

    if favorito:
        print("✅ Favorito encontrado en la base de datos:", favorito)
        return {"favorito_existe": True}
    else:
        print("❌ Favorito NO encontrado")
        raise HTTPException(status_code=404, detail="No se encontraron favoritos para este usuario")

