# rutas/whatsapp.py

from fastapi import Request, APIRouter
from fastapi.responses import PlainTextResponse, JSONResponse
import os
import httpx
import re
from datetime import datetime
from typing import Optional, Dict, Any
from Funciones.whatsapp_leads import guardar_lead
from Funciones.chat_state import get_state, set_state, reset_state

# ✅ para wa.me text prefill
import urllib.parse

# =========================
# CONFIG
# =========================
VERIFY_TOKEN = os.getenv("WHATSAPP_VERIFY_TOKEN", "mitoken")
WHATSAPP_API_TOKEN = os.getenv("WHATSAPP_API_TOKEN")

PHONE_NUMBER_ID = os.getenv("WHATSAPP_PHONE_NUMBER_ID", "531912696676146")
GRAPH_URL = f"https://graph.facebook.com/v21.0/{PHONE_NUMBER_ID}/messages"

# ✅ Número del asesor humano (WhatsApp normal)
WHATSAPP_HUMAN_PHONE = (os.getenv("WHATSAPP_HUMAN_PHONE") or "").strip()

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

async def enviar_botones_zona(to: str):
    payload = {
        "messaging_product": "whatsapp",
        "to": to,
        "type": "interactive",
        "interactive": {
            "type": "button",
            "body": {"text": "¿En qué zona buscas glamping?"},
            "action": {
                "buttons": [
                    {
                        "type": "reply",
                        "reply": {"id": "ZONA_BOGOTA", "title": "Cerca a Bogotá"},
                    },
                    {
                        "type": "reply",
                        "reply": {"id": "ZONA_MEDELLIN", "title": "Cerca a Medellín"},
                    },
                    {
                        "type": "reply",
                        "reply": {
                            "id": "ZONA_BOYACA_SANTANDER",
                            "title": "Boyacá / Santander",
                        },
                    },
                ]
            },
        },
    }
    await _post_graph(payload)


async def enviar_lista_fuente(to: str):
    """
    List message: ideal para 5 opciones.
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
                            {"id": "FUENTE_GOOGLE_ADS", "title": "Publicidad en Google"},
                            {"id": "FUENTE_INSTAGRAM", "title": "Instagram"},
                            {"id": "FUENTE_TIKTOK", "title": "Tiktok"},
                            {
                                "id": "FUENTE_REFERIDO",
                                "title": "Me recomendó un amigo/familiar",
                            },
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
        "Bienvenido a *Glamperos* 🌿🏕️ Colombia 🇨🇴\n\n"
        "Dependiendo de tu consulta, te guiaremos con unas preguntas para ayudarte mejor.\n\n"
        "Este sistema no permite oír audios 🔇, por lo que deberás escribir las respuestas.\n\n"
        "Presiona *OK* para continuar."
    )


def pedir_ciudad() -> str:
    # (ya no se usa en el flujo principal, porque ahora usamos botones)
    return "¡Genial! 😊 ¿En qué ciudad o zona buscas glamping?"


def pedir_fecha_llegada() -> str:
    return (
        "¿En qué fecha deseas *llegar*? 📅\n\n"
        "Escribe la fecha en formato *DD/MM/AAAA*.\n"
        "Ejemplo: *09/01/2026*"
    )


def pedir_fecha_salida() -> str:
    return (
        "¿En qué fecha deseas *salir*? 📅\n\n"
        "Escribe la fecha en formato *DD/MM/AAAA*.\n"
        "Ejemplo: *12/01/2026*"
    )


# =========================
# HELPERS (context merge)
# =========================
def _merge_context(prev: Dict[str, Any], new_fields: Dict[str, Any]) -> Dict[str, Any]:
    base = prev or {}
    base.update(new_fields or {})
    return base


# =========================
# HELPERS (human redirect)
# =========================
def _resumen_contexto(ctx: Dict[str, Any]) -> str:
    city = ctx.get("city")
    arrival = ctx.get("arrival_date")
    departure = ctx.get("departure_date")
    source = ctx.get("source")
    property_id = ctx.get("property_id")

    partes = []
    if city:
        partes.append(f"Zona/Ciudad: {city}")
    if arrival:
        partes.append(f"Llegada: {arrival}")
    if departure:
        partes.append(f"Salida: {departure}")
    if property_id:
        partes.append(f"Glamping: https://glamperos.com/propiedad/{property_id}")
    if source:
        partes.append(f"Fuente: {source}")

    return " | ".join(partes) if partes else "Sin datos aún."


def _wa_me_link(phone_digits: str, text: str) -> str:
    # wa.me requiere dígitos y el texto URL-encoded
    return f"https://wa.me/{phone_digits}?text={urllib.parse.quote(text)}"


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
        await enviar_boton_ok(
            numero, texto_inicio_glamperos(), button_id="OK_INICIO", button_title="OK"
        )
        return JSONResponse({"status": "ok"})

    # -------------------------
    # ESTADO ACTUAL (antes de humano, para capturar contexto)
    # -------------------------
    estado = get_state(numero) or {"state": "WAIT_OK", "context": {}}
    state = estado.get("state") or "WAIT_OK"
    context = estado.get("context") or {}

    # -------------------------
    # HUMANO -> REDIRECCIÓN A WA.ME (WhatsApp normal)
    # -------------------------
    if texto_lower in ["humano", "asesor", "agente", "persona", "hablar con humano"]:
        if not WHATSAPP_HUMAN_PHONE:
            await enviar_texto(
                numero,
                "En este momento no tenemos un número de asesor configurado.\n"
                "Por favor intenta más tarde o escribe *menu*.",
            )
            return JSONResponse({"status": "ok"})

        resumen = _resumen_contexto(context)

        texto_prellenado = (
            "Hola 👋 Necesito ayuda de un asesor humano de Glamperos.\n"
            f"Mi WhatsApp: {numero}\n"
            f"Resumen: {resumen}\n\n"
            "Mi solicitud es:"
        )

        link = _wa_me_link(WHATSAPP_HUMAN_PHONE, texto_prellenado)

        await enviar_texto(
            numero,
            "Entendido ✅\n\n"
            "Para hablar con un asesor humano, escríbenos aquí 👇\n"
            f"{link}\n\n"
            "El mensaje ya va prellenado con tu información. Solo presiona *Enviar*.",
        )

        # Marcamos que fue redirigido (opcional)
        set_state(
            numero,
            "REDIRECTED_TO_HUMAN",
            _merge_context(context, {"redirected_at": datetime.utcnow().isoformat()}),
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

    # Si ya fue redirigido a humano, no seguimos molestando (solo permitir menu)
    if state == "REDIRECTED_TO_HUMAN":
        return JSONResponse({"status": "ok"})

    # -------------------------
    # FLUJO
    # -------------------------
    if state == "WAIT_OK":
        if texto_lower in ["ok_inicio", "ok", "okay", "okey", "ok."]:
            set_state(numero, "ASK_CITY", {})
            await enviar_botones_zona(numero)
            return JSONResponse({"status": "ok"})

        # Si escribe cualquier cosa, lo encarrilamos con el OK
        await enviar_boton_ok(
            numero, texto_inicio_glamperos(), button_id="OK_INICIO", button_title="OK"
        )
        set_state(numero, "WAIT_OK", {})
        return JSONResponse({"status": "ok"})

    if state == "ASK_CITY":
        # Si llega vacío o algo raro, volvemos a mostrar los botones
        if not (texto or "").strip():
            await enviar_botones_zona(numero)
            return JSONResponse({"status": "ok"})

        mapa_zonas = {
            "ZONA_BOGOTA": "Cerca a Bogotá",
            "ZONA_MEDELLIN": "Cerca a Medellín",
            "ZONA_BOYACA_SANTANDER": "Boyacá o Santander",
        }

        # Si viene de botón, texto será el ID
        zona = mapa_zonas.get(texto)

        # Fallback: si escribe manualmente
        zona_final = zona or texto

        set_state(
            numero,
            "ASK_ARRIVAL_DATE",
            {
                "city": zona_final,
                "city_code": texto if zona else None,
                "via": "search",
            },
        )

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
                "La fecha de salida debe ser *posterior* a la fecha de llegada 🙂\n\n"
                + pedir_fecha_salida(),
            )
            return JSONResponse({"status": "ok"})

        nuevo_contexto = _merge_context(context, {"departure_date": salida.strftime("%d/%m/%Y")})
        set_state(numero, "ASK_SOURCE", nuevo_contexto)
        await enviar_lista_fuente(numero)
        return JSONResponse({"status": "ok"})

    if state == "ASK_SOURCE":
        fuente = texto  # ej: FUENTE_GOOGLE_ADS
        nuevo_context = {**context, "source": fuente}

        # Guardar state final
        set_state(numero, "DONE", nuevo_context)

        # ✅ Guardar lead en otra colección
        lead_id = guardar_lead(
            phone=numero,
            context=nuevo_context,
            property_id=nuevo_context.get("property_id"),
        )
        print(f"✅ Lead guardado en whatsapp_leads: {lead_id}")

        await enviar_texto(
            numero,
            "Perfecto ✅\n\n"
            "Ya tengo la información 🙌\n"
            "En breve te compartimos opciones disponibles 🌄\n\n"
            "Si quieres reiniciar, escribe *menu*.",
        )
        return JSONResponse({"status": "ok"})

    # Fallback (si el estado quedó raro)
    reset_state(numero)
    set_state(numero, "WAIT_OK", {})
    await enviar_boton_ok(
        numero, texto_inicio_glamperos(), button_id="OK_INICIO", button_title="OK"
    )
    return JSONResponse({"status": "ok"})
