import os
import httpx
import asyncio

async def enviar_whatsapp_cliente(
    numero: str,
    codigo_reserva: str,
    whatsapp: str,
    nombre_glamping_reservado: str,
    direccion_glamping: str,
    latitud: float,
    longitud: float,
    nombre_cliente: str,
):
    """
    Envía un mensaje de WhatsApp al cliente con los detalles de la reserva.
    """
    whatsapp_api_token = os.getenv("WHATSAPP_API_TOKEN")
    if not whatsapp_api_token:
        raise Exception("WHATSAPP_API_TOKEN no está definido en las variables de entorno.")
    # Remover el prefijo "57" si el número inicia con él
    if whatsapp.startswith("57"):
        whatsapp = whatsapp[2:]
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
                        },
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
            raise Exception(
                f"Error al enviar mensaje: {response.json().get('error', {}).get('message', 'Error desconocido')}"
            )

async def enviar_whatsapp_propietario(
    numero: str,
    nombre_propietario: str,
    nombre_glamping: str,
    fecha_inicio: str,
    fecha_fin: str,
    imagen_url: str = "https://storage.googleapis.com/glamperos-imagenes/Imagenes/animal1.jpeg",
):
    """
    Envía un mensaje de WhatsApp al propietario con la confirmación de la reserva.
    """
    whatsapp_api_token = os.getenv("WHATSAPP_API_TOKEN")
    if not whatsapp_api_token:
        raise Exception("WHATSAPP_API_TOKEN no está definido en las variables de entorno.")
    if numero.startswith("57"):
        numero = numero[2:]
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
            raise Exception(
                f"Error al enviar mensaje: {response.json().get('error', {}).get('message', 'Error desconocido')}"
            )
