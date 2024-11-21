from fastapi import APIRouter, HTTPException, status
from typing import List
from bson import ObjectId
from bd.ConexionMongo import ConexionMongo
from bd.models.glamping import ModeloGlamping  
from bd.schemas.glamping import SchemaGlamping

# Conectar a la base de datos y colección
db = ConexionMongo["glamperos"]
collection_glampings = db["glampings"]

# Crear el router
ruta_glampings = APIRouter(
    prefix="/glampings",
    tags=["Glampings"],
    responses={status.HTTP_404_NOT_FOUND: {"description": "No encontrado"}},
)


@ruta_glampings.post("/", response_model=SchemaGlamping, status_code=status.HTTP_201_CREATED)
async def crear_glamping(glamping: ModeloGlamping):
    """
    Endpoint para crear un nuevo glamping
    """
    try:
        # Convertir el modelo en un diccionario
        nuevo_glamping = glamping.model_dump()

        # Convertir HttpUrl a string
        nuevo_glamping["imagenes"] = [str(url) for url in nuevo_glamping["imagenes"]]
        if nuevo_glamping.get("video_youtube"):
            nuevo_glamping["video_youtube"] = str(nuevo_glamping["video_youtube"])

        # Eliminar el ID si está presente, ya que Mongo lo genera automáticamente
        if nuevo_glamping.get("id"):
            del nuevo_glamping["id"]

        # Insertar en MongoDB
        resultado = collection_glampings.insert_one(nuevo_glamping)
        nuevo_glamping["id"] = str(resultado.inserted_id)

        return nuevo_glamping
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al crear glamping: {str(e)}")


@ruta_glampings.get("/", response_model=List[SchemaGlamping])
async def obtener_glampings():
    """
    Endpoint para obtener todos los glampings
    """
    try:
        # Consultar todos los glampings de la colección
        glampings = list(collection_glampings.find())
        for glamping in glampings:
            glamping["id"] = str(glamping["_id"])
            del glamping["_id"]  # Eliminar el _id original para evitar problemas de serialización
        return glampings
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al obtener glampings: {str(e)}")


@ruta_glampings.get("/{id}", response_model=SchemaGlamping)
async def obtener_glamping_por_id(id: str):
    """
    Endpoint para obtener un glamping por su ID
    """
    try:
        # Buscar un glamping por su ID
        glamping = collection_glampings.find_one({"_id": ObjectId(id)})
        if not glamping:
            raise HTTPException(status_code=404, detail="Glamping no encontrado")
        glamping["id"] = str(glamping["_id"])
        del glamping["_id"]
        return glamping
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al obtener glamping: {str(e)}")
