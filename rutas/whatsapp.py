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
class MensajeWhatsAppTemplate(BaseModel):
    numero: str
    parametros: dict

    """
    Envía un mensaje utilizando una plantilla aprobada.
    - `numero`: Número de WhatsApp del destinatario.
    - `parametros`: Diccionario con los valores para reemplazar las variables de la plantilla.
    """

@ruta_whatsapp.post("/enviar-plantilla")
async def enviar_mensaje_plantilla(mensaje: MensajeWhatsAppTemplate):
    # Credenciales de Twilio desde las variables de entorno
    account_sid = os.environ.get("TWILIO_ACCOUNT_SID")
    auth_token = os.environ.get("TWILIO_AUTH_TOKEN")
    from_whatsapp = 'whatsapp:+573215658598'
    template_sid = 'HX9fbee548a467e2255d2b1e2ed7d4dd2f'

    if not account_sid or not auth_token:
        raise HTTPException(status_code=500, detail="Twilio credentials not set in environment variables.")

    client = Client(account_sid, auth_token)

    try:
        # Envío del mensaje utilizando la plantilla
        mensaje_twilio = client.messages.create(
            from_=from_whatsapp,
            to=f'whatsapp:{mensaje.numero}',
            template={
                'name': 'confirmacion',
                'parameters': mensaje.parametros or []
            },
            content_sid=template_sid
        )
        return {"status": "success", "message_sid": mensaje_twilio.sid}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al enviar mensaje: {str(e)}")
