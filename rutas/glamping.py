from fastapi import FastAPI, APIRouter, HTTPException, UploadFile, Form, File
from fastapi.middleware.cors import CORSMiddleware
from google.cloud import storage
from pymongo import MongoClient
from bson.objectid import ObjectId
from typing import List
from datetime import datetime
import os
import uuid
import base64

# Configuración inicial para Google Cloud Storage
credenciales_base64 = os.environ.get("GOOGLE_CLOUD_CREDENTIALS")
if credenciales_base64:
    # Decodificar el JSON de credenciales desde la variable de entorno
    credenciales_json = base64.b64decode(credenciales_base64).decode("utf-8")
    with open("temp_google_credentials.json", "w") as cred_file:
        cred_file.write(credenciales_json)
    os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = "temp_google_credentials.json"

BUCKET_NAME = "glamperos-imagenes"

# Conexión a MongoDB usando variables de entorno
MONGO_URI = os.environ.get("MONGO_URI", "mongodb://localhost:27017")
ConexionMongo = MongoClient(MONGO_URI)
db = ConexionMongo["glamperos"]  # Base de datos "glamperos"

# Crear la app de FastAPI
app = FastAPI()

# Configurar CORS para múltiples orígenes
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:8000",  # Dominio local
        "http://127.0.0.1:8000",  # Otra forma del dominio local
        "https://edwinzaratep.github.io",  # Dominio de producción
    ],
    allow_credentials=True,
    allow_methods=["*"],  # Permitir todos los métodos (GET, POST, etc.)
    allow_headers=["*"],  # Permitir todos los encabezados
)

# Crear el router para glampings
ruta_glampings = APIRouter(
    prefix="/glampings",
    tags=["Glampings de glamperos"],
    responses={404: {"description": "No encontrado"}},
)
app.include_router(ruta_glampings)


# Función para subir archivos al bucket
def subir_a_google_storage(archivo: UploadFile, carpeta: str = "glampings") -> str:
    """
    Sube un archivo al bucket de Google Cloud Storage y devuelve la URL pública.
    :param archivo: UploadFile cargado por el usuario.
    :param carpeta: Carpeta dentro del bucket donde se almacenará el archivo.
    :return: URL pública del archivo.
    """
    try:
        cliente = storage.Client()
        bucket = cliente.bucket(BUCKET_NAME)

        # Crear un nombre único para el archivo
        blob_nombre = f"{carpeta}/{uuid.uuid4().hex}_{archivo.filename}"
        blob = bucket.blob(blob_nombre)

        # Subir el archivo al bucket
        blob.upload_from_file(archivo.file, content_type=archivo.content_type)

        # Generar la URL pública directamente
        return f"https://storage.googleapis.com/{BUCKET_NAME}/{blob_nombre}"
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al subir archivo: {str(e)}")


# Función para convertir ObjectId a string
def convertir_objectid(documento):
    """
    Convierte ObjectId a string en documentos MongoDB.
    :param documento: Documento o lista de documentos de MongoDB.
    :return: Documento con ObjectId convertido a string.
    """
    if isinstance(documento, list):
        return [convertir_objectid(doc) for doc in documento]
    elif isinstance(documento, dict):
        return {key: str(value) if isinstance(value, ObjectId) else value for key, value in documento.items()}
    return documento


# Endpoint para crear un nuevo glamping
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
    Crear un glamping y almacenar imágenes en Google Cloud Storage.
    """
    try:
        # Subir imágenes al bucket y generar URLs públicas
        imagen_urls = [subir_a_google_storage(imagen) for imagen in imagenes]

        # Crear el documento del glamping
        nuevo_glamping = {
            "nombre": nombre,
            "ubicacion": ubicacion,
            "precio_noche": precio_noche,
            "descripcion": descripcion,
            "caracteristicas": caracteristicas.split(","),
            "imagenes": imagen_urls,
            "video_youtube": video_youtube,
            "calificacion": None,
            "creado": datetime.now(),
        }

        # Insertar en MongoDB
        resultado = db["glampings"].insert_one(nuevo_glamping)
        nuevo_glamping["_id"] = str(resultado.inserted_id)

        # Devolver el documento con ObjectId convertido
        return convertir_objectid(nuevo_glamping)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al crear glamping: {str(e)}")


# Endpoint para obtener todos los glampings
@ruta_glampings.get("/")
async def obtener_glampings():
    """
    Obtener todos los glampings con las URLs públicas de las imágenes.
    """
    try:
        glampings = list(db["glampings"].find())
        return convertir_objectid(glampings)  # Convertir ObjectId antes de devolver
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al obtener glampings: {str(e)}")
