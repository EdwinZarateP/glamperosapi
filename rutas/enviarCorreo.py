from fastapi import APIRouter, status
import resend


# Configurar clave de API de Resend
resend.api_key = "re_TpRoK8hZ_cDMXrA8Vz1zYQYcwCgGnHTfy"

# Crear el router con el prefijo "/correos"
ruta_correos = APIRouter(
    prefix="/correos",
    tags=["correos"],
    responses={status.HTTP_404_NOT_FOUND: {"message": "No encontrado"}}
)

@ruta_correos.post("/send-email")
async def send_email():
    try:
        # Enviar el correo
        response = resend.Emails.send({
            "from": "registro@glamperos.com",
            "to": "emzp1994@gmail.com",
            "subject": "Validacion de correo para crear Glamping!",
            "html": "<p>Hola soy Edwin!</p>"
        })
        return {"status": "success", "response": response}
    except Exception as e:
        return {"status": "error", "error": str(e)}
