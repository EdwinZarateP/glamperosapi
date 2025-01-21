from fastapi import FastAPI, Request, APIRouter
from fastapi.responses import JSONResponse

# Crear el router
ruta_whatsapp = APIRouter(
    prefix="/whatsapp",
    tags=["whatsapp"],
    responses={404: {"message": "No encontrado"}},
)

# Ruta para manejar la verificación del webhook
@ruta_whatsapp.get("/")
async def verify_webhook(request: Request):
    # Facebook envía el desafío en el parámetro 'hub.challenge'
    hub_challenge = request.query_params.get("hub.challenge")
    hub_verify_token = request.query_params.get("hub.verify_token")
    
    # Verifica que el token sea el correcto
    if hub_verify_token == "mi_token_secreto":  # Aquí reemplaza con el token de verificación que hayas elegido
        return JSONResponse(content=hub_challenge)
    else:
        return JSONResponse(content="Error de verificación", status_code=403)


# Ruta para recibir los mensajes
@ruta_whatsapp.post("/")
async def webhook(request: Request):
    # Obtiene los datos recibidos del mensaje de WhatsApp
    data = await request.json()
    
    # Aquí puedes procesar los datos recibidos (por ejemplo, almacenar los mensajes en una base de datos)
    print(f"Datos recibidos del mensaje: {data}")
    
    # Puedes agregar una respuesta automatizada o lógica adicional aquí
    return {"status": "ok"}
