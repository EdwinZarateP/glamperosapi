from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from twilio.rest import Client
import os

# Configuración del enrutador
ruta_whatsapp = APIRouter(
    prefix="/whatsapp",
    tags=["whatsapp"],
    responses={404: {"message": "No encontrado"}},
)

# Modelo de entrada para el mensaje
class MensajeWhatsAppDirecto(BaseModel):
    numero: str
    mensaje: str

    """
    Envía un mensaje de texto directo por WhatsApp.
    - `numero`: Número de WhatsApp del destinatario.
    - `mensaje`: El mensaje que quiere enviar.
    """

# Ruta para enviar mensaje por WhatsApp
@ruta_whatsapp.post("/enviar-directo")
async def enviar_mensaje_directo(mensaje: MensajeWhatsAppDirecto):
    # Credenciales de Twilio desde las variables de entorno
    account_sid = os.environ.get("TWILIO_ACCOUNT_SID")
    auth_token = os.environ.get("TWILIO_AUTH_TOKEN")
    from_whatsapp = 'whatsapp:+573215658598'

    if not account_sid or not auth_token:
        raise HTTPException(status_code=500, detail="Twilio credentials not set in environment variables.")

    client = Client(account_sid, auth_token)

    try:
        # Envío del mensaje directo
        mensaje_twilio = client.messages.create(
            from_=from_whatsapp,
            body=mensaje.mensaje,
            to=f'whatsapp:{mensaje.numero}'
        )
        return {"status": "success", "message_sid": mensaje_twilio.sid}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al enviar mensaje: {str(e)}")
