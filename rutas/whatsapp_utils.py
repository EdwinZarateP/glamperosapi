# whatsapp_utils.py

import os
import httpx

PHONE_NUMBER_ID = os.getenv("WHATSAPP_PHONE_NUMBER_ID", "531912696676146")
GRAPH_URL = f"https://graph.facebook.com/v21.0/{PHONE_NUMBER_ID}/messages"

def _get_token():
    token = os.getenv("WHATSAPP_API_TOKEN")
    if not token:
        print("⚠️ WHATSAPP_API_TOKEN no está definido en las variables de entorno.")
        return None
    return token

async def _post_whatsapp(body: dict, error_prefix: str):
    token = _get_token()
    if not token:
        return

    async with httpx.AsyncClient() as client:
        resp = await client.post(
            GRAPH_URL,
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
            },
            json=body,
            timeout=10
        )

    if resp.status_code != 200:
        print(f"❌ {error_prefix}: {resp.text}")
    else:
        print(f"✅ {error_prefix}: enviado correctamente.")


async def enviar_whatsapp_cliente(
    numero: str,
    codigoReserva: str,
    whatsapp: str,
    nombreGlampingReservado: str,
    direccionGlamping: str,
    latitud: float,
    longitud: float,
    nombreCliente: str,
):
    try:
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
                                    "name": nombreGlampingReservado,
                                    "address": direccionGlamping,
                                },
                            },
                        ],
                    },
                    {
                        "type": "body",
                        "parameters": [
                            {"type": "text", "text": nombreCliente},
                            {"type": "text", "text": codigoReserva},
                            {"type": "text", "text": whatsapp},
                        ],
                    },
                ],
            },
        }

        await _post_whatsapp(body, "WhatsApp al cliente (reserva)")

        print("👉 Enviando WhatsApp al cliente con:")
        print(f"Nombre: {nombreCliente}, Código: {codigoReserva}, WhatsApp: {whatsapp}")
        print(f"Ubicación: {nombreGlampingReservado}, {direccionGlamping}, {latitud}, {longitud}")

    except Exception as e:
        print(f"🚨 Error al enviar mensaje de WhatsApp al cliente: {e}")


async def enviar_whatsapp_propietario(
    numero: str,
    nombrePropietario: str,
    nombreGlamping: str,
    fechaInicio: str,
    fechaFin: str,
    imagenUrl: str = "https://storage.googleapis.com/glamperos-imagenes/Imagenes/animal1.jpeg",
):
    try:
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
                            {"type": "image", "image": {"link": imagenUrl}},
                        ],
                    },
                    {
                        "type": "body",
                        "parameters": [
                            {"type": "text", "text": nombrePropietario},
                            {"type": "text", "text": nombreGlamping},
                            {"type": "text", "text": fechaInicio},
                            {"type": "text", "text": fechaFin},
                        ],
                    },
                ],
            },
        }

        await _post_whatsapp(body, "WhatsApp al propietario (confirmación reserva)")

    except Exception as e:
        print(f"🚨 Error al enviar mensaje de WhatsApp al propietario: {e}")


async def enviar_whatsapp_compra_bonos(
    numero: str,
    pdf: str,
    correo_cliente: str,
    valor_bono: str,
    imagenUrl: str = "https://storage.googleapis.com/glamperos-imagenes/Imagenes/animal1.jpeg",
):
    try:
        body = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": numero,
            "type": "template",
            "template": {
                "name": "notifica_compra_bonos",
                "language": {"code": "es"},
                "components": [
                    {
                        "type": "header",
                        "parameters": [
                            {"type": "image", "image": {"link": imagenUrl}},
                        ],
                    },
                    {
                        "type": "body",
                        "parameters": [
                            {"type": "text", "text": pdf},
                            {"type": "text", "text": valor_bono},
                            {"type": "text", "text": correo_cliente},
                        ],
                    },
                ],
            },
        }

        await _post_whatsapp(body, "WhatsApp compra bonos (notificación)")

    except Exception as e:
        print(f"🚨 Error al enviar mensaje de WhatsApp al cliente de bonos: {e}")
