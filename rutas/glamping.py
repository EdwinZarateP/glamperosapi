from fastapi import APIRouter, HTTPException, UploadFile, Form, File, Body, Query
from geopy.distance import geodesic
from datetime import timedelta
from google.cloud import storage
from pymongo import MongoClient
from bson.objectid import ObjectId
from typing import List, Optional
from datetime import datetime
from pytz import timezone
from PIL import Image
from pydantic import BaseModel
from io import BytesIO
import os
import base64
import uuid
import json
from bd.models.glamping import ModeloGlamping
from PIL import Image, ExifTags
from utils.deepseek_utils import extraer_intencion, generar_respuesta  # ✅ importa tu util nuevo

class PaginaGlampings(BaseModel):
    glampings: List[ModeloGlamping]
    total: int

BUCKET_NAME = "glamperos-imagenes"

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

def actualizar_union_fechas(glamping_id: str):
    glamping = db["glampings"].find_one({"_id": ObjectId(glamping_id)})
    manual = set(glamping.get("fechasReservadasManual", []))
    airbnb = set(glamping.get("fechasReservadasAirbnb", []))
    booking = set(glamping.get("fechasReservadasBooking", []))
    union = list(manual.union(airbnb).union(booking))
    db["glampings"].update_one(
        {"_id": ObjectId(glamping_id)},
        {"$set": {"fechasReservadas": union}}
    )


# Crear el router para glampings
ruta_glampings = APIRouter(
    prefix="/glampings",
    tags=["Glampings"],
    responses={404: {"description": "No encontrado"}},
)


def corregir_orientacion(imagen: Image.Image) -> Image.Image:
    """Corrige la orientación de la imagen según los metadatos EXIF."""
    try:
        # Obtener la clave de orientación en ExifTags
        for orientation_tag in ExifTags.TAGS.keys():
            if ExifTags.TAGS[orientation_tag] == 'Orientation':
                break

        exif = imagen._getexif()
        if exif:
            orientation = exif.get(orientation_tag, None)

            # Rotar la imagen según la orientación EXIF
            if orientation == 3:
                imagen = imagen.rotate(180, expand=True)
            elif orientation == 6:
                imagen = imagen.rotate(270, expand=True)
            elif orientation == 8:
                imagen = imagen.rotate(90, expand=True)
    except Exception:
        pass  # Si la imagen no tiene EXIF o hay un error, se usa la imagen tal cual.

    return imagen

def optimizar_imagen(archivo: UploadFile, formato: str = "WEBP", max_width: int = 1200, max_height: int = 800) -> BytesIO:
    """Corrige la orientación, redimensiona y convierte la imagen a WebP."""
    try:
        imagen = Image.open(archivo.file)
        
        # 1. Corregir la orientación EXIF antes de redimensionar
        imagen = corregir_orientacion(imagen)
        
        # 2. Redimensionar y convertir
        imagen.thumbnail((max_width, max_height), Image.Resampling.LANCZOS)
        
        # 3. Guardar en un buffer
        buffer = BytesIO()
        imagen.save(buffer, format=formato, optimize=True, quality=75)
        buffer.seek(0)
        return buffer
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error al optimizar la imagen: {str(e)}")


# Función para subir archivos optimizados al bucket de Google Cloud Storage

def subir_a_google_storage(archivo: UploadFile, carpeta: str = "glampings") -> str:
    """Sube la imagen corregida y optimizada a Google Cloud Storage."""
    try:
        cliente = storage.Client()
        bucket = cliente.bucket(BUCKET_NAME)

        # Optimizar y corregir la imagen antes de subirla
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


# Definir la zona horaria de Colombia
ZONA_HORARIA_COLOMBIA = timezone("America/Bogota")

# Crear un nuevo glamping con validaciones por cada paso
@ruta_glampings.post("/", status_code=201, response_model=ModeloGlamping)
async def crear_glamping(
    habilitado: Optional[bool] = Form(True),
    nombreGlamping: str = Form(...),
    tipoGlamping: str = Form(...),
    Acepta_Mascotas: bool = Form(...),
    ubicacion: str = Form(...),
    direccion: str = Form(...),
    precioEstandar: float = Form(...),
    precioEstandarAdicional: float = Form(..., ge=0),
    diasCancelacion: float = Form(..., ge=0), 
    Cantidad_Huespedes: float = Form(...),
    Cantidad_Huespedes_Adicional: float = Form(..., ge=0), 
    minimoNoches: float = Form(..., ge=0),
    descuento: float = Form(..., ge=0), 
    descripcionGlamping: str = Form(...),
    amenidadesGlobal: str = Form(...),
    ciudad_departamento: str = Form(...),
    imagenes: List[UploadFile] = File(...),
    video_youtube: str = Form(None),
    fechasReservadas: Optional[str] = Form(None),
    propietario_id: str = Form(...),
    urlIcal: Optional[str] = Form(None),
    urlIcalBooking: Optional[str] = Form(None)
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

        # Convertir la fecha de creación a la hora de Colombia (UTC-5)
        fecha_creacion_colombia = datetime.now().astimezone(ZONA_HORARIA_COLOMBIA)

        # Crear el glamping en la base de datos
        nuevo_glamping = {
            "habilitado":habilitado,
            "nombreGlamping": nombreGlamping,
            "tipoGlamping": tipoGlamping,
            "Acepta_Mascotas": Acepta_Mascotas,
            "ubicacion": ubicacion,
            "direccion": direccion,
            "precioEstandar": precioEstandar,
            "precioEstandarAdicional": precioEstandarAdicional,
            "diasCancelacion": diasCancelacion,
            "Cantidad_Huespedes": Cantidad_Huespedes,
            "Cantidad_Huespedes_Adicional":Cantidad_Huespedes_Adicional,
            "minimoNoches":minimoNoches,
            "descuento": descuento,
            "descripcionGlamping": descripcionGlamping,
            "amenidadesGlobal": amenidades_lista,
            "ciudad_departamento": ciudad_departamento,
            "imagenes": imagen_urls,
            "video_youtube": video_youtube,
            "calificacion": 5,
            "fechasReservadas": fechas_reservadas_lista,
            "creado": fecha_creacion_colombia,
            "propietario_id": propietario_id,
            "urlIcal": urlIcal,
            "urlIcalBooking": urlIcalBooking
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


@ruta_glampings.get("/glampingfiltrados", response_model=List[ModeloGlamping])
async def glamping_filtrados(
    lat: Optional[float] = Query(None),
    lng: Optional[float] = Query(None),
    tipoGlamping: Optional[str] = Query(None),
    precioMin: Optional[float] = Query(None),
    precioMax: Optional[float] = Query(None),
    totalHuespedes: Optional[float] = Query(None),
    fechaInicio: Optional[str] = Query(None),
    fechaFin: Optional[str] = Query(None),
    amenidades: Optional[List[str]] = Query(None),
    aceptaMascotas: Optional[bool] = Query(None),
    page: int = Query(1, ge=1),
    limit: int = Query(24, ge=1),
    distanciaMax: float = Query(150.0),
):
    try:
        filtro: dict = {"habilitado": True}

        if tipoGlamping:
            filtro["tipoGlamping"] = tipoGlamping
        
        if aceptaMascotas is not None:
            filtro["Acepta_Mascotas"] = aceptaMascotas

        if precioMin is not None or precioMax is not None:
            precio_filter = {}
            if precioMin is not None:
                precio_filter["$gte"] = precioMin
            if precioMax is not None:
                precio_filter["$lte"] = precioMax
            filtro["precioEstandar"] = precio_filter

        if fechaInicio and fechaFin:
            inicio = datetime.strptime(fechaInicio, "%Y-%m-%d")
            fin = datetime.strptime(fechaFin, "%Y-%m-%d")
            dias = [
                (inicio + timedelta(days=i)).strftime("%Y-%m-%d")
                for i in range((fin - inicio).days + 1)
            ]
            filtro["fechasReservadas"] = {"$not": {"$elemMatch": {"$in": dias}}}

        if amenidades:
            filtro["amenidadesGlobal"] = {"$all": amenidades}

        # Consulta sin paginar aún
        cursor = db["glampings"].find(filtro).sort([
            ("calificacion", -1),
            ("nombreGlamping", 1),
            ("_id", 1),
        ])
        resultados = list(cursor)

        # Filtrar por capacidad total de huéspedes
        if totalHuespedes is not None:
            resultados = [
                gl for gl in resultados
                if (
                    isinstance(gl.get("Cantidad_Huespedes"), (int, float, str)) and
                    isinstance(gl.get("Cantidad_Huespedes_Adicional"), (int, float, str)) and
                    (
                        float(gl.get("Cantidad_Huespedes", 0)) +
                        float(gl.get("Cantidad_Huespedes_Adicional", 0))
                    ) >= totalHuespedes
                )
            ]

        # Si lat y lng fueron pasados, filtrar por distancia
                
        if lat is not None and lng is not None:
            coordenadas_usuario = (lat, lng)
            resultados_con_distancia = []

            for gl in resultados:
                if "ubicacion" in gl:
                    try:
                        ubic = gl["ubicacion"]
                        if isinstance(ubic, str):
                            ubic = json.loads(ubic)
                        distancia = geodesic(coordenadas_usuario, (ubic["lat"], ubic["lng"])).km
                        if distancia <= distanciaMax:
                            gl["distancia"] = distancia
                            resultados_con_distancia.append(gl)
                    except Exception:
                        continue  # Ignorar errores por coordenadas mal formateadas

            resultados = sorted(resultados_con_distancia, key=lambda x: x["distancia"])

        # Paginación
        inicio = (page - 1) * limit
        fin = inicio + limit
        resultados_paginados = resultados[inicio:fin]

        return [convertir_objectid(g) for g in resultados_paginados]

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al filtrar glampings: {e}")



@ruta_glampings.get(
    "/glampingfiltrados2",
    response_model=PaginaGlampings
)
async def glamping_filtrados2(
    lat: Optional[float] = Query(None),
    lng: Optional[float] = Query(None),
    tipoGlamping: Optional[str] = Query(None),
    precioMin: Optional[float] = Query(None),
    precioMax: Optional[float] = Query(None),
    totalHuespedes: Optional[float] = Query(None),
    fechaInicio: Optional[str] = Query(None),
    fechaFin: Optional[str] = Query(None),
    amenidades: Optional[List[str]] = Query(None),
    aceptaMascotas: Optional[bool] = Query(None),
    page: int = Query(1, ge=1),
    limit: int = Query(24, ge=1),
    distanciaMax: float = Query(150.0),
):
    try:
        # 1) Construir el filtro base con “habilitado”
        filtro: dict = {"habilitado": True}

        if tipoGlamping:
            filtro["tipoGlamping"] = tipoGlamping

        if aceptaMascotas is not None:
            filtro["Acepta_Mascotas"] = aceptaMascotas

        if precioMin is not None or precioMax is not None:
            precio_filter: dict = {}
            if precioMin is not None:
                precio_filter["$gte"] = precioMin
            if precioMax is not None:
                precio_filter["$lte"] = precioMax
            filtro["precioEstandar"] = precio_filter

        if fechaInicio and fechaFin:
            inicio_dt = datetime.strptime(fechaInicio, "%Y-%m-%d")
            fin_dt = datetime.strptime(fechaFin, "%Y-%m-%d")
            dias_rango = [
                (inicio_dt + timedelta(days=i)).strftime("%Y-%m-%d")
                for i in range((fin_dt - inicio_dt).days + 1)
            ]
            # Excluir fechas reservadas que coincidan con el rango
            filtro["fechasReservadas"] = {"$not": {"$elemMatch": {"$in": dias_rango}}}

        if amenidades:
            filtro["amenidadesGlobal"] = {"$all": amenidades}

        # 2) Ejecución de la consulta SIN paginar todavía
        cursor = db["glampings"].find(filtro).sort([
            ("calificacion", -1),
            ("nombreGlamping", 1),
            ("_id", 1),
        ])
        resultados = list(cursor)

        # 3) Filtrar por capacidad total de huéspedes (si aplica)
        if totalHuespedes is not None:
            resultados = [
                gl for gl in resultados
                if (
                    isinstance(gl.get("Cantidad_Huespedes"), (int, float, str))
                    and isinstance(gl.get("Cantidad_Huespedes_Adicional"), (int, float, str))
                    and (
                        float(gl.get("Cantidad_Huespedes", 0)) +
                        float(gl.get("Cantidad_Huespedes_Adicional", 0))
                    ) >= totalHuespedes
                )
            ]

        # 4) Filtrar por distancia si llegan lat y lng
        if lat is not None and lng is not None:
            coordenadas_usuario = (lat, lng)
            resultados_con_distancia = []
            for gl in resultados:
                if "ubicacion" in gl:
                    try:
                        ubic = gl["ubicacion"]
                        if isinstance(ubic, str):
                            ubic = json.loads(ubic)
                        distancia = geodesic(
                            coordenadas_usuario,
                            (ubic["lat"], ubic["lng"])
                        ).km
                        if distancia <= distanciaMax:
                            gl["distancia"] = distancia
                            resultados_con_distancia.append(gl)
                    except Exception:
                        continue
            # Ordenar por distancia ascendente
            resultados = sorted(resultados_con_distancia, key=lambda x: x["distancia"])

        # 5) Calcular el total FINAL (después de todos los filtros)
        total = len(resultados)

        # 6) Aplicar paginación (slice)
        inicio_idx = (page - 1) * limit
        fin_idx = inicio_idx + limit
        resultados_paginados = resultados[inicio_idx:fin_idx]

        # 7) Devolver el diccionario con “glampings” y “total”
        return {
            "glampings": [convertir_objectid(g) for g in resultados_paginados],
            "total": total
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al filtrar glampings: {e}")




# -------------------Obtener todos los glampings -------------------
@ruta_glampings.get("/", response_model=List[ModeloGlamping])
async def obtener_glampings(page: int = 1, limit: int = 24):
    """
    Obtiene una lista de glampings con paginación.
    
    - `page`: Número de página, por defecto 1.
    - `limit`: Tamaño del lote, por defecto 24.
    """
    try:
        if page < 1 or limit < 1:
            raise HTTPException(status_code=400, detail="Los parámetros `page` y `limit` deben ser mayores a 0")
        
        # Calcular los índices de paginación
        skip = (page - 1) * limit
        
        # Obtener los glampings con límites y saltos
        glampings = list(db["glampings"].find().sort([
          ("calificacion", -1),  # Primero por calificación descendente
          ("nombreGlamping", 1),  # Luego por nombre alfabético (A-Z)
          ("_id", 1)  # Finalmente por ID ascendente
        ]).skip(skip).limit(limit))

        glampings_convertidos = [convertir_objectid(glamping) for glamping in glampings]
        return glampings_convertidos
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al obtener glampings: {str(e)}")


# Obtener todos los glampings SIN PAGINACIÓN (PARA API DEEP SEEK)
@ruta_glampings.get("/todos/", response_model=List[ModeloGlamping])
async def obtener_todos_glampings():
    """
    Obtiene la lista completa de glampings sin paginación.
    """
    try:
        # Obtener todos los glampings sin límites
        glampings = list(db["glampings"].find())
        
        # Convertir los ObjectId y procesar ubicación
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
    Cantidad_Huespedes: str = Form(None),
    Cantidad_Huespedes_Adicional:str = Form(None),
    minimoNoches:str = Form(None),
    Acepta_Mascotas: str = Form(...), 
    precioEstandar: str = Form(None),
    precioEstandarAdicional: str = Form(None),
    diasCancelacion: str = Form(None),    
    descuento: str = Form(None),
    descripcionGlamping: str = Form(None),
    video_youtube: str = Form(None),
    urlIcal: str = Form(None),
    urlIcalBooking: str = Form(None),
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
        if minimoNoches:
            actualizaciones["minimoNoches"] = minimoNoches        
        if Acepta_Mascotas is not None:
            actualizaciones["Acepta_Mascotas"] = Acepta_Mascotas
        if precioEstandar:
            actualizaciones["precioEstandar"] = precioEstandar
        if precioEstandarAdicional is not None:
            actualizaciones["precioEstandarAdicional"] = precioEstandarAdicional
        else:
            actualizaciones["precioEstandarAdicional"] = 0 
        
        if diasCancelacion is not None:
            actualizaciones["diasCancelacion"] = diasCancelacion
        else:
            actualizaciones["diasCancelacion"] = 0         

        if descuento is not None:
            actualizaciones["descuento"] = descuento
        else:
            actualizaciones["descuento"] = 0

        if descripcionGlamping:
            actualizaciones["descripcionGlamping"] = descripcionGlamping
        if video_youtube:
            actualizaciones["video_youtube"] = video_youtube
        if urlIcal:
            actualizaciones["urlIcal"] = urlIcal
        if urlIcalBooking:
            actualizaciones["urlIcalBooking"] = urlIcalBooking
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
    - `imagenes`: Lista de imágenes a subir.
    """
    try:
        # Validar si el glamping existe
        glamping = db["glampings"].find_one({"_id": ObjectId(glamping_id)})
        if not glamping:
            raise HTTPException(status_code=404, detail="Glamping no encontrado")

        # Validar y corregir las imágenes antes de subirlas
        imagen_urls = []
        for imagen in imagenes:
            try:
                url_imagen = subir_a_google_storage(imagen)
                imagen_urls.append(url_imagen)
            except HTTPException as e:
                raise HTTPException(status_code=400, detail=f"Error con la imagen '{imagen.filename}': {e.detail}")

        # Actualizar las imágenes en la base de datos
        db["glampings"].update_one(
            {"_id": ObjectId(glamping_id)},
            {"$push": {"imagenes": {"$each": imagen_urls}}}
        )

        # Obtener el glamping actualizado
        glamping_actualizado = db["glampings"].find_one({"_id": ObjectId(glamping_id)})
        return ModeloGlamping(**convertir_objectid(glamping_actualizado))

    except HTTPException as he:
        raise he
    except Exception as e:
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
@ruta_glampings.patch("/{glamping_id}/fechasReservadasManual", response_model=ModeloGlamping)
async def actualizar_fechas_reservadas_manual(
    glamping_id: str,
    fechas: List[str] = Body(..., embed=True)
):
    try:
        glamping = db["glampings"].find_one({"_id": ObjectId(glamping_id)})
        if not glamping:
            raise HTTPException(status_code=404, detail="Glamping no encontrado")

        db["glampings"].update_one(
            {"_id": ObjectId(glamping_id)},
            {"$addToSet": {"fechasReservadasManual": {"$each": fechas}}}
        )

        actualizar_union_fechas(glamping_id)

        glamping_actualizado = db["glampings"].find_one({"_id": ObjectId(glamping_id)})
        return ModeloGlamping(**convertir_objectid(glamping_actualizado))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al actualizar fechas manuales: {str(e)}")


# eliminar fechas manuales
@ruta_glampings.patch("/{glamping_id}/eliminar_fechas_manual", response_model=ModeloGlamping)
async def eliminar_fechas_reservadas_manual(
    glamping_id: str,
    fechas_a_eliminar: List[str] = Body(..., embed=True)
):
    try:
        glamping = db["glampings"].find_one({"_id": ObjectId(glamping_id)})
        if not glamping:
            raise HTTPException(status_code=404, detail="Glamping no encontrado")

        db["glampings"].update_one(
            {"_id": ObjectId(glamping_id)},
            {"$pullAll": {"fechasReservadasManual": fechas_a_eliminar}}
        )

        actualizar_union_fechas(glamping_id)

        glamping_actualizado = db["glampings"].find_one({"_id": ObjectId(glamping_id)})
        return ModeloGlamping(**convertir_objectid(glamping_actualizado))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"🔥 Error al eliminar fechas manuales: {str(e)}")

@ruta_glampings.put("/{glamping_id}/rotate_image")
async def rotar_imagen(
    glamping_id: str,
    imagenUrl: str = Body(...),
    grados: int = Body(...)
):
    """
    Gira la imagen del Glamping en GCS pero usando un NUEVO nombre de archivo.
    Luego, reemplaza la URL antigua en la BD por la nueva.
    """
    try:
        # 1. Verificar si el glamping existe
        glamping = db["glampings"].find_one({"_id": ObjectId(glamping_id)})
        if not glamping:
            raise HTTPException(status_code=404, detail="Glamping no encontrado")

        # 2. Verificar si la imagenUrl está en la lista de imágenes del glamping
        if imagenUrl not in glamping.get("imagenes", []):
            raise HTTPException(status_code=400, detail="La imagen no pertenece a este glamping.")

        # 3. Obtener el nombre del archivo (antiguo) en GCS
        archivo_nombre_anterior = imagenUrl.split(f"https://storage.googleapis.com/{BUCKET_NAME}/")[-1]

        # 4. Descargar la imagen desde GCS
        cliente = storage.Client()
        bucket = cliente.bucket(BUCKET_NAME)
        blob_anterior = bucket.blob(archivo_nombre_anterior)
        imagen_bytes = blob_anterior.download_as_bytes()

        # 5. Rotar la imagen en memoria
        imagen_pil = Image.open(BytesIO(imagen_bytes))
        imagen_pil = imagen_pil.rotate(grados, expand=True)

        # 6. Crear un nuevo nombre para la imagen rotada
        nombre_archivo_nuevo = f"glampings/{uuid.uuid4().hex}.webp"

        # 7. Subir la imagen rotada con un nombre distinto
        blob_nuevo = bucket.blob(nombre_archivo_nuevo)
        buffer = BytesIO()
        imagen_pil.save(buffer, format="WEBP", optimize=True, quality=75)
        buffer.seek(0)
        blob_nuevo.upload_from_file(buffer, content_type="image/webp")

        nueva_url = f"https://storage.googleapis.com/{BUCKET_NAME}/{nombre_archivo_nuevo}"

        # 8. Actualizar la referencia a la imagen en MongoDB
        #    Reemplazamos la url antigua (imagenUrl) por la nueva (nueva_url)
        db["glampings"].update_one(
            {"_id": ObjectId(glamping_id), "imagenes": imagenUrl},
            {"$set": {"imagenes.$": nueva_url}}
        )

        # Opcional: Eliminar el archivo anterior de GCS si ya no lo quieres
        # blob_anterior.delete()

        # 9. Devolver la nueva URL o el glamping completo
        glamping_actualizado = db["glampings"].find_one({"_id": ObjectId(glamping_id)})
        return {
            "mensaje": "Imagen rotada correctamente y subida con nuevo nombre",
            "nueva_url": nueva_url,
            "imagenes": glamping_actualizado.get("imagenes", [])
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al rotar la imagen: {str(e)}")


# ⏬⏬⏬ NUEVO ENDPOINT ⏬⏬⏬
from math import radians, cos, sin, asin, sqrt

def haversine(lat1, lon1, lat2, lon2):
    """Distancia en km entre dos puntos GPS."""
    dlat, dlon = radians(lat2 - lat1), radians(lon2 - lon1)
    a = sin(dlat/2)**2 + cos(radians(lat1))*cos(radians(lat2))*sin(dlon/2)**2
    return 6371 * 2 * asin(sqrt(a))


@ruta_glampings.post("/preguntar")
def preguntar(json_input: dict):
    pregunta = json_input.get("pregunta", "")
    filtros  = extraer_intencion(pregunta)

    # ——> POST-PROCESSING DE AMENIDADES:
    # Si el usuario no dijo "con X" ni "sin Y" en su pregunta,
    # forzamos amenidades = []
    if not any(token in pregunta.lower() for token in (" con ", " sin ")):
        filtros["amenidades"] = []

    # 1) Armar query base
    query = {"habilitado": True}

    # 2) Filtrar por amenidades SOLO si hay alguna
    if filtros["amenidades"]:
        query["amenidadesGlobal"] = {"$in": filtros["amenidades"]}

    # 3) Filtrar por texto de ubicación
    if filtros.get("ubicacion"):
        regex = {"$regex": filtros["ubicacion"], "$options": "i"}
        query["$or"] = [
            {"ciudad_departamento": regex},
            {"direccion":           regex}
        ]

    # 4) Ejecutar consulta inicial
    raw = list(db["glampings"].find(query))

    # 5) Si el parser devolvió coords, filtrar por distancia
    if filtros.get("ubicacion_coords"):
        ux, uy = filtros["ubicacion_coords"]
        radio  = filtros.get("radio_km", 50)
        raw = [
            g for g in raw
            if ("ubicacion" in g
                and haversine(ux, uy,
                              g["ubicacion"]["lat"],
                              g["ubicacion"]["lng"]) <= radio)
        ]

    # 6) Generar texto natural
    respuesta = generar_respuesta(pregunta, json.dumps(raw, default=str))

    return {
        "filtros":    filtros,
        "resultados": raw,
        "respuesta":  respuesta
    }