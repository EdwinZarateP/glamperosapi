# rutas/whatsapp.py
# ==========================================================

from fastapi import Request, APIRouter
from fastapi.responses import PlainTextResponse, JSONResponse
import os
import httpx
import re
from datetime import datetime, date
from typing import Optional, Dict, Any

from Funciones.whatsapp_leads import guardar_lead
from Funciones.chat_state import get_state, set_state, reset_state

import urllib.parse

# ==========================================================
# CONFIGURACIÓN GENERAL
# ==========================================================

VERIFY_TOKEN = os.getenv("WHATSAPP_VERIFY_TOKEN", "mitoken")
WHATSAPP_API_TOKEN = os.getenv("WHATSAPP_API_TOKEN")

PHONE_NUMBER_ID = os.getenv("WHATSAPP_PHONE_NUMBER_ID", "531912696676146")
GRAPH_URL = f"https://graph.facebook.com/v21.0/{PHONE_NUMBER_ID}/messages"

WHATSAPP_HUMAN_PHONE = (os.getenv("WHATSAPP_HUMAN_PHONE") or "").strip()

# ==========================================================
# ROUTER
# ==========================================================

ruta_whatsapp = APIRouter(
    prefix="/whatsapp",
    tags=["whatsapp"],
    responses={404: {"message": "No encontrado"}},
)

# ==========================================================
# DETECCIÓN DE LINK DE PROPIEDAD
# ==========================================================

PROP_REGEX = re.compile(
    r"glamperos\.com/propiedad/([a-f0-9]{24})",
    re.IGNORECASE,
)

def extraer_property_id(texto: str) -> Optional[str]:
    if not texto:
        return None
    m = PROP_REGEX.search(texto)
    return m.group(1) if m else None

# ==========================================================
# MANEJO DE FECHAS
# ==========================================================

FECHA_REGEX = re.compile(r"^\s*(\d{2})/(\d{2})/(\d{4})\s*$")

def parsear_fecha_ddmmaaaa(texto: str) -> Optional[datetime]:
    if not texto:
        return None

    m = FECHA_REGEX.match(texto)
    if not m:
        return None

    dd, mm, yyyy = int(m.group(1)), int(m.group(2)), int(m.group(3))
    try:
        return datetime(yyyy, mm, dd)
    except ValueError:
        return None

def fecha_es_hoy_o_futura(fecha: datetime) -> bool:
    return fecha.date() >= date.today()

def fechas_en_orden(llegada: datetime, salida: datetime) -> bool:
    return salida > llegada

# ==========================================================
# VERIFICACIÓN WEBHOOK (GET)
# ==========================================================

@ruta_whatsapp.get("/")
async def verify_webhook(request: Request):
    hub_challenge = request.query_params.get("hub.challenge")
    hub_verify_token = request.query_params.get("hub.verify_token")

    if hub_verify_token == VERIFY_TOKEN:
        return PlainTextResponse(str(hub_challenge))

    return PlainTextResponse("Error de verificación", status_code=403)

# ==========================================================
# EXTRACCIÓN DE MENSAJES
# ==========================================================

def extraer_mensaje(data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    try:
        value = data["entry"][0]["changes"][0]["value"]
        mensajes = value.get("messages", [])

        if not mensajes:
            return None

        m = mensajes[0]
        texto = ""

        if m.get("type") == "text":
            texto = (m.get("text", {}).get("body") or "").strip()

        elif m.get("type") == "interactive":
            inter = m.get("interactive", {})
            if inter.get("type") == "button_reply":
                texto = inter["button_reply"].get("id", "")
            elif inter.get("type") == "list_reply":
                texto = inter["list_reply"].get("id", "")

        return {
            "from": m.get("from"),
            "text": texto,
            "id": m.get("id"),
        }

    except Exception:
        return None

# ==========================================================
# ENVÍO DE MENSAJES A WHATSAPP
# ==========================================================

async def _post_graph(payload: Dict[str, Any]):
    if not WHATSAPP_API_TOKEN:
        print("⚠️ WHATSAPP_API_TOKEN no definido")
        return

    async with httpx.AsyncClient() as client:
        try:
            resp = await client.post(
                GRAPH_URL,
                headers={
                    "Authorization": f"Bearer {WHATSAPP_API_TOKEN}",
                    "Content-Type": "application/json",
                },
                json=payload,
                timeout=20,
            )
        except Exception as e:
            print(f"❌ Error HTTP WhatsApp: {e}")
            return

    if resp.status_code != 200:
        print(f"❌ Error WhatsApp {resp.status_code}: {resp.text}")

async def enviar_texto(to: str, texto: str):
    await _post_graph({
        "messaging_product": "whatsapp",
        "to": to,
        "type": "text",
        "text": {
            "preview_url": True,
            "body": texto,
        },
    })

async def enviar_boton_ok(to: str, texto: str):
    await _post_graph({
        "messaging_product": "whatsapp",
        "to": to,
        "type": "interactive",
        "interactive": {
            "type": "button",
            "body": {"text": texto},
            "action": {
                "buttons": [
                    {"type": "reply", "reply": {"id": "OK", "title": "OK"}}
                ]
            },
        },
    })

async def enviar_botones_zona(to: str):
    await _post_graph({
        "messaging_product": "whatsapp",
        "to": to,
        "type": "interactive",
        "interactive": {
            "type": "button",
            "body": {"text": "¿En qué zona buscas glamping?"},
            "action": {
                "buttons": [
                    {"type": "reply", "reply": {"id": "Cerca a Bogotá", "title": "Cerca a Bogotá"}},
                    {"type": "reply", "reply": {"id": "Cerca a Medellín", "title": "Cerca a Medellín"}},
                    {"type": "reply", "reply": {"id": "Boyacá / Santander", "title": "Boyacá / Santander"}},
                ]
            },
        },
    })

async def enviar_lista_fuente(to: str):
    await _post_graph({
        "messaging_product": "whatsapp",
        "to": to,
        "type": "interactive",
        "interactive": {
            "type": "list",
            "body": {
                "text": "Antes de enviarte opciones, cuéntanos cómo llegaste a nosotros 👇"
            },
            "action": {
                "button": "Seleccionar",
                "sections": [
                    {
                        "title": "¿Cómo nos encontraste?",
                        "rows": [
                            {"id": "FUENTE_GOOGLE_ADS", "title": "Google Ads"},
                            {"id": "FUENTE_INSTAGRAM", "title": "Instagram"},
                            {"id": "FUENTE_TIKTOK", "title": "TikTok"},
                            {"id": "FUENTE_REFERIDO", "title": "Referido"},
                            {"id": "FUENTE_CHATGPT", "title": "ChatGPT"},
                        ],
                    }
                ],
            },
        },
    })

# ==========================================================
# TEXTOS BASE
# ==========================================================

def texto_inicio_glamperos() -> str:
    return (
        "Bienvenido a *Glamperos* 🌿🏕️ Colombia 🇨🇴\n\n"
        "Te haremos unas preguntas rápidas para ayudarte mejor.\n\n"
        "Este sistema no permite audios 🔇\n\n"
        "Presiona *OK* para continuar."
    )

def pedir_fecha_llegada() -> str:
    return (
        "¿En qué fecha deseas *llegar*? 📅\n\n"
        "Formato *DD/MM/AAAA*\n"
        "Ejemplo: 09/01/2026"
    )

def pedir_fecha_salida() -> str:
    return (
        "¿En qué fecha deseas *salir*? 📅\n\n"
        "Formato *DD/MM/AAAA*\n"
        "Ejemplo: 12/01/2026"
    )

# ==========================================================
# HELPERS DE CONTEXTO
# ==========================================================

def _merge_context(prev: Dict[str, Any], new_fields: Dict[str, Any]) -> Dict[str, Any]:
    base = prev or {}
    base.update(new_fields or {})
    return base

def _resumen_contexto(ctx: Dict[str, Any]) -> str:
    partes = []

    if ctx.get("arrival_date") and ctx.get("departure_date"):
        partes.append(f"📅 {ctx['arrival_date']} → {ctx['departure_date']}")

    if ctx.get("city"):
        partes.append(f"📍 {ctx['city']}")

    if ctx.get("property_id"):
        partes.append(f"🏕️ https://glamperos.com/propiedad/{ctx['property_id']}")

    partes.append("🤖 Fuente: CHAT_GPT")

    return "\n".join(partes)

def _link_humano_con_contexto(ctx: Dict[str, Any]) -> Optional[str]:
    if not WHATSAPP_HUMAN_PHONE:
        return None

    texto = (
        "Hola 👋\n\n"
        "Te escribo desde el chat automático de Glamperos.\n\n"
        f"{_resumen_contexto(ctx)}\n\n"
        "Gracias 🙌"
    )

    return f"https://wa.me/{WHATSAPP_HUMAN_PHONE}?text={urllib.parse.quote(texto)}"

# ==========================================================
# WEBHOOK PRINCIPAL (POST)
# ==========================================================

@ruta_whatsapp.post("/")
async def webhook(request: Request):
    data = await request.json()
    msg = extraer_mensaje(data)

    if not msg:
        return JSONResponse({"status": "ok"})

    numero = msg["from"]
    texto = (msg["text"] or "").strip()
    texto_lower = texto.lower()

    # -----------------------
    # COMANDOS GLOBALES
    # -----------------------

    if texto_lower in ["menu", "inicio", "reiniciar"]:
        reset_state(numero)
        set_state(numero, "WAIT_OK", {})
        await enviar_boton_ok(numero, texto_inicio_glamperos())
        return JSONResponse({"status": "ok"})

    estado = get_state(numero) or {"state": "WAIT_OK", "context": {}}
    state = estado["state"]
    ctx = estado["context"]

    # -----------------------
    # HUMANO
    # -----------------------

    if texto_lower in ["humano", "asesor", "persona"]:
        link = _link_humano_con_contexto(ctx)
        await enviar_texto(
            numero,
            "Habla con un asesor humano aquí 👇\n\n" + link
        )
        set_state(numero, "REDIRECTED_TO_HUMAN", ctx)
        return JSONResponse({"status": "ok"})

    # -----------------------
    # LINK DE PROPIEDAD
    # -----------------------

    prop_id = extraer_property_id(texto)
    if prop_id:
        set_state(numero, "ASK_ARRIVAL_DATE", {"property_id": prop_id})
        await enviar_texto(numero, pedir_fecha_llegada())
        return JSONResponse({"status": "ok"})

    if state == "WAIT_OK":
        set_state(numero, "ASK_CITY", {})
        await enviar_botones_zona(numero)
        return JSONResponse({"status": "ok"})

    if state == "ASK_CITY":
        set_state(numero, "ASK_ARRIVAL_DATE", {"city": texto})
        await enviar_texto(numero, pedir_fecha_llegada())
        return JSONResponse({"status": "ok"})

    if state == "ASK_ARRIVAL_DATE":
        llegada = parsear_fecha_ddmmaaaa(texto)
        if not llegada or not fecha_es_hoy_o_futura(llegada):
            await enviar_texto(
                numero,
                "La fecha debe ser *hoy o futura* 🙂\n\n" + pedir_fecha_llegada()
            )
            return JSONResponse({"status": "ok"})

        set_state(
            numero,
            "ASK_DEPARTURE_DATE",
            _merge_context(ctx, {"arrival_date": llegada.strftime("%d/%m/%Y")}),
        )
        await enviar_texto(numero, pedir_fecha_salida())
        return JSONResponse({"status": "ok"})

    if state == "ASK_DEPARTURE_DATE":
        salida = parsear_fecha_ddmmaaaa(texto)
        llegada = parsear_fecha_ddmmaaaa(ctx.get("arrival_date"))

        if not salida or not fechas_en_orden(llegada, salida):
            await enviar_texto(
                numero,
                "La salida debe ser posterior a la llegada 🙂\n\n" + pedir_fecha_salida()
            )
            return JSONResponse({"status": "ok"})

        nuevo_ctx = _merge_context(
            ctx,
            {
                "departure_date": salida.strftime("%d/%m/%Y"),
                "source": "CHAT_GPT",
            },
        )

        guardar_lead(
            phone=numero,
            context=nuevo_ctx,
            property_id=nuevo_ctx.get("property_id"),
        )

        link = _link_humano_con_contexto(nuevo_ctx)
        await enviar_texto(
            numero,
            "Perfecto ✅\n\n"
            "Habla con un asesor humano aquí 👇\n\n" + link
        )

        set_state(numero, "REDIRECTED_TO_HUMAN", nuevo_ctx)
        return JSONResponse({"status": "ok"})

    return JSONResponse({"status": "ok"})
