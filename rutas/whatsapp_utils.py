# whatsapp_utils.py
import os
import httpx
from typing import Optional

async def enviar_whatsapp_cliente(
    numero: str,
    codigo_reserva: str,
    whatsapp: str,
    nombre_glamping_reservado: str,
    direccion_glamping: str,
    latitud: float,
    longitud: float,
    nombre_cliente: str,
) -> None:
    """
    Envía un mensaje de WhatsApp al cliente con los detalles de la reserva usando la plantilla "mensajeclientereserva".
    """
    if not numero:
        raise ValueError("No has actualizado tu WhatsApp")
    if whatsapp.startswith("57"):
        whatsapp = whatsapp[2:]
    whatsapp_api_token = os.getenv("WHATSAPP_API_TOKEN")
    if not whatsapp_api_token:
        raise ValueError("WHATSAPP_API_TOKEN no está definido en las variables de entorno.")
    
    url = "https://graph.facebook.com/v21.0/531912696676146/messages"
    body = {
        "messaging_product": "whatsapp",
        "recipient_type": "individual",
        "to": numero,
        "type": "template",
        "template": {
            "name": "mensajeclientereserva",
            "language": {"code": "es_CO"},
            "components": [
                {
                    "type": "header",
                    "parameters": [
                        {
                            "type": "location",
                            "location": {
                                "longitude": longitud,
                                "latitude": latitud,
                                "name": nombre_glamping_reservado,
                                "address": direccion_glamping,
                            },
                        }
                    ],
                },
                {
                    "type": "body",
                    "parameters": [
                        {"type": "text", "text": nombre_cliente},
                        {"type": "text", "text": codigo_reserva},
                        {"type": "text", "text": whatsapp},
                    ],
                },
            ],
        },
    }
    async with httpx.AsyncClient() as client:
        response = await client.post(
            url,
            json=body,
            headers={
                "Authorization": f"Bearer {whatsapp_api_token}",
                "Content-Type": "application/json",
            },
        )
        if response.status_code != 200:
            error_message = response.json().get("error", {}).get("message", "Error desconocido")
            raise Exception(f"Error al enviar mensaje de WhatsApp al cliente: {error_message}")

async def enviar_whatsapp_propietario(
    numero: str,
    nombre_propietario: str,
    nombre_glamping: str,
    fecha_inicio: str,
    fecha_fin: str,
    imagen_url: Optional[str] = "https://storage.googleapis.com/glamperos-imagenes/Imagenes/animal1.jpeg",
) -> None:
    """
    Envía un mensaje de WhatsApp al propietario con la confirmación de reserva usando la plantilla "confirmacionreserva".
    """
    if not numero:
        raise ValueError("No has actualizado tu WhatsApp.")
    if numero.startswith("57"):
        numero = numero[2:]
    whatsapp_api_token = os.getenv("WHATSAPP_API_TOKEN")
    if not whatsapp_api_token:
        raise ValueError("WHATSAPP_API_TOKEN no está definido en las variables de entorno.")
    
    url = "https://graph.facebook.com/v21.0/531912696676146/messages"
    body = {
        "messaging_product": "whatsapp",
        "recipient_type": "individual",
        "to": numero,
        "type": "template",
        "template": {
            "name": "confirmacionreserva",
            "language": {"code": "es_CO"},
            "components": [
                {
                    "type": "header",
                    "parameters": [
                        {"type": "image", "image": {"link": imagen_url}},
                    ],
                },
                {
                    "type": "body",
                    "parameters": [
                        {"type": "text", "text": nombre_propietario},
                        {"type": "text", "text": nombre_glamping},
                        {"type": "text", "text": fecha_inicio},
                        {"type": "text", "text": fecha_fin},
                    ],
                },
            ],
        },
    }
    async with httpx.AsyncClient() as client:
        response = await client.post(
            url,
            json=body,
            headers={
                "Authorization": f"Bearer {whatsapp_api_token}",
                "Content-Type": "application/json",
            },
        )
        if response.status_code != 200:
            error_message = response.json().get("error", {}).get("message", "Error desconocido")
            raise Exception(f"Error al enviar mensaje de WhatsApp al propietario: {error_message}")
