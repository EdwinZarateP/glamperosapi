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
to_whatsapp_number = 'whatsapp:+573125443396'  # El número de destino

# SID de la plantilla
template_sid = 'HX9fbee548a467e2255d2b1e2ed7d4dd2f'  # Este SID debe ser el SID de la plantilla de WhatsApp

# Inicialización del cliente de Twilio
client = Client(account_sid, auth_token)

# Función para enviar el mensaje
@ruta_whatsapp.post("/enviar-mensaje")
async def enviar_mensaje():
    try:
        # Enviar mensaje utilizando la plantilla de WhatsApp
        message = client.messages.create(
            to=to_whatsapp_number,
            from_=from_whatsapp_number,
            body="Este es un mensaje de confirmación",  # Texto que aparecerá si no se usa plantilla
            status_callback="https://www.yourcallbackurl.com",
            # Usar 'template' aquí ya no es válido directamente en 'create', pero el flujo de plantillas debe configurarse
        )
        return {"status": "success", "message_sid": message.sid}
    except Exception as e:
        return {"status": "error", "message": str(e)}
