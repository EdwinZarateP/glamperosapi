from fastapi import APIRouter, HTTPException, Depends, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from pymongo import MongoClient
from bson import ObjectId
from passlib.context import CryptContext
import jwt
import os
from datetime import datetime, timedelta, timezone
from typing import List
from pydantic import BaseModel
from bd.models.usuario import modelo_usuario, modelo_usuarios
from fastapi.responses import JSONResponse
import requests


# Configuración de la base de datos
MONGO_URI = os.environ.get("MONGO_URI", "mongodb://localhost:27017")
ConexionMongo = MongoClient(MONGO_URI)
base_datos = ConexionMongo["glamperos"]

# Configuración de FastAPI y seguridad
ruta_usuario = APIRouter(
    prefix="/usuarios",
    tags=["Usuarios"],
    responses={status.HTTP_404_NOT_FOUND: {"message": "No encontrado"}},
)

esquema_oauth2 = OAuth2PasswordBearer(tokenUrl="usuarios/token")
CLAVE_SECRETA = "tu_clave_secreta"  # Cambia esto por una clave secreta más segura
ALGORITMO = "HS256"
EXPIRE_MINUTOS_TOKEN = 20

# Configuración de la contraseña
contexto_pwd = CryptContext(schemes=["bcrypt"], deprecated="auto")


# Modelos de datos
class Usuario(BaseModel):
    nombre: str
    email: str
    telefono: str
    clave: str
    glampings: List[str] = []  # Lista de IDs de glampings asociados


def modelo_usuario(usuario) -> dict:
    return {
        "id": str(usuario["_id"]),
        "nombre": usuario["nombre"],
        "email": usuario["email"],
        "telefono": usuario["telefono"],
        "glampings": usuario.get("glampings", []),
    }


# Funciones de seguridad
def crear_hash(clave: str) -> str:
    return contexto_pwd.hash(clave)


def verificar_hash(clave: str, clave_hash: str) -> bool:
    return contexto_pwd.verify(clave, clave_hash)


def crear_token(data: dict, expires_delta: timedelta = None) -> str:
    to_encode = data.copy()
    if expires_delta:
        expira = datetime.now(timezone.utc) + expires_delta
    else:
        expira = datetime.now(timezone.utc) + timedelta(minutes=15)
    to_encode.update({"exp": expira})
    return jwt.encode(to_encode, CLAVE_SECRETA, algorithm=ALGORITMO)


async def obtener_usuario_actual(token: str = Depends(esquema_oauth2)):
    excepcion_credenciales = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="No se pudo validar las credenciales",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, CLAVE_SECRETA, algorithms=[ALGORITMO])
        email = payload.get("sub")
        if email is None:
            raise excepcion_credenciales
    except jwt.PyJWTError:
        raise excepcion_credenciales
    usuario = base_datos.usuarios.find_one({"email": email})
    if usuario is None:
        raise excepcion_credenciales
    return modelo_usuario(usuario)


# Rutas de la API
@ruta_usuario.post("/token")
async def iniciar_sesion(form_data: OAuth2PasswordRequestForm = Depends()):
    usuario = base_datos.usuarios.find_one({"email": form_data.username})
    if not usuario or not verificar_hash(form_data.password, usuario["clave"]):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Credenciales incorrectas")
    
    expires_access_token = timedelta(minutes=EXPIRE_MINUTOS_TOKEN)
    access_token = crear_token(data={"sub": usuario["email"]}, expires_delta=expires_access_token)
    
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "nombre": usuario["nombre"],
    }

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
                "email": usuario_existente["email"]
            }
        }

    # Crear un nuevo usuario si no existe
    usuario.clave = crear_hash(usuario.clave)
    nuevo_usuario = {
        "nombre": usuario.nombre,
        "email": usuario.email,
        "telefono": usuario.telefono,
        "clave": usuario.clave,
        "glampings": [],
    }
    
    # Insertar el nuevo usuario en la base de datos
    result = base_datos.usuarios.insert_one(nuevo_usuario)
    
    # Recuperar el ID del usuario recién creado
    nuevo_usuario["_id"] = str(result.inserted_id)
    
    # Respuesta con el ID del usuario recién creado
    return {"mensaje": "Usuario creado exitosamente", "usuario": nuevo_usuario}



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
        "clave": crear_hash("autenticacionGoogle"),
        "glampings": [],
    }
    result = base_datos.usuarios.insert_one(nuevo_usuario)
    return modelo_usuario(base_datos.usuarios.find_one({"_id": result.inserted_id}))


@ruta_usuario.get("/{usuario_id}", response_model=dict)
async def obtener_usuario(usuario_id: str, usuario_actual: dict = Depends(obtener_usuario_actual)):
    usuario = base_datos.usuarios.find_one({"_id": ObjectId(usuario_id)})
    if usuario is None:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    return modelo_usuario(usuario)


@ruta_usuario.put("/{usuario_id}", response_model=dict)
async def actualizar_usuario(usuario_id: str, usuario: Usuario, usuario_actual: dict = Depends(obtener_usuario_actual)):
    usuario_actualizado = {
        "nombre": usuario.nombre,
        "email": usuario.email,
        "telefono": usuario.telefono,
        "clave": crear_hash(usuario.clave),
    }
    result = base_datos.usuarios.update_one({"_id": ObjectId(usuario_id)}, {"$set": usuario_actualizado})
    if result.modified_count == 0:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    return modelo_usuario(base_datos.usuarios.find_one({"_id": ObjectId(usuario_id)}))


@ruta_usuario.delete("/{usuario_id}", response_model=dict)
async def eliminar_usuario(usuario_id: str, usuario_actual: dict = Depends(obtener_usuario_actual)):
    result = base_datos.usuarios.delete_one({"_id": ObjectId(usuario_id)})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    return {"mensaje": "Usuario eliminado"}


@ruta_usuario.get("/{usuario_id}/glampings", response_model=List[dict])
async def obtener_glampings_usuario(usuario_id: str):
    usuario = base_datos.usuarios.find_one({"_id": ObjectId(usuario_id)})
    if not usuario:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    
    glamping_ids = usuario.get("glampings", [])
    glampings = list(base_datos.glampings.find({"_id": {"$in": [ObjectId(glamping_id) for glamping_id in glamping_ids]}}))
    return glampings


@ruta_usuario.delete("/{usuario_id}/glampings/{glamping_id}", response_model=dict)
async def desvincular_glamping(usuario_id: str, glamping_id: str):
    result = base_datos.usuarios.update_one(
        {"_id": ObjectId(usuario_id)},
        {"$pull": {"glampings": glamping_id}}
    )
    if result.modified_count == 0:
        raise HTTPException(status_code=404, detail="Usuario o glamping no encontrado")
    return {"mensaje": "Glamping desvinculado exitosamente"}


@ruta_usuario.get("/", response_model=dict)
async def buscar_usuario(email: str):
    """Buscar un usuario por su correo electrónico."""
    if not email:
        raise HTTPException(status_code=400, detail="Se requiere un correo electrónico válido")
    
    usuario = base_datos.usuarios.find_one({"email": email})
    if not usuario:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    return modelo_usuario(usuario)
