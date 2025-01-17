import os
import socketio
from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse
from motor.motor_asyncio import AsyncIOMotorClient

# Crear el servidor de Socket.IO
sio = socketio.AsyncServer()

# Configuración de MongoDB
MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017")
client = AsyncIOMotorClient(MONGO_URI)
db = client["glamperos"]
messages_collection = db["mensajes"]

# Crear el enrutador de FastAPI para mensajería
ruta_mensajes = APIRouter(
    prefix="/mensajes",
    tags=["Mensajes"],
    responses={404: {"description": "No encontrado"}},
)

# Ruta para almacenar los mensajes en MongoDB
@ruta_mensajes.post("/enviar_mensaje")
async def store_message(message: dict):
    try:
        # Validación del mensaje
        if not message.get("emisor") or not message.get("receptor") or not message.get("mensaje"):
            raise HTTPException(status_code=400, detail="Faltan campos requeridos")

        # Guardar el mensaje en la colección de MongoDB
        result = await messages_collection.insert_one(message)
        return JSONResponse(content={"message": "Mensaje guardado exitosamente", "id": str(result.inserted_id)}, status_code=200)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error: {str(e)}")

# Manejar eventos de conexión y recepción de mensajes por Socket.IO
@sio.event
async def connect(sid, environ):
    print(f"Usuario {sid} conectado")

@sio.event
async def disconnect(sid):
    print(f"Usuario {sid} desconectado")

@sio.event
async def send_message(sid, data):
    """Recibe un mensaje del usuario y lo guarda en MongoDB"""
    try:
        # Validación de datos
        if not data.get("emisor") or not data.get("receptor") or not data.get("mensaje"):
            return {"error": "Faltan datos en el mensaje"}
        
        # Agregar campos de emisor y receptor y guardar el mensaje
        message = {
            "emisor": data["emisor"],
            "receptor": data["receptor"],
            "mensaje": data["mensaje"],
            "timestamp": data["timestamp"]
        }

        # Guardar el mensaje en MongoDB
        await messages_collection.insert_one(message)

        # Enviar el mensaje de vuelta al receptor por Socket.IO
        await sio.emit('receive_message', message, room=data["receptor"])
        
        return {"message": "Mensaje enviado"}
    except Exception as e:
        return {"error": f"Error al enviar el mensaje: {str(e)}"}





# Obtener los receptores únicos con los que el emisor ha tenido conversaciones
@ruta_mensajes.get("/conversaciones/{emisor}")
async def get_conversaciones(emisor: str):
    try:
        # Buscar tanto como emisor como receptor y traer el último mensaje por cada conversación
        conversation_ids = await messages_collection.aggregate([
            {
                "$match": {
                    "$or": [
                        {"emisor": emisor},
                        {"receptor": emisor}
                    ]
                }
            },
            {
                "$project": {
                    "contacto": {
                        "$cond": [
                            {"$eq": ["$emisor", emisor]},
                            "$receptor",  # Si es el emisor, tomar el receptor
                            "$emisor"    # Si es el receptor, tomar el emisor
                        ]
                    },
                    "timestamp": 1  # Traer el campo timestamp para ordenar
                }
            },
            {
                "$group": {
                    "_id": "$contacto",  # Agrupar por el contacto único
                    "ultima_fecha": {"$max": "$timestamp"}  # Obtener la última fecha (timestamp más reciente)
                }
            },
            {
                "$project": {
                    "_id": 0,  # No incluir el campo _id
                    "contacto": "$_id",  # Renombrar _id a contacto
                    "ultima_fecha": 1  # Incluir la última fecha
                }
            }
        ]).to_list(length=100)

        if not conversation_ids:
            return JSONResponse(content={"message": "No hay conversaciones para este emisor."}, status_code=404)

        # Retornar la lista de contactos únicos con la última fecha de conversación
        return {"conversaciones": conversation_ids}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error: {str(e)}")





# Ruta para obtener los mensajes entre un emisor y un receptor
from bson import ObjectId
@ruta_mensajes.get("/obtener_mensajes/{emisor}/{receptor}")
async def get_messages(emisor: str, receptor: str):
    try:
        # Realizar la consulta utilizando $or para buscar mensajes donde el emisor y receptor sean intercambiables
        messages = await messages_collection.find(
            {
                "$or": [
                    {"emisor": emisor, "receptor": receptor},
                    {"emisor": receptor, "receptor": emisor}
                ]
            }
        ).to_list(length=100)

        if not messages:
            return JSONResponse(content={"message": "No hay mensajes entre estos usuarios."}, status_code=404)

        # Convertir el campo '_id' de cada mensaje a string antes de devolverlo
        for message in messages:
            message['_id'] = str(message['_id'])  # Convertir ObjectId a string

        # Retornar los mensajes encontrados
        return {"mensajes": messages}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error: {str(e)}")
