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
    name: str
    email: str

@ruta_correos.post("/send-email")
async def send_email(data: EmailRequest):
    try:
        # Agregar correo adicional por defecto
        destinatarios = [data.email, "emzp1994@gmail.com"]  # Añadir el correo adicional

        # Enviar el correo
        response = resend.Emails.send({
            "from": "registro@glamperos.com",
            "to": destinatarios,  # Usar la lista de destinatarios
            "subject": "¡Bienvenid@ a la familia Glamperos!",
            "html": f"""
            <div style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
                <h1 style="color: #4CAF50;">¡Bienvenido a la familia Glamperos!</h1>
                <p>
                    Estimad@ {data.name},
                </p>
                <p>
                    Nos sentimos muy emocionados de tenerte como parte de nuestra
                    Comunidad de emprendedores de experiencias únicas. Gracias por inscribir tu propiedad con Glamperos, 
                    el lugar donde el glamping cobra vida.
                    Una vez verifiquemos si tu glamping cumple con nuestros requisitos, te notificaremos a este correo cuando quede activo en la plataforma!
                </p>
                <p>
                    Ahora estás listo/a para conectar con cientos de personas que buscan una experiencia única, confortable y memorable en tu espacio.
                </p>
                <p>
                    Si necesitas ayuda o tienes preguntas, nuestro equipo estará siempre aquí para ti.
                </p>
                <p>
                    ¡Juntos haremos que esta aventura sea inolvidable!
                </p>
                <p style="margin: 20px 0;">
                    El equipo de <strong style="color: #4CAF50;">Glamperos</strong>.
                </p>
                <hr style="border: 1px solid #e0e0e0;">
                <p style="font-size: 0.9em; color: #777;">
                    Si tienes preguntas, no dudes en ponerte en contacto con nosotros a través de nuestro portal.
                </p>
            </div>
            """
        })

        return {"status": "success", "response": response}
    except Exception as e:
        return {"status": "error", "error": str(e)}

