from fastapi import Request, APIRouter
from fastapi.responses import PlainTextResponse, JSONResponse
import os
import httpx

# =========================
# CONFIG
# =========================
VERIFY_TOKEN = os.getenv("WHATSAPP_VERIFY_TOKEN", "mitoken")
WHATSAPP_API_TOKEN = os.getenv("WHATSAPP_API_TOKEN")

# ⚠️ Debe ser tu PHONE_NUMBER_ID (el mismo que usas para enviar templates)
PHONE_NUMBER_ID = os.getenv("WHATSAPP_PHONE_NUMBER_ID", "531912696676146")
GRAPH_URL = f"https://graph.facebook.com/v21.0/{PHONE_NUMBER_ID}/messages"

# =========================
# ROUTER
# =========================
ruta_whatsapp = APIRouter(
    prefix="/whatsapp",
    tags=["whatsapp"],
    responses={404: {"message": "No encontrado"}},
)

# =========================
# VERIFICACIÓN WEBHOOK (GET)
# =========================
@ruta_whatsapp.get("/")
async def verify_webhook(request: Request):
    hub_challenge = request.query_params.get("hub.challenge")
    hub_verify_token = request.query_params.get("hub.verify_token")

    if hub_verify_token == VERIFY_TOKEN:
        # Meta espera texto plano (sin comillas)
        return PlainTextResponse(str(hub_challenge))

    return PlainTextResponse("Error de verificación", status_code=403)


# =========================
# UTILIDADES
# =========================
def extraer_mensaje(data: dict):
    """
    Extrae el primer mensaje entrante del payload de Meta.
    Retorna None si es un evento sin mensajes (por ejemplo, status updates).
    """
    try:
        value = data["entry"][0]["changes"][0]["value"]
        mensajes = value.get("messages", [])
        if not mensajes:
            return None

        m = mensajes[0]
        return {
            "from": m.get("from"),  # número del usuario
            "type": m.get("type"),
            "text": (m.get("text") or {}).get("body", "").strip(),
            "id": m.get("id"),
        }
    except Exception:
        return None


async def enviar_texto(to: str, texto: str):
    """
    Responde con mensaje normal (session message).
    Solo funciona si el usuario te escribió dentro de las últimas 24h.
    """
    if not WHATSAPP_API_TOKEN:
        print("⚠️ WHATSAPP_API_TOKEN no está definido en variables de entorno.")
        return

    body = {
        "messaging_product": "whatsapp",
        "to": to,
        "type": "text",
        "text": {"body": texto},
    }

    async with httpx.AsyncClient() as client:
        resp = await client.post(
            GRAPH_URL,
            headers={
                "Authorization": f"Bearer {WHATSAPP_API_TOKEN}",
                "Content-Type": "application/json",
            },
            json=body,
            timeout=10,
        )

    if resp.status_code != 200:
        print(f"❌ Error al responder por WhatsApp: {resp.text}")


# =========================
# WEBHOOK MENSAJES (POST)
# =========================
@ruta_whatsapp.post("/")
async def webhook(request: Request):
    data = await request.json()
    print("📩 Webhook recibido:", data)

    msg = extraer_mensaje(data)
    if not msg:
        # Puede ser status updates u otros eventos sin 'messages'
        return JSONResponse({"status": "ok"})

    numero = msg["from"]
    texto = (msg["text"] or "").lower()

    # BOT BÁSICO (puedes crecerlo luego con estados en Mongo)
    if texto in ["hola", "buenas", "hey"]:
        await enviar_texto(
            numero,
            "Hola 👋 Soy Glamperos 🌿\n\n"
            "1️⃣ Buscar glamping\n"
            "2️⃣ Soporte\n"
            "3️⃣ Mis reservas"
        )
    elif texto == "1":
        await enviar_texto(numero, "Perfecto 🌄 ¿En qué ciudad buscas glamping?")
    elif texto == "2":
        await enviar_texto(numero, "Cuéntame tu problema o tu código de reserva 🙏")
    elif texto == "3":
        await enviar_texto(numero, "Pásame tu correo o tu código de reserva para buscarla.")
    else:
        await enviar_texto(numero, "No entendí 😅 Escribe *hola* para ver el menú.")

    return JSONResponse({"status": "ok"})
