from fastapi import APIRouter, HTTPException
import os
import requests
from typing import Dict
from pymongo import MongoClient

# 1. Obtén la clave de OpenAI desde variables de entorno
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
if not OPENAI_API_KEY:
    raise ValueError("❌ ERROR: La variable OPENAI_API_KEY no está configurada.")

# 2. Conexión a MongoDB
MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017")
ConexionMongo = MongoClient(MONGO_URI)
db = ConexionMongo["glamperos"]

# 3. Crear el router para OpenAI (puedes cambiar el prefix a "/openai" o mantener "/deepseek")
ruta_openai = APIRouter(
    prefix="/openai",
    tags=["OpenAI"],
    responses={404: {"description": "No encontrado"}},
)

@ruta_openai.post("/")
async def chat_openai(data: Dict[str, str]):
    """
    Chatbot que responde preguntas sobre glampings usando OpenAI GPT-3.5.

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

    # 4. Obtener la info de los glampings desde MongoDB
    glampings = list(db["glampings"].find({}, {
        "_id": 0, 
        "nombreGlamping": 1, 
        "ciudad_departamento": 1, 
        "descripcionGlamping": 1,
        "calificacion": 1
    }))

    # Si no hay glampings, avisar
    if not glampings:
        raise HTTPException(status_code=500, detail="No se encontraron datos de glampings en la base de datos.")

    # 5. Crear un contexto con la info de los glampings
    #    para que GPT-3.5 sepa qué responder
    contexto = "\n".join([
        f"{g['nombreGlamping']} en {g['ciudad_departamento']}: {g['descripcionGlamping']} (Calificación: {g.get('calificacion', 'N/A')})"
        for g in glampings
    ])

    # 6. Payload para la API de OpenAI
    payload = {
        "model": "gpt-3.5-turbo",
        "messages": [
            {
                "role": "system", 
                "content": "Eres un asistente de reservas de Glamping en Colombia. Usa la información del contexto para responder."
            },
            {
                "role": "user", 
                "content": f"Contexto:\n{contexto}\n\nPregunta: {message}"
            }
        ],
        "max_tokens": 200
    }

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {OPENAI_API_KEY}"
    }

    # 7. Llamar a la API de OpenAI nueva
    try:
        response = requests.post("https://api.openai.com/v1/chat/completions", json=payload, headers=headers)
        response.raise_for_status()
        respuesta_bot = response.json()["choices"][0]["message"]["content"]
        return {"response": respuesta_bot}
    
    except requests.exceptions.RequestException as e:
        raise HTTPException(status_code=500, detail=f"Error en la API de OpenAI: {str(e)}")
