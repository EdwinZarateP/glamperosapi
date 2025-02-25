from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
import os
import requests
from pymongo import MongoClient
from typing import List

# Obtener la API Key desde variables de entorno
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY")
if not DEEPSEEK_API_KEY:
    raise ValueError("❌ ERROR: La variable DEEPSEEK_API_KEY no está configurada.")

# Conexión a MongoDB (cambia la URI si usas otro servidor)
MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017")
ConexionMongo = MongoClient(MONGO_URI)
db = ConexionMongo["glamperos"]

# Crear el router para DeepSeek
ruta_deepseek = APIRouter(
    prefix="/deepseek",
    tags=["DeepSeek"],
    responses={404: {"description": "No encontrado"}},
)

# Definir el esquema del request body con Pydantic
class DeepSeekRequest(BaseModel):
    message: str

@ruta_deepseek.post("/")
async def chat_deepseek(request: DeepSeekRequest):
    """
    Chatbot que responde preguntas sobre glampings usando DeepSeek AI.
    
    **Parámetro de entrada (JSON):**  
    ```json
    { "message": "¿Cuáles son los mejores glampings en Cali?" }
    ```

    **Respuesta esperada:**
    ```json
    { "response": "Los mejores glampings en Cali son..." }
    ```
    """
    message = request.message.strip()  # Limpiar espacios en blanco

    if not message:
        raise HTTPException(status_code=400, detail="El mensaje no puede estar vacío.")

    # Obtener información de los glampings desde MongoDB
    glampings = list(db["glampings"].find({}, {"_id": 0, "nombreGlamping": 1, "ciudad_departamento": 1, "descripcionGlamping": 1, "calificacion": 1}))

    if not glampings:
        raise HTTPException(status_code=500, detail="No se encontraron datos de glampings en la base de datos.")

    # Formatear la información de los glampings para el contexto de DeepSeek
    contexto = "\n".join([
        f"{g['nombreGlamping']} en {g['ciudad_departamento']}: {g['descripcionGlamping']} (Calificación: {g['calificacion']})"
        for g in glampings
    ])

    # Configurar la solicitud a la API de DeepSeek
    payload = {
        "model": "deepseek-chat",
        "messages": [
            {"role": "system", "content": "Eres un asistente de reservas de Glamping en Colombia. Usa la información del contexto para responder."},
            {"role": "user", "content": f"Contexto:\n{contexto}\n\nPregunta: {message}"}
        ],
        "max_tokens": 300
    }

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {DEEPSEEK_API_KEY}"
    }

    try:
        response = requests.post("https://api.deepseek.com/v1/chat/completions", json=payload, headers=headers)
        response.raise_for_status()
        respuesta_bot = response.json().get("choices", [{}])[0].get("message", {}).get("content", "No se pudo obtener una respuesta.")

        return {"response": respuesta_bot}
    
    except requests.exceptions.RequestException as e:
        raise HTTPException(status_code=500, detail=f"Error en la API de DeepSeek: {str(e)}")
