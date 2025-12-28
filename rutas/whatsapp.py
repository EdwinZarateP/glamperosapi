from fastapi import Request, APIRouter
from fastapi.responses import PlainTextResponse, JSONResponse
import os
import httpx
import re

from Funciones.chat_state import get_state, set_state, reset_state

# =========================
# CONFIG
# =========================
VERIFY_TOKEN = os.getenv("WHATSAPP_VERIFY_TOKEN", "mitoken")
WHATSAPP_API_TOKEN = os.getenv("WHATSAPP_API_TOKEN")

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
# DETECCIÓN DE URL GLAMPING
# =========================
PROP_REGEX = re.compile(r"glamperos\.com/propiedad/([a-f0-9]{24})", re.IGNORECASE)

def extraer_property_id(texto: str):
    m = PROP_REGEX.search(texto or "")
    return m.group(1) if m else None

# =========================
# VERIFICACIÓN WEBHOOK (GET)
# =========================
@ruta_whatsapp.get("/")
async def verify_webhook(request: Request):
    hub_challenge = request.query_params.get("hub.challenge")
    hub_verify_token = request.query_params.get("hub.verify_token")

    if hub_verify_token == VERIFY_TOKEN:
        return PlainTextResponse(str(hub_challenge))
    return PlainTextResponse("Error de verificación", status_code=403)

# =========================
# UTILIDADES
# =========================
def extraer_mensaje(data: dict):
    try:
        value = data["entry"][0]["changes"][0]["value"]
        mensajes = value.get("messages", [])
        if not mensajes:
            return None

        m = mensajes[0]
        return {
            "from": m.get("from"),
            "type": m.get("type"),
            "text": (m.get("text") or {}).get("body", "").strip(),
            "id": m.get("id"),
        }
    except Exception:
        return None

async def enviar_texto(to: str, texto: str):
    if not WHATSAPP_API_TOKEN:
        print("⚠️ WHATSAPP_API_TOKEN no está definido.")
        return

    body = {
        "messaging_product": "whatsapp",
        "to": to,
        "type": "text",
        "text": {"preview_url": True, "body": texto},
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
        print(f"❌ Error WhatsApp: {resp.text}")

def menu_principal():
    return (
        "Hola 👋 Soy Glamperos 🌿\n\n"
        "¿Qué te gustaría hacer?\n\n"
        "1️⃣ Buscar glampings\n"
        "2️⃣ Enviar link de un glamping\n"
        "3️⃣ Soporte\n\n"
        "Puedes escribir:\n"
        "• 'Quiero glampings en Guatavita'\n"
        "• pegar el link de una propiedad\n"
        "• o escribir *menu*"
    )

# =========================
# WEBHOOK MENSAJES (POST)
# =========================
@ruta_whatsapp.post("/")
async def webhook(request: Request):
    data = await request.json()
    msg = extraer_mensaje(data)
    if not msg:
        return JSONResponse({"status": "ok"})

    numero = msg["from"]
    texto = msg["text"]
    texto_lower = texto.lower()

    # Atajo global
    if texto_lower in ["menu", "menú", "inicio"]:
        reset_state(numero)
        await enviar_texto(numero, menu_principal())
        return JSONResponse({"status": "ok"})

    # Detectar link en cualquier punto
    property_id = extraer_property_id(texto)
    if property_id:
        set_state(numero, "ASK_PROPERTY_DATES", {"property_id": property_id})
        await enviar_texto(
            numero,
            "¡Perfecto! 🌿 Vi el link del glamping.\n\n"
            "¿Para qué fechas estás interesado?\n"
            "Ejemplo:\n"
            "📅 05/01/2026 - 06/01/2026"
        )
        return JSONResponse({"status": "ok"})

    estado_actual = get_state(numero)
    state = estado_actual["state"]
    context = estado_actual["context"]

    if state == "MENU":
        if texto_lower in ["hola", "hey", "buenas", "hello"]:
            await enviar_texto(numero, menu_principal())
            return JSONResponse({"status": "ok"})

        if "glamping" in texto_lower:
            set_state(numero, "ASK_CITY", {})
            await enviar_texto(numero, "¡Genial! 😊 ¿En qué ciudad o zona buscas glamping?")
            return JSONResponse({"status": "ok"})

        await enviar_texto(numero, menu_principal())
        return JSONResponse({"status": "ok"})

    if state == "ASK_CITY":
        set_state(numero, "ASK_DATES", {"city": texto})
        await enviar_texto(
            numero,
            f"Perfecto 📍 *{texto}*\n\n"
            "¿Para qué fechas?\n"
            "📅 05/01/2026 - 06/01/2026"
        )
        return JSONResponse({"status": "ok"})

    if state == "ASK_DATES":
        set_state(numero, "ASK_GUESTS", {**context, "dates": texto})
        await enviar_texto(numero, "¿Para cuántas personas sería la estadía?")
        return JSONResponse({"status": "ok"})

    if state == "ASK_GUESTS":
        reset_state(numero)
        await enviar_texto(
            numero,
            "Perfecto ✅\n\n"
            "Ya tengo la información 🙌\n"
            "En breve te compartimos opciones disponibles 🌄\n\n"
            "Escribe *menu* para volver al inicio."
        )
        return JSONResponse({"status": "ok"})

    if state == "ASK_PROPERTY_DATES":
        set_state(numero, "ASK_PROPERTY_GUESTS", {**context, "dates": texto})
        await enviar_texto(numero, "¿Para cuántas personas?")
        return JSONResponse({"status": "ok"})

    if state == "ASK_PROPERTY_GUESTS":
        reset_state(numero)
        await enviar_texto(
            numero,
            "¡Listo! 🌿\n\n"
            "Vamos a revisar disponibilidad y precios.\n"
            "Un asesor continuará contigo si es necesario 💬"
        )
        return JSONResponse({"status": "ok"})

    reset_state(numero)
    await enviar_texto(numero, menu_principal())
    return JSONResponse({"status": "ok"})
