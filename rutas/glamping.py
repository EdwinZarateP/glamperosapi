from fastapi import FastAPI, APIRouter, HTTPException, UploadFile, Form, File
from fastapi.responses import StreamingResponse
from bson.objectid import ObjectId
from pymongo import MongoClient
from gridfs import GridFS
from typing import List
from datetime import datetime
from bd.ConexionMongo import ConexionMongo  # Usa tu conexión configurada

# Configuración de la base de datos y GridFS
db = ConexionMongo["glamperos"]
fs = GridFS(db)

# Crear el router y la aplicación
ruta_glampings = APIRouter(
    prefix="/glampings",
    tags=["Glampings de glamperos"],
    responses={404: {"description": "No encontrado"}},
)

app = FastAPI()
app.include_router(ruta_glampings)


def convertir_objectid(documento):
    """
    Convierte ObjectId a string en documentos MongoDB.
    """
    if isinstance(documento, list):
        return [convertir_objectid(doc) for doc in documento]
    elif isinstance(documento, dict):
        return {
            key: str(value) if isinstance(value, ObjectId) else value
            for key, value in documento.items()
        }
    return documento


@ruta_glampings.post("/", status_code=201)
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
    Crear un glamping y almacenar imágenes en GridFS.
    """
    try:
        imagen_ids = []
        for imagen in imagenes:
            # Validar tipo de archivo
            if not imagen.content_type.startswith("image/"):
                raise HTTPException(status_code=400, detail="Solo se permiten imágenes.")

            # Guardar la imagen en GridFS
            contenido = await imagen.read()
            imagen_id = fs.put(contenido, filename=imagen.filename, content_type=imagen.content_type)
            imagen_ids.append(str(imagen_id))

        # Crear el documento del glamping
        nuevo_glamping = {
            "nombre": nombre,
            "ubicacion": ubicacion,
            "precio_noche": precio_noche,
            "descripcion": descripcion,
            "caracteristicas": caracteristicas.split(","),
            "imagenes": imagen_ids,
            "video_youtube": video_youtube,
            "calificacion": None,
            "creado": datetime.now(),
        }

        # Insertar el documento en la colección
        resultado = db["glampings"].insert_one(nuevo_glamping)
        nuevo_glamping["id"] = str(resultado.inserted_id)

        return convertir_objectid(nuevo_glamping)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al crear glamping: {str(e)}")


@ruta_glampings.get("/")
async def obtener_glampings():
    """
    Obtener todos los glampings con referencias a imágenes.
    """
    try:
        glampings = list(db["glampings"].find())
        glampings = [convertir_objectid(glamping) for glamping in glampings]

        # Generar URLs para las imágenes
        for glamping in glampings:
            glamping["imagenes"] = [
                f"https://glamperosapi.onrender.com/glampings/imagenes/{img_id}"
                for img_id in glamping.get("imagenes", [])
            ]
        return glampings
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al obtener glampings: {str(e)}")


@ruta_glampings.get("/imagenes/{imagen_id}")
async def obtener_imagen(imagen_id: str):
    """
    Obtener una imagen de GridFS por su ID.
    """
    try:
        # Buscar la imagen en GridFS
        imagen = fs.get(ObjectId(imagen_id))
        headers = {"Content-Disposition": f"inline; filename={imagen.filename}"}
        return StreamingResponse(imagen, media_type=imagen.content_type, headers=headers)
    except Exception as e:
        raise HTTPException(status_code=404, detail=f"Imagen no encontrada: {str(e)}")
