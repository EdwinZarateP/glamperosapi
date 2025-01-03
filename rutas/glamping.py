from fastapi import APIRouter, HTTPException, UploadFile, Form, File
from google.cloud import storage
from pymongo import MongoClient
from bson.objectid import ObjectId
from typing import List, Optional
from datetime import datetime
from datetime import datetime
from PIL import Image
from io import BytesIO
import os
import base64
import uuid
import json
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
    tags=["Glampings"],
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
        raise HTTPException(status_code=400, detail=f"Error al optimizar la imagen: {str(e)}")

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
        raise HTTPException(status_code=500, detail=f"Error al subir la imagen a Google Storage: {str(e)}")


# Función para convertir ObjectId a string y validar `ubicacion`
def convertir_objectid(documento):
    if isinstance(documento, list):
        return [convertir_objectid(doc) for doc in documento]
    elif isinstance(documento, dict):
        documento["_id"] = str(documento["_id"]) if "_id" in documento else None
        if "ubicacion" in documento and isinstance(documento["ubicacion"], str):
            try:
                documento["ubicacion"] = json.loads(documento["ubicacion"])
            except json.JSONDecodeError:
                pass
        return documento
    return documento


# Crear un nuevo glamping con validaciones por cada paso
@ruta_glampings.post("/", status_code=201, response_model=ModeloGlamping)
async def crear_glamping(
    habilitado: Optional[bool] = Form(False),
    nombreGlamping: str = Form(...),
    tipoGlamping: str = Form(...),
    Acepta_Mascotas: bool = Form(...),
    ubicacion: str = Form(...),
    precioEstandar: float = Form(...),
    Cantidad_Huespedes: float = Form(...),
    descuento: float = Form(...),
    descripcionGlamping: str = Form(...),
    amenidadesGlobal: str = Form(...),
    ciudad_departamento: str = Form(...),
    imagenes: List[UploadFile] = File(...),
    video_youtube: str = Form(None),
    fechasReservadas: Optional[str] = Form(None),
    propietario_id: str = Form(...),
):
    try:
        # Validación de las imágenes una por una
        imagen_urls = []
        for imagen in imagenes:
            try:
                url_imagen = subir_a_google_storage(imagen)
                imagen_urls.append(url_imagen)
            except HTTPException as e:
                raise HTTPException(status_code=400, detail=f"Error con la imagen '{imagen.filename}': {e.detail}")

        # Manejo de fechasReservadas
        fechas_reservadas_lista = fechasReservadas.split(",") if fechasReservadas else []

        # Procesamiento de amenidadesGlobal: convertir de cadena a lista de amenidades
        amenidades_lista = [amenidad.strip() for amenidad in amenidadesGlobal.split(",")]

        # Crear el glamping en la base de datos
        nuevo_glamping = {
            "habilitado":habilitado,
            "nombreGlamping": nombreGlamping,
            "tipoGlamping": tipoGlamping,
            "Acepta_Mascotas": Acepta_Mascotas,
            "ubicacion": ubicacion,
            "precioEstandar": precioEstandar,
            "Cantidad_Huespedes": Cantidad_Huespedes,
            "descuento": descuento,
            "descripcionGlamping": descripcionGlamping,
            "amenidadesGlobal": amenidades_lista,
            "ciudad_departamento": ciudad_departamento,
            "imagenes": imagen_urls,
            "video_youtube": video_youtube,
            "calificacion": 4.5,
            "fechasReservadas": fechas_reservadas_lista,
            "creado": datetime.now(),
            "propietario_id": propietario_id,
        }

        # Intentar insertar en MongoDB
        resultado = db["glampings"].insert_one(nuevo_glamping)
        glamping_id = str(resultado.inserted_id)

        # Asociar glamping al usuario propietario
        db["usuarios"].update_one(
            {"_id": ObjectId(propietario_id)},
            {"$push": {"glampings": glamping_id}}
        )

        nuevo_glamping["_id"] = glamping_id
        return ModeloGlamping(**convertir_objectid(nuevo_glamping))

    except HTTPException as he:
        # Lanza errores específicos que se hayan identificado
        raise he
    except Exception as e:
        # Captura otros errores no esperados
        raise HTTPException(status_code=500, detail=f"Error interno: {str(e)}")


# Obtener todos los glampings
@ruta_glampings.get("/", response_model=List[ModeloGlamping])
async def obtener_glampings(page: int = 1, limit: int = 30):
    """
    Obtiene una lista de glampings con paginación.
    
    - `page`: Número de página, por defecto 1.
    - `limit`: Tamaño del lote, por defecto 30.
    """
    try:
        if page < 1 or limit < 1:
            raise HTTPException(status_code=400, detail="Los parámetros `page` y `limit` deben ser mayores a 0")
        
        # Calcular los índices de paginación
        skip = (page - 1) * limit
        
        # Obtener los glampings con límites y saltos
        glampings = list(db["glampings"].find().skip(skip).limit(limit))
        glampings_convertidos = [convertir_objectid(glamping) for glamping in glampings]
        return glampings_convertidos
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al obtener glampings: {str(e)}")



# Obtener un glamping por ID
@ruta_glampings.get("/{glamping_id}", response_model=ModeloGlamping)
async def obtener_glamping_por_id(glamping_id: str):
    try:
        glamping = db["glampings"].find_one({"_id": ObjectId(glamping_id)})
        if not glamping:
            raise HTTPException(status_code=404, detail="Glamping no encontrado")
        return ModeloGlamping(**convertir_objectid(glamping))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al obtener glamping: {str(e)}")


# Eliminar un glamping
@ruta_glampings.delete("/{glamping_id}", status_code=204)
async def eliminar_glamping(glamping_id: str):
    try:
        resultado = db["glampings"].delete_one({"_id": ObjectId(glamping_id)})
        if resultado.deleted_count == 0:
            raise HTTPException(status_code=404, detail="Glamping no encontrado")
        return {"mensaje": "Glamping eliminado correctamente"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al eliminar glamping: {str(e)}")



# Con esto se obtienen los favoritos
@ruta_glampings.post("/por_ids", response_model=List[ModeloGlamping])
async def obtener_glampings_por_ids(glamping_ids: List[str]):
    """
    Obtiene los glampings que coincidan con los IDs proporcionados.

    - `glamping_ids`: Lista de IDs de los glampings.
    """
    try:
        # Convertir los IDs a ObjectId
        object_ids = [ObjectId(glamping_id) for glamping_id in glamping_ids]
        
        # Consultar en la base de datos
        glampings = list(db["glampings"].find({"_id": {"$in": object_ids}}))
        
        # Verificar si se encontraron resultados
        if not glampings:
            raise HTTPException(status_code=404, detail="No se encontraron glampings con los IDs proporcionados")
        
        # Convertir los documentos para incluir `ObjectId` como string
        glampings_convertidos = [convertir_objectid(glamping) for glamping in glampings]
        return glampings_convertidos
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al obtener glampings por IDs: {str(e)}")



# Actualizar la calificación de un glamping
@ruta_glampings.patch("/{glamping_id}/calificacion", response_model=ModeloGlamping)
async def actualizar_calificacion(
    glamping_id: str,
    calificacion: float = Form(..., ge=0, le=5)  # Validación para que la calificación esté entre 0 y 5
):
    try:
        # Buscar el glamping por ID
        glamping = db["glampings"].find_one({"_id": ObjectId(glamping_id)})
        if not glamping:
            raise HTTPException(status_code=404, detail="Glamping no encontrado")

        # Actualizar la calificación
        actualizaciones = {"calificacion": calificacion}
        db["glampings"].update_one({"_id": ObjectId(glamping_id)}, {"$set": actualizaciones})

        # Obtener el glamping actualizado
        glamping_actualizado = db["glampings"].find_one({"_id": ObjectId(glamping_id)})
        return ModeloGlamping(**convertir_objectid(glamping_actualizado))

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al actualizar la calificación: {str(e)}")


# solo para actualizar datos basicos del glamping
@ruta_glampings.put("/{glamping_id}", response_model=ModeloGlamping)
async def actualizar_glamping(
    glamping_id: str,
    nombreGlamping: str = Form(None),
    tipoGlamping: str = Form(None),
    Acepta_Mascotas: bool = Form(...),
    precioEstandar: float = Form(None),
    descuento: float = Form(None),
    descripcionGlamping: str = Form(None),
    video_youtube: str = Form(None),
    amenidadesGlobal: str = Form(...), 
):
    try:
        glamping = db["glampings"].find_one({"_id": ObjectId(glamping_id)})
        if not glamping:
            raise HTTPException(status_code=404, detail="Glamping no encontrado")

        # Procesamiento de amenidadesGlobal: convertir de cadena a lista de amenidades
        amenidades_lista = [amenidad.strip() for amenidad in amenidadesGlobal.split(",")]

        actualizaciones = {}
        if nombreGlamping:
            actualizaciones["nombreGlamping"] = nombreGlamping
        if tipoGlamping:
            actualizaciones["tipoGlamping"] = tipoGlamping
        if Acepta_Mascotas:
            actualizaciones["Acepta_Mascotas"] = Acepta_Mascotas
        if precioEstandar:
            actualizaciones["precioEstandar"] = precioEstandar
        if descuento:
            actualizaciones["descuento"] = descuento
        if descripcionGlamping:
            actualizaciones["descripcionGlamping"] = descripcionGlamping
        if video_youtube:
            actualizaciones["video_youtube"] = video_youtube
        if amenidadesGlobal:
            actualizaciones["amenidadesGlobal"] = amenidades_lista

        db["glampings"].update_one({"_id": ObjectId(glamping_id)}, {"$set": actualizaciones})
        glamping_actualizado = db["glampings"].find_one({"_id": ObjectId(glamping_id)})
        return ModeloGlamping(**convertir_objectid(glamping_actualizado))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al actualizar glamping: {str(e)}")
