# rutas/whatsapp.py

from fastapi import Request, APIRouter
from fastapi.responses import PlainTextResponse, JSONResponse
import os
import httpx
import re
from datetime import datetime
from typing import Optional, Dict, Any

# ✅ Import correcto según tu estructura:
# /rutas/Funciones/chat_state.py
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
# DETECCIÓN URL PROPIEDAD
# =========================
PROP_REGEX = re.compile(r"glamperos\.com/propiedad/([a-f0-9]{24})", re.IGNORECASE)


def extraer_property_id(texto: str) -> Optional[str]:
    m = PROP_REGEX.search(texto or "")
    return m.group(1) if m else None


# =========================
# FECHAS (DD/MM/AAAA)
# =========================
FECHA_REGEX = re.compile(r"^\s*(\d{2})/(\d{2})/(\d{4})\s*$")


def parsear_fecha_ddmmaaaa(texto: str) -> Optional[datetime]:
    """
    Valida DD/MM/AAAA y convierte a datetime (sin hora).
    Retorna None si no es válido.
    """
    m = FECHA_REGEX.match(texto or "")
    if not m:
        return None
    dd, mm, yyyy = int(m.group(1)), int(m.group(2)), int(m.group(3))
    try:
        return datetime(yyyy, mm, dd)
    except ValueError:
        return None


def fechas_en_orden(llegada: datetime, salida: datetime) -> bool:
    return salida > llegada


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
# EXTRAER MENSAJE
# =========================
def extraer_mensaje(data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """
    Soporta:
    - text
    - interactive (button_reply / list_reply)
    """
    try:
        value = data["entry"][0]["changes"][0]["value"]
        mensajes = value.get("messages", [])
        if not mensajes:
            return None

        m = mensajes[0]
        msg_type = m.get("type")
        texto = ""

        if msg_type == "text":
            texto = ((m.get("text") or {}).get("body") or "").strip()

        elif msg_type == "interactive":
            inter = m.get("interactive") or {}
            itype = inter.get("type")

            if itype == "button_reply":
                br = inter.get("button_reply") or {}
                texto = (br.get("id") or br.get("title") or "").strip()

            elif itype == "list_reply":
                lr = inter.get("list_reply") or {}
                texto = (lr.get("id") or lr.get("title") or "").strip()

        return {
            "from": m.get("from"),
            "type": msg_type,
            "text": texto,
            "id": m.get("id"),
        }
    except Exception:
        return None


# =========================
# ENVIAR MENSAJES
# =========================
async def _post_graph(payload: Dict[str, Any]):
    if not WHATSAPP_API_TOKEN:
        print("⚠️ WHATSAPP_API_TOKEN no está definido.")
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
            print(f"❌ Error HTTPX WhatsApp: {e}")
            return

    if resp.status_code != 200:
        print(f"❌ Error WhatsApp: {resp.status_code} - {resp.text}")


async def enviar_texto(to: str, texto: str):
    payload = {
        "messaging_product": "whatsapp",
        "to": to,
        "type": "text",
        "text": {"preview_url": True, "body": texto},
    }
    await _post_graph(payload)


async def enviar_boton_ok(
    to: str,
    texto: str,
    button_id: str = "OK_INICIO",
    button_title: str = "OK",
):
    """
    Reply buttons: máximo 3.
    Aquí usamos 1 botón.
    """
    payload = {
        "messaging_product": "whatsapp",
        "to": to,
        "type": "interactive",
        "interactive": {
            "type": "button",
            "body": {"text": texto},
            "action": {
                "buttons": [
                    {"type": "reply", "reply": {"id": button_id, "title": button_title}}
                ]
            },
        },
    }
    await _post_graph(payload)


async def enviar_lista_fuente(to: str):
    """
    List message: ideal para 7 opciones.
    """
    payload = {
        "messaging_product": "whatsapp",
        "to": to,
        "type": "interactive",
        "interactive": {
            "type": "list",
            "body": {
                "text": (
                    "Mientras buscamos glampings disponibles para las fechas solicitadas, "
                    "cuéntanos cómo llegaste a nosotros 👇"
                )
            },
            "action": {
                "button": "Seleccionar",
                "sections": [
                    {
                        "title": "¿Cómo nos encontraste?",
                        "rows": [
                            {"id": "FUENTE_GOOGLE_ORGANICO", "title": "Buscando en Google"},
                            {"id": "FUENTE_GOOGLE_ADS", "title": "Publicidad en Google"},
                            {"id": "FUENTE_INSTAGRAM_ORGANICO", "title": "Instagram"},
                            {"id": "FUENTE_INSTAGRAM_ADS", "title": "Publicidad de Instagram"},
                            {"id": "FUENTE_MERCADOLIBRE", "title": "Mercadolibre"},
                            {"id": "FUENTE_REFERIDO", "title": "Me recomendó un amigo/familiar"},
                            {"id": "FUENTE_CLIENTE", "title": "Ya soy cliente"},
                        ],
                    }
                ],
            },
        },
    }
    await _post_graph(payload)


# =========================
# TEXTOS
# =========================
def texto_inicio_glamperos() -> str:
    return (
        "Gracias por comunicarte con *Glamperos* 🌿🏕️ Colombia 🇨🇴\n\n"
        "Dependiendo de tu consulta, te guiaremos con unas preguntas para ayudarte mejor.\n\n"
        "Este sistema no permite oír audios 🔇, por lo que deberás escribir las respuestas.\n\n"
        "Presiona *OK* para continuar."
    )


def pedir_ciudad() -> str:
    return "¡Genial! 😊 ¿En qué ciudad o zona buscas glamping?"


def pedir_fecha_llegada() -> str:
    return (
        "¿En qué fecha deseas *llegar*? 📅\n\n"
        "Escribe la fecha en formato *DD/MM/AAAA*.\n"
        "Ejemplo: *09/02/2024*"
    )


def pedir_fecha_salida() -> str:
    return (
        "¿En qué fecha deseas *salir*? 📅\n\n"
        "Escribe la fecha en formato *DD/MM/AAAA*.\n"
        "Ejemplo: *12/02/2024*"
    )


# =========================
# HELPERS (context merge)
# =========================
def _merge_context(prev: Dict[str, Any], new_fields: Dict[str, Any]) -> Dict[str, Any]:
    base = prev or {}
    base.update(new_fields or {})
    return base


# =========================
# WEBHOOK MENSAJES (POST)
# =========================
@ruta_whatsapp.post("/")
async def webhook(request: Request):
    data = await request.json()

    msg = extraer_mensaje(data)
    if not msg:
        return JSONResponse({"status": "ok"})

    numero = msg.get("from")
    texto = (msg.get("text") or "").strip()
    texto_lower = texto.lower().strip()

    # -------------------------
    # ATAJOS GLOBALES
    # -------------------------
    if texto_lower in ["menu", "menú", "inicio", "reiniciar", "cancelar", "reset"]:
        reset_state(numero)
        set_state(numero, "WAIT_OK", {})
        await enviar_boton_ok(numero, texto_inicio_glamperos(), button_id="OK_INICIO", button_title="OK")
        return JSONResponse({"status": "ok"})

    if texto_lower in ["humano", "asesor", "agente", "persona", "hablar con humano"]:
        # Modo "humano": el bot no guía más, solo deja un mensaje.
        set_state(numero, "HUMAN_HANDOFF", {"requested_at": datetime.utcnow().isoformat()})
        await enviar_texto(
            numero,
            "Entendido ✅\n\n"
            "Te pondremos en contacto con un asesor humano.\n"
            "Mientras tanto, por favor cuéntanos tu necesidad en 1 mensaje."
        )
        return JSONResponse({"status": "ok"})

    # Detectar link de propiedad en cualquier momento
    property_id = extraer_property_id(texto)
    if property_id:
        # Si llega con link, NO pedimos ciudad; vamos directo a fechas.
        set_state(numero, "ASK_ARRIVAL_DATE", {"property_id": property_id, "via": "link"})
        await enviar_texto(numero, "¡Perfecto! 🌿 Ya vi el link del glamping.")
        await enviar_texto(numero, pedir_fecha_llegada())
        return JSONResponse({"status": "ok"})

    # -------------------------
    # ESTADO ACTUAL
    # -------------------------
    estado = get_state(numero) or {"state": "WAIT_OK", "context": {}}
    state = estado.get("state") or "WAIT_OK"
    context = estado.get("context") or {}

    # Si está en handoff humano, el bot no debe “pisar” la conversación.
    if state == "HUMAN_HANDOFF":
        await enviar_texto(
            numero,
            "Gracias. Un asesor humano continuará la conversación.\n"
            "Si deseas volver al bot, escribe *menu*."
        )
        return JSONResponse({"status": "ok"})

    # -------------------------
    # FLUJO
    # -------------------------
    if state == "WAIT_OK":
        # Si presiona el botón OK (llega como id) o escribe ok
        if texto_lower in ["ok_inicio", "ok", "okay", "okey", "ok."]:
            set_state(numero, "ASK_CITY", {})
            await enviar_texto(numero, pedir_ciudad())
            return JSONResponse({"status": "ok"})

        # Si escribe cualquier cosa, lo encarrilamos con el OK
        await enviar_boton_ok(numero, texto_inicio_glamperos(), button_id="OK_INICIO", button_title="OK")
        set_state(numero, "WAIT_OK", {})
        return JSONResponse({"status": "ok"})

    if state == "ASK_CITY":
        # Guardar city
        set_state(numero, "ASK_ARRIVAL_DATE", {"city": texto, "via": "search"})
        await enviar_texto(numero, pedir_fecha_llegada())
        return JSONResponse({"status": "ok"})

    if state == "ASK_ARRIVAL_DATE":
        llegada = parsear_fecha_ddmmaaaa(texto)
        if not llegada:
            await enviar_texto(numero, "No pude leer la fecha 😅\n\n" + pedir_fecha_llegada())
            return JSONResponse({"status": "ok"})

        nuevo_contexto = _merge_context(context, {"arrival_date": llegada.strftime("%d/%m/%Y")})
        set_state(numero, "ASK_DEPARTURE_DATE", nuevo_contexto)
        await enviar_texto(numero, pedir_fecha_salida())
        return JSONResponse({"status": "ok"})

    if state == "ASK_DEPARTURE_DATE":
        salida = parsear_fecha_ddmmaaaa(texto)
        if not salida:
            await enviar_texto(numero, "No pude leer la fecha 😅\n\n" + pedir_fecha_salida())
            return JSONResponse({"status": "ok"})

        llegada_txt = context.get("arrival_date")
        llegada_dt = parsear_fecha_ddmmaaaa(llegada_txt) if llegada_txt else None
        if llegada_dt and not fechas_en_orden(llegada_dt, salida):
            await enviar_texto(
                numero,
                "La fecha de salida debe ser *posterior* a la fecha de llegada 🙂\n\n" + pedir_fecha_salida()
            )
            return JSONResponse({"status": "ok"})

        nuevo_contexto = _merge_context(context, {"departure_date": salida.strftime("%d/%m/%Y")})
        set_state(numero, "ASK_SOURCE", nuevo_contexto)
        await enviar_lista_fuente(numero)
        return JSONResponse({"status": "ok"})

    if state == "ASK_SOURCE":
        # Aquí texto llega como ID seleccionado (list_reply id)
        fuente = texto  # ej: FUENTE_GOOGLE_ORGANICO

        # Guardamos en estado (context) para que quede en Mongo "chat_states"
        nuevo_contexto = _merge_context(context, {"source": fuente})
        set_state(numero, "DONE", nuevo_contexto)

        await enviar_texto(
            numero,
            "Perfecto ✅\n\n"
            "Ya tengo la información 🙌\n"
            "En breve te compartimos opciones disponibles 🌄\n\n"
            "Si quieres reiniciar, escribe *menu*.\n"
            "Si deseas hablar con un humano, escribe *humano*."
        )
        return JSONResponse({"status": "ok"})

    # Fallback (si el estado quedó raro)
    reset_state(numero)
    set_state(numero, "WAIT_OK", {})
    await enviar_boton_ok(numero, texto_inicio_glamperos(), button_id="OK_INICIO", button_title="OK")
    return JSONResponse({"status": "ok"})
