from fastapi import FastAPI, APIRouter, HTTPException, UploadFile, Form, File
from fastapi.middleware.cors import CORSMiddleware
from google.cloud import storage
from pymongo import MongoClient
from bson.objectid import ObjectId
from typing import Optional, List, Dict
from datetime import datetime
from PIL import Image
from io import BytesIO
import os
import uuid
import base64
from dotenv import load_dotenv  # Para cargar las variables de entorno desde .env

# === Cargar variables de entorno ===
load_dotenv()  # Carga las variables de entorno desde el archivo .env

# Configuración inicial
MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017")
GOOGLE_CLOUD_CREDENTIALS = os.getenv("GOOGLE_CLOUD_CREDENTIALS")
BUCKET_NAME = os.getenv("BUCKET_NAME", "default-bucket")

# Configurar Google Cloud Credentials
if GOOGLE_CLOUD_CREDENTIALS:
    credenciales_json = base64.b64decode(GOOGLE_CLOUD_CREDENTIALS).decode("utf-8")
    with open("temp_google_credentials.json", "w") as cred_file:
        cred_file.write(credenciales_json)
    os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = "temp_google_credentials.json"

# Conexión a MongoDB
ConexionMongo = MongoClient(MONGO_URI)
db = ConexionMongo["glamperos"]

# === Modelos y Esquemas ===
from pydantic import BaseModel, HttpUrl


class ModeloGlamping(BaseModel):
    id: Optional[str] = None                          # ID generado por MongoDB
    nombre: str                                       # Nombre del glamping
    ubicacion: Dict[str, float]                      # Ubicación (latitud y longitud)
    precio_noche: float                               # Precio por noche
    descripcion: str                                  # Descripción
    imagenes: List[str]                               # Lista de rutas/URLs de imágenes
    video_youtube: Optional[HttpUrl] = None          # Video de YouTube (opcional)
    calificacion: Optional[float] = None             # Promedio de calificaciones (1.0 a 5.0)
    caracteristicas: List[str]                       # Características del glamping
    servicios: List[str]                              # Servicios adicionales
    propietario_id: Optional[str] = None             # ID del propietario
    ciudad_departamento: str                         # Ciudad y departamento del glamping
    creado: Optional[datetime] = None                # Fecha de creación (opcional)

# === Utilidades ===
def convertir_objectid(documento):
    if isinstance(documento, list):
        return [convertir_objectid(doc) for doc in documento]
    elif isinstance(documento, dict):
        return {key: str(value) if isinstance(value, ObjectId) else value for key, value in documento.items()}
    return documento


def subir_a_google_storage(archivo: UploadFile, carpeta: str = "glampings") -> str:
    try:
        cliente = storage.Client()
        bucket = cliente.bucket(BUCKET_NAME)

        # Convertimos la imagen a WebP
        buffer = BytesIO()
        imagen = Image.open(archivo.file)
        imagen.save(buffer, format="WEBP", optimize=True, quality=75)
        buffer.seek(0)

        # Subimos la imagen al bucket
        nombre_archivo = f"{carpeta}/{uuid.uuid4().hex}.webp"
        blob = bucket.blob(nombre_archivo)
        blob.upload_from_file(buffer, content_type="image/webp")
        return f"https://storage.googleapis.com/{BUCKET_NAME}/{nombre_archivo}"
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al subir archivo: {str(e)}")


# === Endpoints ===
ruta_glampings = APIRouter(
    prefix="/glampings",
    tags=["Glampings"],
    responses={404: {"description": "No encontrado"}},
)

@ruta_glampings.post("/", status_code=201)
async def crear_glamping(
    nombre: str = Form(...),
    ubicacion: str = Form(...),
    precio_noche: float = Form(...),
    descripcion: str = Form(...),
    caracteristicas: str = Form(...),
    servicios: str = Form(...),
    ciudad_departamento: str = Form(...),
    propietario_id: Optional[str] = Form(None),
    imagenes: List[UploadFile] = File(...),
    video_youtube: Optional[str] = Form(None),
):
    try:
        imagen_urls = [subir_a_google_storage(imagen) for imagen in imagenes]
        ubicacion_dict = {k: float(v) for k, v in (x.split(":") for x in ubicacion.split(","))}

        nuevo_glamping = ModeloGlamping(
            nombre=nombre,
            ubicacion=ubicacion_dict,
            precio_noche=precio_noche,
            descripcion=descripcion,
            caracteristicas=caracteristicas.split(","),
            servicios=servicios.split(","),
            ciudad_departamento=ciudad_departamento,
            propietario_id=propietario_id,
            imagenes=imagen_urls,
            video_youtube=video_youtube,
            creado=datetime.now(),
        ).dict()

        resultado = db["glampings"].insert_one(nuevo_glamping)
        nuevo_glamping["_id"] = str(resultado.inserted_id)
        return convertir_objectid(nuevo_glamping)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al crear glamping: {str(e)}")


@ruta_glampings.get("/")
async def obtener_glampings():
    try:
        glampings = list(db["glampings"].find())
        return convertir_objectid(glampings)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al obtener glampings: {str(e)}")


@ruta_glampings.get("/{glamping_id}")
async def obtener_glamping_por_id(glamping_id: str):
    try:
        glamping = db["glampings"].find_one({"_id": ObjectId(glamping_id)})
        if not glamping:
            raise HTTPException(status_code=404, detail="Glamping no encontrado")
        return convertir_objectid(glamping)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al obtener glamping: {str(e)}")


@ruta_glampings.put("/{glamping_id}")
async def actualizar_glamping(
    glamping_id: str,
    nombre: Optional[str] = Form(None),
    ubicacion: Optional[str] = Form(None),
    precio_noche: Optional[float] = Form(None),
    descripcion: Optional[str] = Form(None),
    caracteristicas: Optional[str] = Form(None),
    servicios: Optional[str] = Form(None),
    ciudad_departamento: Optional[str] = Form(None),
    imagenes: List[UploadFile] = File(None),
    video_youtube: Optional[str] = Form(None),
):
    try:
        actualizaciones = {}
        if nombre:
            actualizaciones["nombre"] = nombre
        if ubicacion:
            actualizaciones["ubicacion"] = {k: float(v) for k, v in (x.split(":") for x in ubicacion.split(","))}
        if precio_noche:
            actualizaciones["precio_noche"] = precio_noche
        if descripcion:
            actualizaciones["descripcion"] = descripcion
        if caracteristicas:
            actualizaciones["caracteristicas"] = caracteristicas.split(",")
        if servicios:
            actualizaciones["servicios"] = servicios.split(",")
        if ciudad_departamento:
            actualizaciones["ciudad_departamento"] = ciudad_departamento
        if imagenes:
            imagen_urls = [subir_a_google_storage(imagen) for imagen in imagenes]
            actualizaciones["imagenes"] = imagen_urls
        if video_youtube:
            actualizaciones["video_youtube"] = video_youtube

        db["glampings"].update_one({"_id": ObjectId(glamping_id)}, {"$set": actualizaciones})
        glamping_actualizado = db["glampings"].find_one({"_id": ObjectId(glamping_id)})
        return convertir_objectid(glamping_actualizado)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al actualizar glamping: {str(e)}")


@ruta_glampings.delete("/{glamping_id}", status_code=204)
async def eliminar_glamping(glamping_id: str):
    try:
        resultado = db["glampings"].delete_one({"_id": ObjectId(glamping_id)})
        if resultado.deleted_count == 0:
            raise HTTPException(status_code=404, detail="Glamping no encontrado")
        return {"detail": "Glamping eliminado correctamente"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al eliminar glamping: {str(e)}")
