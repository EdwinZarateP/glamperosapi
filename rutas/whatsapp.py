# rutas/whatsapp.py

from fastapi import Request, APIRouter
from fastapi.responses import PlainTextResponse, JSONResponse
import os
import httpx
import re
from typing import Optional, Dict, Any

# ✅ IMPORT CORRECTO (porque "Funciones" está dentro de "rutas")
# Requisitos:
# - debe existir: rutas/__init__.py
# - debe existir: rutas/Funciones/__init__.py
from Funciones.chat_state import get_state, set_state, reset_state


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
# DETECCIÓN DE URL GLAMPING
# =========================
PROP_REGEX = re.compile(r"glamperos\.com/propiedad/([a-f0-9]{24})", re.IGNORECASE)


def extraer_property_id(texto: str) -> Optional[str]:
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
        # Meta espera texto plano (sin comillas)
        return PlainTextResponse(str(hub_challenge))

    return PlainTextResponse("Error de verificación", status_code=403)


# =========================
# UTILIDADES
# =========================
def extraer_mensaje(data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """
    Extrae el primer mensaje entrante del payload de Meta.
    Retorna None si es un evento sin mensajes (por ejemplo status updates).
    """
    try:
        value = data["entry"][0]["changes"][0]["value"]
        mensajes = value.get("messages", [])
        if not mensajes:
            return None

        m = mensajes[0]
        msg_type = m.get("type")

        # Solo manejamos texto por ahora
        text_body = ""
        if msg_type == "text":
            text_body = ((m.get("text") or {}).get("body") or "").strip()

        return {
            "from": m.get("from"),  # número del usuario
            "type": msg_type,
            "text": text_body,
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
            timeout=20,
        )

    if resp.status_code != 200:
        print(f"❌ Error WhatsApp: {resp.status_code} - {resp.text}")


def menu_principal() -> str:
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

    # Si no es texto, responde con guía
    if msg["type"] != "text" or not (msg.get("text") or "").strip():
        await enviar_texto(
            numero,
            "Por ahora solo puedo leer mensajes de texto 🙂\n\n"
            "Escribe *menu* para ver opciones.",
        )
        return JSONResponse({"status": "ok"})

    texto = msg["text"]
    texto_lower = texto.lower().strip()

    # Atajos globales
    if texto_lower in ["menu", "menú", "inicio", "reiniciar", "cancelar"]:
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
            "📅 05/01/2026 - 06/01/2026",
        )
        return JSONResponse({"status": "ok"})

    estado_actual = get_state(numero) or {"state": "MENU", "context": {}}
    state = estado_actual.get("state", "MENU")
    context = estado_actual.get("context", {}) or {}

    # -------------------------
    # STATE MACHINE
    # -------------------------
    if state == "MENU":
        if texto_lower in ["hola", "hey", "buenas", "hello"]:
            await enviar_texto(numero, menu_principal())
            return JSONResponse({"status": "ok"})

        if texto_lower == "1" or "glamping" in texto_lower or "glampings" in texto_lower:
            set_state(numero, "ASK_CITY", {})
            await enviar_texto(numero, "¡Genial! 😊 ¿En qué ciudad o zona buscas glamping?")
            return JSONResponse({"status": "ok"})

        if texto_lower == "2":
            await enviar_texto(numero, "Pega aquí el link del glamping 👇")
            return JSONResponse({"status": "ok"})

        if texto_lower == "3" or "soporte" in texto_lower:
            set_state(numero, "SUPPORT", {})
            await enviar_texto(numero, "Cuéntame tu problema o tu código de reserva 🙏")
            return JSONResponse({"status": "ok"})

        await enviar_texto(numero, menu_principal())
        return JSONResponse({"status": "ok"})

    if state == "ASK_CITY":
        set_state(numero, "ASK_DATES", {"city": texto})
        await enviar_texto(
            numero,
            f"Perfecto 📍 *{texto}*\n\n"
            "¿Para qué fechas?\n"
            "📅 05/01/2026 - 06/01/2026",
        )
        return JSONResponse({"status": "ok"})

    if state == "ASK_DATES":
        set_state(numero, "ASK_GUESTS", {**context, "dates": texto})
        await enviar_texto(numero, "¿Para cuántas personas sería la estadía?")
        return JSONResponse({"status": "ok"})

    if state == "ASK_GUESTS":
        # Aquí solo reseteas el estado (temporal).
        # Si quieres “verlo en base”, debes guardarlo en otra colección (leads).
        reset_state(numero)
        await enviar_texto(
            numero,
            "Perfecto ✅\n\n"
            "Ya tengo la información 🙌\n"
            "En breve te compartimos opciones disponibles 🌄\n\n"
            "Escribe *menu* para volver al inicio.",
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
            "Un asesor continuará contigo si es necesario 💬",
        )
        return JSONResponse({"status": "ok"})

    if state == "SUPPORT":
        reset_state(numero)
        await enviar_texto(
            numero,
            "Gracias 🙏 Ya registré tu solicitud de soporte.\n"
            "Un asesor te contactará.\n\n"
            "Escribe *menu* para volver al inicio.",
        )
        return JSONResponse({"status": "ok"})

    # Fallback
    reset_state(numero)
    await enviar_texto(numero, menu_principal())
    return JSONResponse({"status": "ok"})
