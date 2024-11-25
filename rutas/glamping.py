from fastapi import FastAPI, APIRouter, HTTPException, UploadFile, Form, File
from fastapi.middleware.cors import CORSMiddleware
from google.cloud import storage
from pymongo import MongoClient
from bson.objectid import ObjectId
from typing import List
from datetime import datetime
from PIL import Image
from io import BytesIO
import os
import uuid
import base64
import json  # Para manejar JSON
from bd.models.glamping import ModeloGlamping

# Configuración inicial para Google Cloud Storage
credenciales_base64 = os.environ.get("GOOGLE_CLOUD_CREDENTIALS")
if credenciales_base64:
    credenciales_json = base64.b64decode(credenciales_base64).decode("utf-8")
    with open("temp_google_credentials.json", "w") as cred_file:
        cred_file.write(credenciales_json)
    os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = "temp_google_credentials.json"

BUCKET_NAME = "glamperos-imagenes"

# Conexión a MongoDB usando variables de entorno
MONGO_URI = os.environ.get("MONGO_URI", "mongodb://localhost:27017")
ConexionMongo = MongoClient(MONGO_URI)
db = ConexionMongo["glamperos"]

# Crear el router para glampings
ruta_glampings = APIRouter(
    prefix="/glampings",
    tags=["Glampings de glamperos"],
    responses={404: {"description": "No encontrado"}},
)

# Función para optimizar imágenes y convertirlas a WebP
def optimizar_imagen(archivo: UploadFile, formato: str = "WEBP", max_width: int = 1200, max_height: int = 800) -> BytesIO:
    try:
        imagen = Image.open(archivo.file)
        imagen.thumbnail((max_width, max_height), Image.Resampling.LANCZOS)
        buffer = BytesIO()
        imagen.save(buffer, format=formato, optimize=True, quality=75)
        buffer.seek(0)
        return buffer
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al optimizar imagen: {str(e)}")

# Función para subir archivos optimizados al bucket de Google Cloud Storage
def subir_a_google_storage(archivo: UploadFile, carpeta: str = "glampings") -> str:
    try:
        cliente = storage.Client()
        bucket = cliente.bucket(BUCKET_NAME)
        archivo_optimizado = optimizar_imagen(archivo)
        nombre_archivo = f"{carpeta}/{uuid.uuid4().hex}.webp"
        blob = bucket.blob(nombre_archivo)
        blob.upload_from_file(archivo_optimizado, content_type="image/webp")
        return f"https://storage.googleapis.com/{BUCKET_NAME}/{nombre_archivo}"
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al subir archivo: {str(e)}")

# Función para convertir ObjectId a string y validar `ubicacion`
def convertir_objectid(documento):
    if isinstance(documento, list):
        return [convertir_objectid(doc) for doc in documento]
    elif isinstance(documento, dict):
        documento = {key: str(value) if isinstance(value, ObjectId) else value for key, value in documento.items()}
        # Validar y convertir el campo 'ubicacion' si es un string
        if "ubicacion" in documento and isinstance(documento["ubicacion"], str):
            try:
                documento["ubicacion"] = json.loads(documento["ubicacion"])
            except json.JSONDecodeError:
                pass  # Si no es un JSON válido, se deja como está
        return documento
    return documento

# Endpoint para crear un nuevo glamping
@ruta_glampings.post("/", status_code=201, response_model=ModeloGlamping)
async def crear_glamping(
    nombre: str = Form(...),
    ubicacion: str = Form(...),
    precio_noche: float = Form(...),
    descripcion: str = Form(...),
    caracteristicas: str = Form(...),
    ciudad_departamento: str = Form(...),
    imagenes: List[UploadFile] = File(...),
    video_youtube: str = Form(None),
    propietario_id: str = Form(...),
):
    try:
        imagen_urls = [subir_a_google_storage(imagen) for imagen in imagenes]
        nuevo_glamping = {
            "nombre": nombre,
            "ubicacion": ubicacion,
            "precio_noche": precio_noche,
            "descripcion": descripcion,
            "caracteristicas": caracteristicas.split(","),
            "ciudad_departamento": ciudad_departamento,
            "imagenes": imagen_urls,
            "video_youtube": video_youtube,
            "calificacion": None,
            "creado": datetime.now(),
            "propietario_id": propietario_id,
        }
        resultado = db["glampings"].insert_one(nuevo_glamping)
        nuevo_glamping["_id"] = str(resultado.inserted_id)
        return ModeloGlamping(**convertir_objectid(nuevo_glamping))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al crear glamping: {str(e)}")

# Endpoint para obtener todos los glampings
@ruta_glampings.get("/", response_model=List[ModeloGlamping])
async def obtener_glampings():
    try:
        glampings = list(db["glampings"].find())
        return [ModeloGlamping(**convertir_objectid(glamping)) for glamping in glampings]
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al obtener glampings: {str(e)}")

# Endpoint para obtener un glamping por ID
@ruta_glampings.get("/{glamping_id}", response_model=ModeloGlamping)
async def obtener_glamping_por_id(glamping_id: str):
    try:
        glamping = db["glampings"].find_one({"_id": ObjectId(glamping_id)})
        if not glamping:
            raise HTTPException(status_code=404, detail="Glamping no encontrado")
        return ModeloGlamping(**convertir_objectid(glamping))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al obtener glamping: {str(e)}")

# Endpoint para actualizar un glamping por ID
@ruta_glampings.put("/{glamping_id}", response_model=ModeloGlamping)
async def actualizar_glamping(
    glamping_id: str,
    nombre: str = Form(None),
    ubicacion: str = Form(None),
    precio_noche: float = Form(None),
    descripcion: str = Form(None),
    caracteristicas: str = Form(None),
    ciudad_departamento: str = Form(None),
    imagenes: List[UploadFile] = File(None),
    video_youtube: str = Form(None),
    propietario_id: str = Form(None),
):
    try:
        glamping = db["glampings"].find_one({"_id": ObjectId(glamping_id)})
        if not glamping:
            raise HTTPException(status_code=404, detail="Glamping no encontrado")

        actualizaciones = {}
        if nombre:
            actualizaciones["nombre"] = nombre
        if ubicacion:
            actualizaciones["ubicacion"] = ubicacion
        if precio_noche:
            actualizaciones["precio_noche"] = precio_noche
        if descripcion:
            actualizaciones["descripcion"] = descripcion
        if caracteristicas:
            actualizaciones["caracteristicas"] = caracteristicas.split(",")
        if ciudad_departamento:
            actualizaciones["ciudad_departamento"] = ciudad_departamento
        if imagenes:
            imagen_urls = [subir_a_google_storage(imagen) for imagen in imagenes]
            actualizaciones["imagenes"] = imagen_urls
        if video_youtube:
            actualizaciones["video_youtube"] = video_youtube
        if propietario_id:
            actualizaciones["propietario_id"] = propietario_id

        db["glampings"].update_one({"_id": ObjectId(glamping_id)}, {"$set": actualizaciones})
        glamping_actualizado = db["glampings"].find_one({"_id": ObjectId(glamping_id)})
        return ModeloGlamping(**convertir_objectid(glamping_actualizado))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al actualizar glamping: {str(e)}")

# Endpoint para eliminar un glamping por ID
@ruta_glampings.delete("/{glamping_id}", status_code=204)
async def eliminar_glamping(glamping_id: str):
    try:
        resultado = db["glampings"].delete_one({"_id": ObjectId(glamping_id)})
        if resultado.deleted_count == 0:
            raise HTTPException(status_code=404, detail="Glamping no encontrado")
        return {"detail": "Glamping eliminado correctamente"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al eliminar glamping: {str(e)}")
