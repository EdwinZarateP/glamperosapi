from fastapi import APIRouter
from twilio.rest import Client
import os

# Configuración del enrutador
ruta_whatsapp = APIRouter(
    prefix="/whatsapp",
    tags=["whatsapp"],
    responses={404: {"message": "No encontrado"}},
)

# Credenciales de Twilio desde las variables de entorno
account_sid = os.environ.get("TWILIO_ACCOUNT_SID")
auth_token = os.environ.get("TWILIO_AUTH_TOKEN")
from_whatsapp_number = 'whatsapp:+573215658598'  # Tu número de WhatsApp registrado en Twilio
to_whatsapp_number = 'whatsapp:+575443396'  # El número de destino

# SID de la plantilla
template_sid = 'HX9fbee548a467e2255d2b1e2ed7d4dd2f'

# Inicialización del cliente de Twilio
client = Client(account_sid, auth_token)

# Función para enviar el mensaje
@ruta_whatsapp.post("/enviar-mensaje")
async def enviar_mensaje():
    try:
        message = client.messages.create(
            to=to_whatsapp_number,
            from_=from_whatsapp_number,
            body="Confirmación de tu mensaje",  # Puedes incluir un texto simple, si es necesario
            template={
                'name': 'confirmacion',  # El nombre de tu plantilla
                'language': {'code': 'es_MX'},  # El idioma de la plantilla
                'parameters': [
                    {'type': 'text', 'text': 'Parámetro del mensaje'}
                ]
            }
        )
        return {"status": "success", "message_sid": message.sid}
    except Exception as e:
        return {"status": "error", "message": str(e)}
