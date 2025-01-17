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

    """
    Envía un mensaje utilizando una plantilla aprobada.
    - `numero`: Número de WhatsApp del destinatario.
    """

# Ruta para enviar mensajes usando la plantilla aprobada
@ruta_whatsapp.post("/enviar-plantilla")
async def enviar_mensaje_plantilla(mensaje: MensajeWhatsAppTemplate):
    # Credenciales de Twilio desde las variables de entorno
    account_sid = os.environ.get("TWILIO_ACCOUNT_SID")
    auth_token = os.environ.get("TWILIO_AUTH_TOKEN")
    from_whatsapp = 'whatsapp:+573215658598'
    template_name = 'confirmacion'  # Nombre de tu plantilla
    template_namespace = 'your_template_namespace'  # Namespace de la plantilla si lo tienes, puede ser vacío

    if not account_sid or not auth_token:
        raise HTTPException(status_code=500, detail="Twilio credentials not set in environment variables.")

    client = Client(account_sid, auth_token)

    try:
        # Envío del mensaje utilizando la plantilla
        mensaje_twilio = client.messages.create(
            from_=from_whatsapp,
            to=f'whatsapp:{mensaje.numero}',
            # Aquí usamos `template` y los parámetros para la plantilla, si no hay parámetros no es necesario incluir nada.
            body="Este es un mensaje de prueba",
            template={
                "namespace": template_namespace,
                "name": template_name,
                "language": {"code": "es"},
                "components": []
            }
        )

        # Respuesta
        return {"status": "success", "message_sid": mensaje_twilio.sid}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al enviar mensaje: {str(e)}")
