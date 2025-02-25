from fastapi import APIRouter, HTTPException
import os
import openai
from typing import Dict
from pymongo import MongoClient

# Obtener la API Key de OpenAI desde variables de entorno
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "tu_api_key_aqui")

# Conexión a MongoDB
MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017")
ConexionMongo = MongoClient(MONGO_URI)
db = ConexionMongo["glamperos"]

# Crear el router para OpenAI
ruta_openai = APIRouter(
    prefix="/openai",
    tags=["OpenAI"],
    responses={404: {"description": "No encontrado"}},
)

@ruta_openai.post("/")
async def chat_openai(data: Dict[str, str]):
    """
    Chatbot que responde preguntas sobre glampings usando OpenAI.

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

    # Configurar la solicitud a OpenAI
    try:
        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",  # Puedes cambiar a "gpt-4o" si tienes acceso
            messages=[
                {"role": "system", "content": "Eres un asistente de reservas de Glamping en Colombia. Usa la información del contexto para responder."},
                {"role": "user", "content": f"Contexto:\n{contexto}\n\nPregunta: {message}"}
            ],
            max_tokens=200
        )

        respuesta_bot = response["choices"][0]["message"]["content"]
        return {"response": respuesta_bot}

    except openai.error.OpenAIError as e:
        raise HTTPException(status_code=500, detail=f"Error en la API de OpenAI: {str(e)}")
