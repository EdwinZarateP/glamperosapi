import os
from fastapi import APIRouter, status, HTTPException
from pydantic import BaseModel
import resend

# Cargar la clave de API desde las variables de entorno
resend.api_key = os.getenv("RESEND_API_KEY")

# Verificar si la clave de API está presente
if not resend.api_key:
    raise ValueError("La clave RESEND_API_KEY no está configurada en las variables de entorno.")

# Crear el router con el prefijo "/correos"
ruta_correos = APIRouter(
    prefix="/correos",
    tags=["correos"],
    responses={status.HTTP_404_NOT_FOUND: {"message": "No encontrado"}}
)

# Modelo de datos para el cuerpo del request
class EmailRequest(BaseModel):
    from_email: str = "registro@glamperos.com"  # Remitente opcional con valor por defecto
    name: str
    email: str
    subject: str
    html_content: str  # Contenido del correo

@ruta_correos.post("/send-email")
async def send_email(data: EmailRequest):
    try:
        # Agregar correo adicional por defecto
        destinatarios = [data.email]

        # Enviar el correo
        response = resend.Emails.send({
            "from": data.from_email,  # Usar el remitente proporcionado o el valor por defecto
            "to": destinatarios,
            "subject": data.subject,
            "html": data.html_content  # Usar el contenido HTML enviado desde el frontend
        })

        return {"status": "success", "response": response}
    except Exception as e:
        return {"status": "error", "error": str(e)}
