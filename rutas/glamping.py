from bson import ObjectId
from fastapi import APIRouter, HTTPException, status, File, UploadFile, Form
from typing import List
from datetime import datetime
from pathlib import Path
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

UPLOAD_DIR = Path("uploads")  # Carpeta donde se guardarán las imágenes
UPLOAD_DIR.mkdir(exist_ok=True)  # Crear la carpeta si no existe


def convertir_objectid(documento):
    """Convierte ObjectId a string en un documento MongoDB."""
    if isinstance(documento, list):  # Si es una lista, aplica recursivamente
        return [convertir_objectid(doc) for doc in documento]
    elif isinstance(documento, dict):  # Si es un diccionario, convierte cada campo
        return {
            key: str(value) if isinstance(value, ObjectId) else convertir_objectid(value)
            for key, value in documento.items()
        }
    else:  # Si no es lista ni diccionario, devuelve el valor tal cual
        return documento


def preparar_glamping_para_schema(documento):
    """Ajusta el documento al esquema esperado por SchemaGlamping."""
    base_url = "https://glamperosapi.onrender.com/"  # Cambia esto a tu dominio si está en producción

    if "ubicacion" in documento:
        import json
        try:
            # Si la ubicación es una cadena JSON válida, conviértela a dict
            if isinstance(documento["ubicacion"], str):
                documento["ubicacion"] = json.loads(documento["ubicacion"])
            # Si no es un dict válido, define una ubicación predeterminada
            if not isinstance(documento["ubicacion"], dict):
                documento["ubicacion"] = {"lat": 0.0, "lng": 0.0}
        except json.JSONDecodeError:
            # En caso de error al decodificar JSON, establece un valor predeterminado
            documento["ubicacion"] = {"lat": 0.0, "lng": 0.0}

    if "imagenes" in documento and isinstance(documento["imagenes"], list):
        # Si las imágenes son rutas relativas, convierte a URLs completas
        documento["imagenes"] = [
            f"{base_url}{img}" if img.startswith("/") else img
            for img in documento["imagenes"]
        ]
    return documento


@ruta_glampings.post("/", status_code=status.HTTP_201_CREATED)
async def crear_glamping(
    nombre: str = Form(...),
    ubicacion: str = Form(...),
    precio_noche: float = Form(...),
    descripcion: str = Form(...),
    caracteristicas: str = Form(...),
    imagenes: List[UploadFile] = File(...),  # Recibir múltiples archivos
    video_youtube: str = Form(None),
):
    """
    Endpoint para crear un nuevo glamping con manejo de múltiples imágenes y datos
    """
    try:
        rutas_imagenes = []
        for imagen in imagenes:
            # Guardar cada imagen en el servidor
            ruta_archivo = UPLOAD_DIR / imagen.filename
            with open(ruta_archivo, "wb") as f:
                contenido = await imagen.read()
                f.write(contenido)

            rutas_imagenes.append(f"/uploads/{imagen.filename}")

        # Crear el documento
        nuevo_glamping = {
            "nombre": nombre,
            "ubicacion": ubicacion,
            "precio_noche": precio_noche,
            "descripcion": descripcion,
            "caracteristicas": caracteristicas.split(","),
            "imagenes": rutas_imagenes,
            "video_youtube": video_youtube,
            "calificacion": None,
            "creado": datetime.now(),
        }

        # Insertar en la base de datos
        resultado = collection_glampings.insert_one(nuevo_glamping)
        nuevo_glamping["id"] = str(resultado.inserted_id)
        return convertir_objectid(nuevo_glamping)
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

        # Convertir ObjectId a string y ajustar los datos al esquema
        glampings = [
            preparar_glamping_para_schema(convertir_objectid(glamping))
            for glamping in glampings
        ]
        return glampings
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error al obtener glampings: {str(e)}"
        )


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
        glamping = preparar_glamping_para_schema(convertir_objectid(glamping))
        return glamping
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al obtener glamping: {str(e)}")
