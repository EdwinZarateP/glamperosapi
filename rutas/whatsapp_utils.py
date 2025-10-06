import os
import httpx

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
        whatsappApiToken = os.getenv("WHATSAPP_API_TOKEN")
        if not whatsappApiToken:
            print("⚠️ WHATSAPP_API_TOKEN no está definido en las variables de entorno.")
            return
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
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                url,
                headers={
                    "Authorization": f"Bearer {whatsappApiToken}",
                    "Content-Type": "application/json",
                },
                json=body,
                timeout=10
            )
        if resp.status_code != 200:
            print(f"❌ Error al enviar WhatsApp al cliente: {resp.text}")
        else:
            print("👉 Enviando WhatsApp al cliente con:")
            print(f"Nombre: {nombreCliente}, Código: {codigoReserva}, WhatsApp: {whatsapp}")
            print(f"Ubicación: {nombreGlampingReservado}, {direccionGlamping}, {latitud}, {longitud}")
            print("✅ WhatsApp enviado al cliente correctamente.")
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
        whatsappApiToken = os.getenv("WHATSAPP_API_TOKEN")
        if not whatsappApiToken:
            print("⚠️ WHATSAPP_API_TOKEN no está definido en las variables de entorno.")
            return
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
                            {
                                "type": "image",
                                "image": {"link": imagenUrl},
                            },
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
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                url,
                headers={
                    "Authorization": f"Bearer {whatsappApiToken}",
                    "Content-Type": "application/json",
                },
                json=body,
                timeout=10
            )
        if resp.status_code != 200:
            print(f"❌ Error al enviar WhatsApp al propietario: {resp.text}")
        else:
            print("✅ WhatsApp enviado al propietario correctamente.")
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
        whatsappApiToken = os.getenv("WHATSAPP_API_TOKEN")
        if not whatsappApiToken:
            print("⚠️ WHATSAPP_API_TOKEN no está definido en las variables de entorno.")
            return
        url = "https://graph.facebook.com/v21.0/531912696676146/messages"
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
                            {
                                "type": "image",
                                "image": {"link": imagenUrl},
                            },
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
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                url,
                headers={
                    "Authorization": f"Bearer {whatsappApiToken}",
                    "Content-Type": "application/json",
                },
                json=body,
                timeout=10
            )
        if resp.status_code != 200:
            print(f"❌ Error al enviar WhatsApp al cliente de bonos: {resp.text}")
        else:
            print("✅ WhatsApp enviado al propietario correctamente.")
    except Exception as e:
        print(f"🚨 Error al enviar mensaje de WhatsApp al cliente de bonos: {e}")
