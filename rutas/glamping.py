from fastapi import APIRouter, HTTPException, UploadFile, Form, File, Body
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
    precioEstandarAdicional: float = Form(..., ge=0), 
    Cantidad_Huespedes: float = Form(...),
    Cantidad_Huespedes_Adicional: float = Form(..., ge=0), 
    descuento: float = Form(..., ge=0), 
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
            "precioEstandarAdicional": precioEstandarAdicional,
            "Cantidad_Huespedes": Cantidad_Huespedes,
            "Cantidad_Huespedes_Adicional":Cantidad_Huespedes_Adicional,
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
@ruta_glampings.put("/Datos/{glamping_id}", response_model=ModeloGlamping)
async def actualizar_glamping(
    glamping_id: str,
    nombreGlamping: str = Form(None),
    tipoGlamping: str = Form(None),
    Cantidad_Huespedes: float = Form(None),
    Cantidad_Huespedes_Adicional:float = Form(None),
    Acepta_Mascotas: str = Form(...), 
    precioEstandar: float = Form(None),
    precioEstandarAdicional: float = Form(None),
    descuento: float = Form(None),
    descripcionGlamping: str = Form(None),
    video_youtube: str = Form(None),
    amenidadesGlobal: str = Form(...), 
):
    try:
        glamping = db["glampings"].find_one({"_id": ObjectId(glamping_id)})
        if not glamping:
            raise HTTPException(status_code=404, detail="Glamping no encontrado")

        # Procesar el valor de Acepta_Mascotas
        if Acepta_Mascotas == "false":
            Acepta_Mascotas = False
        elif Acepta_Mascotas == "true":
            Acepta_Mascotas = True
        else:
            raise HTTPException(status_code=400, detail="Valor inválido para Acepta_Mascotas")

        # Procesamiento de amenidadesGlobal: convertir de cadena a lista de amenidades
        amenidades_lista = [amenidad.strip() for amenidad in amenidadesGlobal.split(",")]

        actualizaciones = {}
        if nombreGlamping:
            actualizaciones["nombreGlamping"] = nombreGlamping
        if tipoGlamping:
            actualizaciones["tipoGlamping"] = tipoGlamping
        if Cantidad_Huespedes:
            actualizaciones["Cantidad_Huespedes"] = Cantidad_Huespedes
        
        if Cantidad_Huespedes_Adicional is not None:
            actualizaciones["Cantidad_Huespedes_Adicional"] = Cantidad_Huespedes_Adicional
        else:
            actualizaciones["Cantidad_Huespedes_Adicional"] = 0 
        
        if Acepta_Mascotas is not None:
            actualizaciones["Acepta_Mascotas"] = Acepta_Mascotas
        if precioEstandar:
            actualizaciones["precioEstandar"] = precioEstandar
        if precioEstandarAdicional is not None:
            actualizaciones["precioEstandarAdicional"] = precioEstandarAdicional
        else:
            actualizaciones["precioEstandarAdicional"] = 0 
        
        if descuento is not None:
            actualizaciones["descuento"] = descuento
        else:
            actualizaciones["descuento"] = 0

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



# Listar glampings por propietario_id
@ruta_glampings.get("/por_propietario/{propietario_id}", response_model=List[ModeloGlamping])
async def listar_glampings_por_propietario(propietario_id: str):
    try:
        # Buscar glampings asociados al propietario_id
        glampings = list(db["glampings"].find({"propietario_id": propietario_id}))
        
        # Verificar si se encontraron glampings
        if not glampings:
            raise HTTPException(status_code=404, detail="No se encontraron glampings para este propietario")
        
        # Convertir los documentos para incluir ObjectId como string
        glampings_convertidos = [convertir_objectid(glamping) for glamping in glampings]
        return glampings_convertidos

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al listar glampings por propietario: {str(e)}")




# endpoint para actualizar solo imagenes
@ruta_glampings.put("/{glamping_id}", response_model=ModeloGlamping)
async def actualizar_imagenes_glamping(
    glamping_id: str,
    imagenes: List[UploadFile] = File(...),
):
    try:
        glamping = db["glampings"].find_one({"_id": ObjectId(glamping_id)})
        if not glamping:
            raise HTTPException(status_code=404, detail="Glamping no encontrado")

        # Subir imágenes a Google Storage y actualizar
        imagen_urls = [subir_a_google_storage(imagen) for imagen in imagenes]
        db["glampings"].update_one(
            {"_id": ObjectId(glamping_id)},
            {"$set": {"imagenes": imagen_urls}}
        )

        glamping_actualizado = db["glampings"].find_one({"_id": ObjectId(glamping_id)})
        return ModeloGlamping(**convertir_objectid(glamping_actualizado))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al actualizar imágenes del glamping: {str(e)}")




# Reorganiza el array de imágenes de un glamping
@ruta_glampings.patch("/{glamping_id}/reorganizar_imagenes", response_model=ModeloGlamping)
async def reorganizar_imagenes(
    glamping_id: str,
    nuevo_orden_imagenes: List[str] = Body(..., example=["url1", "url2", "url3"])
):
    try:
        # Buscar el glamping por ID
        glamping = db["glampings"].find_one({"_id": ObjectId(glamping_id)})
        if not glamping:
            raise HTTPException(status_code=404, detail="Glamping no encontrado")

        # Actualizar el orden de las imágenes en la base de datos
        db["glampings"].update_one(
            {"_id": ObjectId(glamping_id)},
            {"$set": {"imagenes": nuevo_orden_imagenes}}
        )

        # Obtener el glamping actualizado
        glamping_actualizado = db["glampings"].find_one({"_id": ObjectId(glamping_id)})
        return ModeloGlamping(**convertir_objectid(glamping_actualizado))

    except HTTPException as he:
        raise he
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al reorganizar las imágenes: {str(e)}")


# Eliminar una imagen de un glamping
@ruta_glampings.delete("/{glamping_id}/imagenes", status_code=204)
async def eliminar_imagenes(glamping_id: str, imagen_url: str):
    try:
        # Buscar el glamping en la base de datos
        glamping = db["glampings"].find_one({"_id": ObjectId(glamping_id)})
        if not glamping:
            raise HTTPException(status_code=404, detail="Glamping no encontrado")
        
        # Verificar si la imagen existe en el arreglo de imágenes
        if imagen_url not in glamping.get("imagenes", []):
            raise HTTPException(status_code=404, detail="Imagen no encontrada en el glamping")
        
        # Eliminar la imagen del arreglo
        db["glampings"].update_one(
            {"_id": ObjectId(glamping_id)},
            {"$pull": {"imagenes": imagen_url}}  # Utilizamos $pull para eliminar la imagen del arreglo
        )

        # Retornar una respuesta exitosa
        return {"mensaje": "Imagen eliminada correctamente del glamping"}

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al eliminar la imagen: {str(e)}")


# Agregar nuevas imágenes a un glamping existente
@ruta_glampings.post("/{glamping_id}/imagenes", response_model=ModeloGlamping)
async def agregar_imagenes_glamping(
    glamping_id: str,
    imagenes: List[UploadFile] = File(...),
):
    """
    - `glamping_id`: ID del glamping al que se agregarán las imágenes.
    - `imagenes`: Lista de imágenes para subir al glamping.
    """
    try:
        # Validar si el glamping existe
        glamping = db["glampings"].find_one({"_id": ObjectId(glamping_id)})
        if not glamping:
            raise HTTPException(status_code=404, detail="Glamping no encontrado")

        # Validar y procesar cada imagen
        imagen_urls = []
        for imagen in imagenes:
            try:
                # Subir la imagen al almacenamiento y obtener la URL
                url_imagen = subir_a_google_storage(imagen)
                imagen_urls.append(url_imagen)
            except HTTPException as e:
                raise HTTPException(
                    status_code=400,
                    detail=f"Error con la imagen '{imagen.filename}': {e.detail}",
                )

        # Actualizar las imágenes del glamping en la base de datos
        db["glampings"].update_one(
            {"_id": ObjectId(glamping_id)},
            {"$push": {"imagenes": {"$each": imagen_urls}}}
        )

        # Obtener el glamping actualizado
        glamping_actualizado = db["glampings"].find_one({"_id": ObjectId(glamping_id)})
        return ModeloGlamping(**convertir_objectid(glamping_actualizado))

    except HTTPException as he:
        # Errores específicos
        raise he
    except Exception as e:
        # Errores generales
        raise HTTPException(status_code=500, detail=f"Error interno: {str(e)}")


# Obtener las fechas reservadas de un glamping por su ID
@ruta_glampings.get("/{glamping_id}/fechasReservadas", response_model=List[str])
async def obtener_fechas_reservadas(glamping_id: str):
    try:
        # Buscar el glamping por su ID
        glamping = db["glampings"].find_one({"_id": ObjectId(glamping_id)})
        if not glamping:
            raise HTTPException(status_code=404, detail="Glamping no encontrado")
        
        # Obtener el array de fechasReservadas
        fechas_reservadas = glamping.get("fechasReservadas", [])
        
        # Devolver las fechas reservadas
        return fechas_reservadas

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al obtener fechas reservadas: {str(e)}")



# Actualizar fechas reservadas de un glamping
@ruta_glampings.patch("/{glamping_id}/fechasReservadas", response_model=ModeloGlamping)
async def actualizar_fechas_reservadas(
    glamping_id: str,
    fechas: List[str] = Body(..., embed=True)  # Array de fechas a añadir
):
    try:
        # Buscar el glamping por ID
        glamping = db["glampings"].find_one({"_id": ObjectId(glamping_id)})
        if not glamping:
            raise HTTPException(status_code=404, detail="Glamping no encontrado")

        # Añadir las nuevas fechas al array existente
        db["glampings"].update_one(
            {"_id": ObjectId(glamping_id)},
            {"$push": {"fechasReservadas": {"$each": fechas}}}
        )

        # Obtener el glamping actualizado
        glamping_actualizado = db["glampings"].find_one({"_id": ObjectId(glamping_id)})
        return ModeloGlamping(**convertir_objectid(glamping_actualizado))

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al actualizar las fechas reservadas: {str(e)}")


# Eliminar fechas reservadas de un glamping
@ruta_glampings.patch("/{glamping_id}/eliminar_fechas", response_model=ModeloGlamping)
async def eliminar_fechas_reservadas(
    glamping_id: str,
    fechas_a_eliminar: List[str] = Body(..., embed=True)  # Array de fechas a eliminar
):
    try:
        # Buscar el glamping por ID
        glamping = db["glampings"].find_one({"_id": ObjectId(glamping_id)})
        if not glamping:
            raise HTTPException(status_code=404, detail="Glamping no encontrado")

        # Eliminar las fechas reservadas que estén en el array `fechas_a_eliminar`
        db["glampings"].update_one(
            {"_id": ObjectId(glamping_id)},
            {"$pullAll": {"fechasReservadas": fechas_a_eliminar}}  # Elimina las fechas de la lista
        )

        # Obtener el glamping actualizado
        glamping_actualizado = db["glampings"].find_one({"_id": ObjectId(glamping_id)})
        return ModeloGlamping(**convertir_objectid(glamping_actualizado))

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al eliminar las fechas reservadas: {str(e)}")
