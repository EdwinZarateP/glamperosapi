from fastapi import APIRouter, HTTPException, Depends, status, UploadFile, File, Body
from pymongo import MongoClient
from bson import ObjectId
from google.cloud import storage
import uuid
from pytz import timezone
from io import BytesIO
from PIL import Image
from datetime import datetime
from typing import List
from pydantic import BaseModel
import os

# Configuración de la base de datos
MONGO_URI = os.environ.get("MONGO_URI", "mongodb://localhost:27017")
ConexionMongo = MongoClient(MONGO_URI)
base_datos = ConexionMongo["glamperos"]

# Configuración de FastAPI
ruta_usuario = APIRouter(
    prefix="/usuarios",
    tags=["Usuarios"],
    responses={status.HTTP_404_NOT_FOUND: {"message": "No encontrado"}},
)

BUCKET_NAME = "glamperos-imagenes"


# Modelos de datos
class Usuario(BaseModel):
    nombre: str
    email: str
    telefono: str
    clave: str
    glampings: List[str] = []  # Lista de IDs de glampings asociados
    foto: str = None  # Campo opcional para la foto
    banco: str = None  # Campo opcional para la banco
    numeroCuenta: str = None  # Campo opcional para numeroCuenta
    tipoCuenta: str = None  # Campo opcional para tipoCuenta 
    certificadoBancario: str = None  # Campo opcional para la foto


def modelo_usuario(usuario) -> dict:
    return {
        "id": str(usuario["_id"]),
        "nombre": usuario["nombre"],
        "email": usuario["email"],
        "telefono": usuario["telefono"],
        "glampings": usuario.get("glampings", []),
        "foto": usuario["foto"],
        "banco": usuario["banco"],
        "numeroCuenta": usuario["numeroCuenta"],
        "tipoCuenta": usuario["tipoCuenta"],
        "certificadoBancario": usuario["certificadoBancario"],
    }


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


# Rutas de la API

# Definir la zona horaria de Colombia
ZONA_HORARIA_COLOMBIA = timezone("America/Bogota")

# Crear usuario
@ruta_usuario.post("/", response_model=dict)
async def crear_usuario(usuario: Usuario):
    # Buscar si el usuario ya existe
    usuario_existente = base_datos.usuarios.find_one({"email": usuario.email})
    
    if usuario_existente:
        # Si el usuario existe, devuelves sus datos
        return {
            "mensaje": "Correo ya registrado",
            "usuario": {
                "_id": str(usuario_existente["_id"]),
                "nombre": usuario_existente["nombre"],
                "email": usuario_existente["email"],
                "telefono": usuario_existente["telefono"],                
            }
        }

    # Crear un nuevo usuario si no existe
    usuario.clave = "autenticacionGoogle"  # Se omite el uso de clave de acceso aquí
    # Convertir la fecha de creación a la hora de Colombia (UTC-5)
    fecha_creacion_colombia = datetime.now().astimezone(ZONA_HORARIA_COLOMBIA)

    nuevo_usuario = {
        "nombre": usuario.nombre,
        "email": usuario.email,
        "telefono": usuario.telefono,
        "clave": usuario.clave,
        "glampings": [],
        "fecha_registro": fecha_creacion_colombia, 
        "foto": usuario.foto,  # Campo opcional
        "banco": usuario.banco, # Campo opcional
        "numeroCuenta": usuario.numeroCuenta, # Campo opcional
        "tipoCuenta": usuario.tipoCuenta, # Campo opcional  
        "certificadoBancario": usuario.certificadoBancario # Campo opcional                
    }
    
    # Insertar el nuevo usuario en la base de datos
    result = base_datos.usuarios.insert_one(nuevo_usuario)
    
    # Recuperar el ID del usuario recién creado
    nuevo_usuario["_id"] = str(result.inserted_id)
    
    # Respuesta con el ID del usuario recién creado
    return {"mensaje": "Usuario creado exitosamente", "usuario": nuevo_usuario}


# Registro de usuario a través de Google (sin necesidad de clave)
@ruta_usuario.post("/google", response_model=dict)
async def registro_google(email: str, nombre: str):
    usuario_existente = base_datos.usuarios.find_one({"email": email})
    if usuario_existente:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El correo ya está registrado"
        )
    
    nuevo_usuario = {
        "nombre": nombre,
        "email": email,
        "telefono": "",
        "clave": "autenticacionGoogle",  
        "glampings": [],       
    }
    result = base_datos.usuarios.insert_one(nuevo_usuario)
    return modelo_usuario(base_datos.usuarios.find_one({"_id": result.inserted_id}))


# Obtener usuario por ID
@ruta_usuario.get("/{usuario_id}", response_model=dict)
async def obtener_usuario(usuario_id: str):
    usuario = base_datos.usuarios.find_one({"_id": ObjectId(usuario_id)})
    if usuario is None:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    return modelo_usuario(usuario)


# Actualizar foto de usuario
@ruta_usuario.put("/{email}/foto", response_model=dict)
async def actualizar_foto(
    email: str,  # Usamos el email para identificar al usuario
    foto: UploadFile = File(...),  # La nueva foto debe ser enviada como archivo
):
    try:
        # Buscar al usuario por su email
        usuario = base_datos.usuarios.find_one({"email": email})
        if not usuario:
            raise HTTPException(status_code=404, detail="Usuario no encontrado")

        # Subir la foto al almacenamiento (por ejemplo, Google Cloud Storage o S3)
        url_foto = subir_a_google_storage(foto, carpeta="usuarios")

        # Actualizar la URL de la foto en la base de datos
        result = base_datos.usuarios.update_one(
            {"email": email},
            {"$set": {"foto": url_foto}}
        )

        if result.modified_count == 0:
            raise HTTPException(status_code=400, detail="No se pudo actualizar la foto")

        return {"message": "Foto actualizada correctamente", "url_foto": url_foto}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al actualizar la foto: {str(e)}")


# Actualizar teléfono de usuario
@ruta_usuario.put("/{email}/telefono", response_model=dict)
async def actualizar_telefono(
    email: str,  # Usamos el email para identificar al usuario
    telefono: str = Body(..., embed=True),  # El nuevo teléfono debe ser enviado en el cuerpo
):
    try:
        # Buscar al usuario por su email
        usuario = base_datos.usuarios.find_one({"email": email})
        if not usuario:
            raise HTTPException(status_code=404, detail="Usuario no encontrado")

        # Actualizar el teléfono
        result = base_datos.usuarios.update_one(
            {"email": email},
            {"$set": {"telefono": telefono}}
        )

        if result.modified_count == 0:
            raise HTTPException(status_code=400, detail="No se pudo actualizar el teléfono")

        return {"message": "Teléfono actualizado correctamente"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al actualizar el teléfono: {str(e)}")


# Eliminar usuario
@ruta_usuario.delete("/{usuario_id}", response_model=dict)
async def eliminar_usuario(usuario_id: str):
    result = base_datos.usuarios.delete_one({"_id": ObjectId(usuario_id)})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    return {"mensaje": "Usuario eliminado"}


# Desvincular glamping de usuario
@ruta_usuario.delete("/{usuario_id}/glampings/{glamping_id}", response_model=dict)
async def desvincular_glamping(usuario_id: str, glamping_id: str):
    result = base_datos.usuarios.update_one(
        {"_id": ObjectId(usuario_id)},
        {"$pull": {"glampings": glamping_id}}
    )
    if result.modified_count == 0:
        raise HTTPException(status_code=404, detail="Usuario o glamping no encontrado")
    return {"mensaje": "Glamping desvinculado exitosamente"}


# Buscar usuario por email
@ruta_usuario.get("/", response_model=dict)
async def buscar_usuario(email: str):
    """Buscar un usuario por su correo electrónico."""
    if not email:
        raise HTTPException(status_code=400, detail="Se requiere un correo electrónico válido")
    
    usuario = base_datos.usuarios.find_one({"email": email})
    if not usuario:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    return modelo_usuario(usuario)


@ruta_usuario.put("/{usuario_id}/banco", response_model=dict)
async def actualizar_datos_bancarios(
    usuario_id: str,
    banco: str = Body(None, embed=True),
    numeroCuenta: str = Body(None, embed=True),
    tipoCuenta: str = Body(None, embed=True),
    certificadoBancario: UploadFile = File(None),
):
    try:
        # Buscar al usuario por su ID
        usuario = base_datos.usuarios.find_one({"_id": ObjectId(usuario_id)})
        if not usuario:
            raise HTTPException(status_code=404, detail="Usuario no encontrado")
        
        actualizaciones = {}
        
         # Actualizar número de cuenta si se proporciona
        if banco:
            actualizaciones["banco"] = banco

        # Actualizar número de cuenta si se proporciona
        if numeroCuenta:
            actualizaciones["numeroCuenta"] = numeroCuenta
        
        # Actualizar tipo de cuenta si se proporciona
        if tipoCuenta:
            actualizaciones["tipoCuenta"] = tipoCuenta
        
        # Subir el certificado bancario si se proporciona
        if certificadoBancario:
            url_certificado = subir_a_google_storage(certificadoBancario, carpeta="certificadosBancarios")
            actualizaciones["certificadoBancario"] = url_certificado
        
        # Si no hay cambios, no hacer actualización
        if not actualizaciones:
            raise HTTPException(status_code=400, detail="No se proporcionaron datos para actualizar")
        
        # Aplicar la actualización en la base de datos
        result = base_datos.usuarios.update_one(
            {"_id": ObjectId(usuario_id)},
            {"$set": actualizaciones}
        )
        
        if result.modified_count == 0:
            raise HTTPException(status_code=400, detail="No se pudo actualizar los datos bancarios")
        
        return {"message": "Datos bancarios actualizados correctamente", **actualizaciones}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al actualizar los datos bancarios: {str(e)}")
