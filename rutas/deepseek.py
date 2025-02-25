from fastapi import APIRouter, HTTPException
import os
import requests
from typing import Dict
from pymongo import MongoClient

# Obtener la API Key desde variables de entorno
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "tu_api_key_aqui")

# Conexión a MongoDB
MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017")
ConexionMongo = MongoClient(MONGO_URI)
db = ConexionMongo["glamperos"]

# Crear el router para DeepSeek
ruta_deepseek = APIRouter(
    prefix="/deepseek",
    tags=["DeepSeek"],
    responses={404: {"description": "No encontrado"}},
)

@ruta_deepseek.post("/")
async def chat_deepseek(data: Dict[str, str]):
    """
    Chatbot que responde preguntas sobre glampings usando DeepSeek AI.
    
    **Parámetro de entrada (JSON):**  
    - `message`: La pregunta del usuario.
    
    **Ejemplo de uso:**
    ```json
    { "message": "¿Cuáles son los mejores glampings en Cali?" }
    ```
    
    **Respuesta esperada:**
    ```json
    { "response": "Los mejores glampings en Cali son..." }
    ```
    """
    message = data.get("message")
    
    if not message:
        raise HTTPException(status_code=400, detail="El mensaje es obligatorio")

    # Extraer información de glampings desde MongoDB
    glampings = list(db["glampings"].find({}, {"_id": 0, "nombreGlamping": 1, "ciudad_departamento": 1, "descripcionGlamping": 1}))
    contexto = "\n".join([f"{g['nombreGlamping']} en {g['ciudad_departamento']}: {g['descripcionGlamping']}" for g in glampings])

    # Configurar la solicitud a la API de DeepSeek
    payload = {
        "model": "deepseek-chat",
        "messages": [
            {"role": "system", "content": "Eres un asistente de reservas de Glamping en Colombia. Usa la información del contexto para responder."},
            {"role": "user", "content": f"Contexto:\n{contexto}\n\nPregunta: {message}"}
        ],
        "max_tokens": 200
    }

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {DEEPSEEK_API_KEY}"
    }

    try:
        response = requests.post("https://api.deepseek.com/v1/chat/completions", json=payload, headers=headers)
        response.raise_for_status()
        respuesta_bot = response.json()["choices"][0]["message"]["content"]
        return {"response": respuesta_bot}
    
    except requests.exceptions.RequestException as e:
        raise HTTPException(status_code=500, detail=f"Error en la API de DeepSeek: {str(e)}")
