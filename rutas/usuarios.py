from fastapi import APIRouter, HTTPException, Depends, status, UploadFile, File, Body
from pymongo import MongoClient
from bson import ObjectId
from google.cloud import storage
import uuid
from pytz import timezone
from io import BytesIO
from PIL import Image
from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel
from bson.errors import InvalidId
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
class UsuarioGoogle(BaseModel):
    nombre: str
    email: str
    aceptaTratamientoDatos: bool

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
    tipoDocumento: str = None  # Campo opcional para la foto
    numeroDocumento: str = None  # Campo opcional para la foto
    nombreTitular: str = None
    rol: Optional[str] = "usuario"


class GlampingResumen(BaseModel):
    id: str
    nombreGlamping: str
    ciudad_departamento: str

class UsuarioConGlampings(BaseModel):
    nombre: str
    email: str
    telefono: str
    glampings: List[GlampingResumen] = []

def modelo_usuario(usuario) -> dict:
    return {
        "id": str(usuario["_id"]),
        "nombre": usuario.get("nombre", ""),
        "email": usuario.get("email", ""),
        "telefono": usuario.get("telefono", ""),
        "glampings": usuario.get("glampings", []),
        "foto": usuario.get("foto", ""),
        "banco": usuario.get("banco", ""),
        "numeroCuenta": usuario.get("numeroCuenta", ""),
        "tipoCuenta": usuario.get("tipoCuenta", ""),
        "tipoDocumento": usuario.get("tipoDocumento", ""),
        "numeroDocumento": usuario.get("numeroDocumento", ""),
        "nombreTitular": usuario.get("nombreTitular", ""),
        "aceptaTratamientoDatos": usuario.get("aceptaTratamientoDatos", False),
        "rol": usuario.get("rol", "usuario"),
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
                "rol": "usuario",  # Valor por defecto
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
        "tipoDocumento": usuario.tipoDocumento, # Campo opcional 
        "numeroDocumento": usuario.numeroDocumento, # Campo opcional 
        "nombreTitular": usuario.nombreTitular                
    }
    
    # Insertar el nuevo usuario en la base de datos
    result = base_datos.usuarios.insert_one(nuevo_usuario)
    
    # Recuperar el ID del usuario recién creado
    nuevo_usuario["_id"] = str(result.inserted_id)
    
    # Respuesta con el ID del usuario recién creado
    return {"mensaje": "Usuario creado exitosamente", "usuario": nuevo_usuario}


# Registro de usuario a través de Google (sin necesidad de clave)
@ruta_usuario.post("/google", response_model=dict)
async def registro_google(usuario: UsuarioGoogle):
    # 1) Buscamos si ya existe el correo
    usuario_existente = base_datos.usuarios.find_one({"email": usuario.email})

    if usuario_existente:
        # Si en la BD ya había aceptado → devolvemos directo
        if usuario_existente.get("aceptaTratamientoDatos", False):
            return {
                "mensaje": "Correo ya registrado",
                "usuario": modelo_usuario(usuario_existente)
            }

        # Si no había aceptado en la BD, obligamos el check
        if not usuario.aceptaTratamientoDatos:
            raise HTTPException(
                status_code=400,
                detail="Debe aceptar el tratamiento de datos personales para continuar"
            )

        # Marcó ahora el check → actualizamos en la BD y devolvemos
        base_datos.usuarios.update_one(
            {"email": usuario.email},
            {"$set": {"aceptaTratamientoDatos": True}}
        )
        actualizado = base_datos.usuarios.find_one({"email": usuario.email})
        return {
            "mensaje": "Consentimiento registrado",
            "usuario": modelo_usuario(actualizado)
        }

    # 2) Si NO existe, AHORA sí exigimos su consentimiento
    if not usuario.aceptaTratamientoDatos:
        raise HTTPException(
            status_code=400,
            detail="Debe aceptar el tratamiento de datos personales para registrarse"
        )

    # 3) Creamos el nuevo usuario con el campo en True
    nuevo_usuario = {
        "nombre": usuario.nombre,
        "email": usuario.email,
        "telefono": "",
        "clave": "autenticacionGoogle",
        "glampings": [],
        "aceptaTratamientoDatos": True,
        "fecha_registro": datetime.now().astimezone(ZONA_HORARIA_COLOMBIA),
    }
    result = base_datos.usuarios.insert_one(nuevo_usuario)
    usuario_insertado = base_datos.usuarios.find_one({"_id": result.inserted_id})

    return {
        "mensaje": "Usuario creado exitosamente",
        "usuario": modelo_usuario(usuario_insertado)
    }

# ------------Endpoint para obtener Usuarios con glamping--------------------
@ruta_usuario.get(
    "/con-glampings",
    response_model=List[UsuarioConGlampings],
    summary="Listar usuarios con al menos un glamping, incluyendo info de sus glampings"
)
def obtener_usuarios_con_glampings():
    usuarios = base_datos.usuarios.find({"glampings.0": {"$exists": True}})
    resultado = []

    for usuario in usuarios:
        glamping_ids = usuario.get("glampings", [])
        
        # Convertir a ObjectId        
        object_ids = []
        for gid in glamping_ids:
            try:
                object_ids.append(ObjectId(gid))
            except InvalidId:
                print(f"ID inválido ignorado: {gid}")
                continue
        
        # Buscar glampings por ID y seleccionar solo nombre y ciudad_departamento
        glampings = base_datos.glampings.find(
            {"_id": {"$in": object_ids}},
            {"nombreGlamping": 1, "ciudad_departamento": 1}
        )

        glamping_resumen = [
            {
                "id": str(g["_id"]),
                "nombreGlamping": g.get("nombreGlamping", ""),
                "ciudad_departamento": g.get("ciudad_departamento", "")
            }
            for g in glampings
        ]

        if glamping_resumen:  # Solo agregar si tiene glampings válidos
            resultado.append({
            "nombre": usuario["nombre"],
            "email": usuario["email"],
            "telefono": usuario.get("telefono", ""),
            "glampings": glamping_resumen
        })


    return resultado


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
    tipoDocumento: str = Body(None, embed=True),
    numeroDocumento: str = Body(None, embed=True),
    nombreTitular: str = Body(None, embed=True),
    
):
    try:
        # Buscar al usuario por su ID
        usuario = base_datos.usuarios.find_one({"_id": ObjectId(usuario_id)})
        if not usuario:
            raise HTTPException(status_code=404, detail="Usuario no encontrado")
        
        actualizaciones = {}
        
        # Actualizar banco si se proporciona
        if banco:
            actualizaciones["banco"] = banco

        # Actualizar número de cuenta si se proporciona
        if numeroCuenta:
            actualizaciones["numeroCuenta"] = numeroCuenta
        
        # Actualizar tipo de cuenta si se proporciona
        if tipoCuenta:
            actualizaciones["tipoCuenta"] = tipoCuenta
        
        # Actualizar tipo de documento si se proporciona
        if tipoDocumento:
            actualizaciones["tipoDocumento"] = tipoDocumento
        
        # Actualizar numeroDocumento si se proporciona
        if numeroDocumento:
            actualizaciones["numeroDocumento"] = numeroDocumento

        # Actualizar nombreTitular si se proporciona
        if nombreTitular:
            actualizaciones["nombreTitular"] = nombreTitular        
        
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

@ruta_usuario.get("/{usuario_id}/banco", response_model=dict)
async def obtener_datos_bancarios(usuario_id: str):
    """Obtiene los datos bancarios del propietario"""
    usuario = base_datos.usuarios.find_one({"_id": ObjectId(usuario_id)})
    if not usuario:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")

    return {
        "banco": usuario.get("banco"),
        "numeroCuenta": usuario.get("numeroCuenta"),
        "tipoCuenta": usuario.get("tipoCuenta"),
        "tipoDocumento": usuario.get("tipoDocumento"),
        "numeroDocumento": usuario.get("numeroDocumento"),
        "nombreTitular": usuario.get("nombreTitular"),        
    }


# listar glampings según rol
@ruta_usuario.get("/{usuario_id}/glampings", response_model=List[GlampingResumen])
async def obtener_glampings_segun_rol(usuario_id: str):
    usuario = base_datos.usuarios.find_one({"_id": ObjectId(usuario_id)})
    if not usuario:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    
    # Si es superusuario, trae todos los glampings
    if usuario.get("rol") == "admin":
        glampings_cursor = base_datos.glampings.find()
    else:
        glampings_ids = usuario.get("glampings", [])
        object_ids = [ObjectId(gid) for gid in glampings_ids if ObjectId.is_valid(gid)]
        glampings_cursor = base_datos.glampings.find(
            {"_id": {"$in": object_ids}}
        )

    glampings = []
    for g in glampings_cursor:
        glampings.append({
            "id": str(g["_id"]),
            "nombreGlamping": g.get("nombreGlamping", ""),
            "ciudad_departamento": g.get("ciudad_departamento", "")
        })
    
    return glampings


# facebook autenticacion

# import requests

# FACEBOOK_APP_ID = os.getenv("FACEBOOK_APP_ID")
# FACEBOOK_APP_SECRET = os.getenv("FACEBOOK_APP_SECRET")

# @ruta_usuario.post("/facebook", response_model=dict)
# async def registro_facebook(accessToken: str = Body(..., embed=True)):
#     """
#     Registra o inicia sesión con Facebook. 
#     Valida el token de acceso y registra al usuario si no existe.
#     """
#     if not accessToken:
#         raise HTTPException(status_code=400, detail="No se recibió el token de Facebook")

#     # 1. Verificar el token de Facebook
#     #    Usamos /debug_token para validar que el token sea válido y emitido para esta app.
#     debug_url = (
#         f"https://graph.facebook.com/debug_token?"
#         f"input_token={accessToken}&access_token={FACEBOOK_APP_ID}|{FACEBOOK_APP_SECRET}"
#     )
#     debug_response = requests.get(debug_url)
#     debug_data = debug_response.json()

#     # Si el token no es válido, retornamos error
#     if debug_response.status_code != 200 or not debug_data.get("data", {}).get("is_valid"):
#         raise HTTPException(status_code=400, detail="Token de Facebook inválido o expirado")

#     # 2. Obtener datos del usuario con /me (id, name, email, etc.)
#     user_info_url = f"https://graph.facebook.com/me?fields=id,name,email&access_token={accessToken}"
#     user_response = requests.get(user_info_url)
#     if user_response.status_code != 200:
#         raise HTTPException(status_code=400, detail="No se pudo obtener información del usuario de Facebook")

#     user_data = user_response.json()
#     # user_data debe tener campos como { "id": "...", "name": "...", "email": "..." }

#     email = user_data.get("email")
#     nombre = user_data.get("name", "Usuario Facebook")

#     if not email:
#         # Algunos usuarios de Facebook pueden no tener email público
#         # Decide qué hacer en ese caso: forzar que el usuario ingrese un email, etc.
#         raise HTTPException(status_code=400, detail="No se encontró un correo electrónico en Facebook")

#     # 3. Revisar si el usuario ya existe en la base de datos
#     usuario_existente = base_datos.usuarios.find_one({"email": email})
#     if usuario_existente:
#         # El correo ya está registrado → Devolvemos sus datos
#         return {
#             "mensaje": "Correo ya registrado",
#             "usuario": {
#                 "_id": str(usuario_existente["_id"]),
#                 "nombre": usuario_existente["nombre"],
#                 "email": usuario_existente["email"],
#                 "telefono": usuario_existente["telefono"],
#             }
#         }

#     # 4. Crear un nuevo usuario con clave de autenticación de Facebook
#     nuevo_usuario = {
#         "nombre": nombre,
#         "email": email,
#         "telefono": "",
#         "clave": "autenticacionFacebook",  # Distinto a Google
#         "glampings": [],
#         "fecha_registro": datetime.now().astimezone(ZONA_HORARIA_COLOMBIA),
#         "foto": None,
#         "banco": None,
#         "numeroCuenta": None,
#         "tipoCuenta": None,
#         "tipoDocumento": None,
#         "numeroDocumento": None,
#         "nombreTitular": None,
#     }

#     result = base_datos.usuarios.insert_one(nuevo_usuario)
#     nuevo_usuario["_id"] = str(result.inserted_id)

#     return {"mensaje": "Usuario creado exitosamente", "usuario": nuevo_usuario}
