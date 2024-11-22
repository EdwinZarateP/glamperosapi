from bson import ObjectId
from fastapi import APIRouter, HTTPException, status, File, UploadFile, Form
from typing import List
from bd.ConexionMongo import ConexionMongo
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

def convertir_objectid(documento):
    """Convierte el campo _id de ObjectId a string en un documento MongoDB."""
    if "_id" in documento:
        documento["_id"] = str(documento["_id"])  # Convierte el ObjectId a string
    return documento


@ruta_glampings.post("/", status_code=status.HTTP_201_CREATED)
async def crear_glamping(
    nombre: str = Form(...),
    ubicacion: str = Form(...),
    precio_noche: float = Form(...),
    descripcion: str = Form(...),
    caracteristicas: str = Form(...),
    imagenes: List[UploadFile] = File(...),
    video_youtube: str = Form(None),
):
    """
    Endpoint para crear un nuevo glamping con manejo de imágenes y datos
    """
    try:
        # Procesar las imágenes subidas
        rutas_imagenes = []
        for imagen in imagenes:
            contenido = await imagen.read()
            rutas_imagenes.append({
                "filename": imagen.filename,
                "content_type": imagen.content_type,
                "size": len(contenido),
            })

        # Crear el documento
        nuevo_glamping = {
            "nombre": nombre,
            "ubicacion": ubicacion,
            "precio_noche": precio_noche,
            "descripcion": descripcion,
            "caracteristicas": caracteristicas.split(","),
            "imagenes": rutas_imagenes,
            "video_youtube": video_youtube,
        }

        # Insertar en la base de datos
        resultado = collection_glampings.insert_one(nuevo_glamping)
        nuevo_glamping["_id"] = str(resultado.inserted_id)

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
        
        # Convertir ObjectId a string y asegurar que todos los campos coincidan con SchemaGlamping
        glampings = [
            convertir_objectid(glamping) for glamping in glampings
        ]
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
        glamping = convertir_objectid(glamping)
        return glamping
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al obtener glamping: {str(e)}")
