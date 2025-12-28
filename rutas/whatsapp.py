# rutas/whatsapp.py

from fastapi import Request, APIRouter
from fastapi.responses import PlainTextResponse, JSONResponse
import os
import httpx
import re
from datetime import datetime, date
from typing import Optional, Dict, Any, List

from Funciones.whatsapp_leads import guardar_lead
from Funciones.chat_state import get_state, set_state, reset_state

import urllib.parse

# =========================
# CONFIG
# =========================
VERIFY_TOKEN = os.getenv("WHATSAPP_VERIFY_TOKEN", "mitoken")
WHATSAPP_API_TOKEN = os.getenv("WHATSAPP_API_TOKEN")

PHONE_NUMBER_ID = os.getenv("WHATSAPP_PHONE_NUMBER_ID", "531912696676146")
GRAPH_URL = f"https://graph.facebook.com/v21.0/{PHONE_NUMBER_ID}/messages"

# ✅ Número del asesor humano (WhatsApp normal) - SOLO dígitos con indicativo (ej: 573001112233)
WHATSAPP_HUMAN_PHONE = (os.getenv("WHATSAPP_HUMAN_PHONE") or "").strip()

# =========================
# LISTADOS (links)
# (Se envían uno a uno - sin esperas)
# =========================
GLAMPINGS_BOGOTA: List[str] = [
    "https://glamperos.com/propiedad/6897773f34f85956b85eab4a",
    "https://glamperos.com/propiedad/6897772434f85956b85eab49",
    "https://glamperos.com/propiedad/6827602386c9f5be06c6039d",
    "https://glamperos.com/propiedad/68a52a23d83e9028812edf7f",
    "https://glamperos.com/propiedad/682765b486c9f5be06c6039e",
    "https://glamperos.com/propiedad/682768c586c9f5be06c6039f",
    "https://glamperos.com/propiedad/68914d9634f85956b85eaa26",
    "https://glamperos.com/propiedad/68a11b84a0a1c9a8c809b5b5",
    "https://glamperos.com/propiedad/68a11b72a0a1c9a8c809b5b4",
    "https://glamperos.com/propiedad/67e629b7ed46c5cd5fcee9ad",
    "https://glamperos.com/propiedad/688902bb34f85956b85ea78f",
    "https://glamperos.com/propiedad/6822ac0a86c9f5be06c60394",
    "https://glamperos.com/propiedad/67c61158bf722ccb3a8e0b0b",
    "https://glamperos.com/propiedad/67d9bc8cb7356ca665a6eba0",
]

GLAMPINGS_MEDELLIN: List[str] = [
    "https://glamperos.com/propiedad/68f29613d60cc8baef6ad155",
    "https://glamperos.com/propiedad/6886794dbec77fc6ebf64ea0",
    "https://glamperos.com/propiedad/68154a82aadd248f50833fdd",
    "https://glamperos.com/propiedad/681c2a103193d38b54b152ed",
    "https://glamperos.com/propiedad/68978bcd34f85956b85eab59",
    "https://glamperos.com/propiedad/68113e4e0389b5eca382d8fb",
    "https://glamperos.com/propiedad/689fcc4634f85956b85ead6a",
    "https://glamperos.com/propiedad/681be9d51095b0469c0e3600",
]

GLAMPINGS_GUATAVITA: List[str] = [
    "https://glamperos.com/propiedad/68192171659173a779d344db",
    "https://glamperos.com/propiedad/67d6e09cbef08b81f7592b81",
    "https://glamperos.com/propiedad/6812cbd2ab954364e923a027",
    "https://glamperos.com/propiedad/67d996f6b7356ca665a6eb98",
    "https://glamperos.com/propiedad/67d9910bb7356ca665a6eb93",
    "https://glamperos.com/propiedad/6874622906ea14d27344d8bb",
    "https://glamperos.com/propiedad/67acfc3a4d16ab7cc77c4d5f",
    "https://glamperos.com/propiedad/68153b3eaadd248f50833fd9",
    "https://glamperos.com/propiedad/68153dfaaadd248f50833fda",
]

GLAMPINGS_BOYACA: List[str] = [
    "https://glamperos.com/propiedad/681a830f824e61ba124dbb6b",
    "https://glamperos.com/propiedad/6890e6e934f85956b85ea9fa",
    "https://glamperos.com/propiedad/6890df8134f85956b85ea9f7",
    "https://glamperos.com/propiedad/680160d8d90de3e7d2ddae49",
    "https://glamperos.com/propiedad/688926f934f85956b85ea7a1",
    "https://glamperos.com/propiedad/688910fb34f85956b85ea797",
    "https://glamperos.com/propiedad/685093c40695e3a851c2b1a4",
    "https://glamperos.com/propiedad/68153dfaaadd248f50833fda",
]

GLAMPINGS_SANTANDER: List[str] = [
    "https://glamperos.com/propiedad/681d2e645dc068dd1fdf4dc2",
    "https://glamperos.com/propiedad/681525b5aadd248f50833fd5",
    "https://glamperos.com/propiedad/681d2e3d5dc068dd1fdf4dc1",
    "https://glamperos.com/propiedad/681525a1aadd248f50833fd4",
    "https://glamperos.com/propiedad/6815257caadd248f50833fd2",
    "https://glamperos.com/propiedad/6806d872d90de3e7d2ddae51",
    "https://glamperos.com/propiedad/68080acf0389b5eca382d8eb",
    "https://glamperos.com/propiedad/68081af90389b5eca382d8ef",
    "https://glamperos.com/propiedad/68081af10389b5eca382d8ee",
    "https://glamperos.com/propiedad/680810930389b5eca382d8ec",
    "https://glamperos.com/propiedad/680813440389b5eca382d8ed",
    "https://glamperos.com/propiedad/67d4c397e6e0814d14ecd7d7"
]

MAPA_FUENTES = {
    "FUENTE_GOOGLE_ADS": "Google Ads",
    "FUENTE_INSTAGRAM": "Instagram",
    "FUENTE_TIKTOK": "TikTok",
    "FUENTE_REFERIDO": "Referido",
    "FUENTE_CHATGPT": "ChatGPT",
}

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


def es_hoy_o_futura(dt: datetime) -> bool:
    return dt.date() >= date.today()


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

        return {"from": m.get("from"), "type": msg_type, "text": texto, "id": m.get("id")}
    except Exception as e:
        print(f"❌ extraer_mensaje error: {e}")
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
    payload = {
        "messaging_product": "whatsapp",
        "to": to,
        "type": "interactive",
        "interactive": {
            "type": "button",
            "body": {"text": texto},
            "action": {"buttons": [{"type": "reply", "reply": {"id": button_id, "title": button_title}}]},
        },
    }
    await _post_graph(payload)


async def enviar_menu_zonas_numerado(to: str):
    """
    Menú por texto (sin listas interactivas, sin límite de 3).
    El usuario responde 1,2,3,4,5.
    """
    texto = (
        "¿En qué zona buscas glamping? 👇\n\n"
        "Responde con un número:\n"
        "1️⃣ Cerca a Bogotá\n"
        "2️⃣ Guatavita\n"
        "3️⃣ Cerca a Medellín\n"
        "4️⃣ Boyacá\n"
        "5️⃣ Santander\n\n"
        "Si quieres volver al inicio escribe *menu*."
    )
    await enviar_texto(to, texto)


async def enviar_lista_fuente(to: str):
    # Se deja lista interactiva porque aquí no estás pidiendo cambio,
    # pero si también la quieres numerada, se cambia igual que zonas.
    payload = {
        "messaging_product": "whatsapp",
        "to": to,
        "type": "interactive",
        "interactive": {
            "type": "list",
            "body": {"text": "Antes de enviarte opciones, cuéntanos cómo llegaste a nosotros 👇"},
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
    }
    await _post_graph(payload)


# =========================
# TEXTOS
# =========================
def texto_inicio_glamperos() -> str:
    return (
        "Bienvenido a *Glamperos* 🌿🏕️ Colombia 🇨🇴\n\n"
        "Te haremos unas preguntas rápidas para ayudarte mejor.\n\n"
        "Este sistema no permite oír audios 🔇, por lo que deberás escribir las respuestas.\n\n"
        "Presiona *OK* para continuar."
    )


def pedir_fecha_llegada() -> str:
    return (
        "¿En qué fecha deseas *llegar*? 📅\n\n"
        "Escribe la fecha en formato *DD/MM/AAAA*.\n"
        "Ejemplo: 09/01/2026"
    )


def pedir_fecha_salida() -> str:
    return (
        "¿En qué fecha deseas *salir*? 📅\n\n"
        "Escribe la fecha en formato *DD/MM/AAAA*.\n"
        "Ejemplo: 12/01/2026"
    )


async def enviar_links_uno_a_uno(to: str, titulo: str, links: List[str]):
    await enviar_texto(to, f"✨ *{titulo}* ✨")
    if not links:
        await enviar_texto(to, "Por ahora no tengo alojamientos cargados en esta zona. Puedes escribir *menu* para volver.")
        return
    for link in links:
        await enviar_texto(to, link)


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
    """
    - Sin "Mi WhatsApp"
    - Sin palabra "Resumen"
    - Fuente según lo que selecciona
    """
    partes = []

    arrival = ctx.get("arrival_date")
    departure = ctx.get("departure_date")

    if arrival and departure:
        partes.append(f"📅 Fechas: {arrival} → {departure}")
    elif arrival:
        partes.append(f"📅 Llegada: {arrival}")
    elif departure:
        partes.append(f"📅 Salida: {departure}")

    if ctx.get("city"):
        partes.append(f"📍 Zona: {ctx['city']}")

    if ctx.get("property_id"):
        partes.append(f"🏕️ Glamping: https://glamperos.com/propiedad/{ctx['property_id']}")

    fuente_id = ctx.get("source") or "DESCONOCIDA"
    fuente_legible = MAPA_FUENTES.get(fuente_id, fuente_id)
    partes.append(f"🔎 Fuente: {fuente_legible}")

    return "\n".join(partes) if partes else ""


def _wa_me_link(phone_digits: str, text: str) -> str:
    return f"https://wa.me/{phone_digits}?text={urllib.parse.quote(text)}"


def _link_humano_con_contexto(ctx: Dict[str, Any]) -> Optional[str]:
    if not WHATSAPP_HUMAN_PHONE:
        return None

    datos = _resumen_contexto(ctx)

    texto_prellenado = (
        "Hola 👋\n\n"
        "Te escribo desde el chat automático de Glamperos.\n\n"
        f"{datos}\n\n"
        "Quiero hablar con un asesor humano, por favor.\n"
        "Gracias 🙌"
    )

    return _wa_me_link(WHATSAPP_HUMAN_PHONE, texto_prellenado)


def _comando_humano(texto_lower: str) -> bool:
    return texto_lower in ["humano", "asesor", "agente", "persona", "hablar con humano"]


def _es_menu(texto_lower: str) -> bool:
    return texto_lower in ["menu", "menú", "inicio", "volver", "empezar", "reiniciar", "cancelar", "reset"]


# =========================
# WEBHOOK MENSAJES (POST)
# =========================
@ruta_whatsapp.post("/")
async def webhook(request: Request):
    try:
        data = await request.json()
    except Exception as e:
        print(f"❌ No pude leer JSON: {e}")
        return JSONResponse({"status": "ok"})

    msg = extraer_mensaje(data)
    if not msg:
        return JSONResponse({"status": "ok"})

    numero = msg.get("from")
    texto = (msg.get("text") or "").strip()
    texto_lower = texto.lower().strip()

    # -------------------------
    # ATAJOS GLOBALES
    # -------------------------
    if _es_menu(texto_lower):
        reset_state(numero)
        set_state(numero, "WAIT_OK", {})
        await enviar_boton_ok(numero, texto_inicio_glamperos(), button_id="OK_INICIO", button_title="OK")
        return JSONResponse({"status": "ok"})

    # -------------------------
    # ESTADO ACTUAL
    # -------------------------
    estado = get_state(numero) or {"state": "WAIT_OK", "context": {}}
    state = estado.get("state") or "WAIT_OK"
    context = estado.get("context") or {}

    # -------------------------
    # HUMANO (en cualquier momento)
    # -------------------------
    if _comando_humano(texto_lower):
        link = _link_humano_con_contexto(context)
        if not link:
            await enviar_texto(
                numero,
                "En este momento no tenemos un número de asesor configurado.\n"
                "Por favor intenta más tarde o escribe *menu*.",
            )
            return JSONResponse({"status": "ok"})

        await enviar_texto(
            numero,
            "Listo ✅\n\n"
            "Para hablar con un asesor humano, entra aquí 👇\n\n"
            f"{link}",
        )

        set_state(
            numero,
            "REDIRECTED_TO_HUMAN",
            _merge_context(context, {"redirected_at": datetime.utcnow().isoformat()}),
        )
        return JSONResponse({"status": "ok"})

    # -------------------------
    # Detectar link de propiedad en cualquier momento
    # -------------------------
    property_id = extraer_property_id(texto)
    if property_id:
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
            await enviar_menu_zonas_numerado(numero)
            return JSONResponse({"status": "ok"})

        await enviar_boton_ok(numero, texto_inicio_glamperos(), button_id="OK_INICIO", button_title="OK")
        set_state(numero, "WAIT_OK", {})
        return JSONResponse({"status": "ok"})

    if state == "ASK_CITY":
        if not texto:
            await enviar_menu_zonas_numerado(numero)
            return JSONResponse({"status": "ok"})

        # ✅ Selección numerada
        seleccion = texto_lower.strip()

        mapa_numero_zona = {
            "1": ("Cerca a Bogotá", GLAMPINGS_BOGOTA, "ZONA_BOGOTA"),
            "2": ("Guatavita", GLAMPINGS_GUATAVITA, "ZONA_GUATAVITA"),
            "3": ("Cerca a Medellín", GLAMPINGS_MEDELLIN, "ZONA_MEDELLIN"),
            "4": ("Boyacá", GLAMPINGS_BOYACA, "ZONA_BOYACA"),
            "5": ("Santander", GLAMPINGS_SANTANDER, "ZONA_SANTANDER"),
        }

        if seleccion not in mapa_numero_zona:
            await enviar_texto(
                numero,
                "No entendí la opción 😅\n\n"
                "Responde con un número:\n"
                "1️⃣ Cerca a Bogotá\n"
                "2️⃣ Guatavita\n"
                "3️⃣ Cerca a Medellín\n"
                "4️⃣ Boyacá\n"
                "5️⃣ Santander\n\n"
                "O escribe *menu* para volver al inicio."
            )
            return JSONResponse({"status": "ok"})

        zona_nombre, links, zona_code = mapa_numero_zona[seleccion]

        nuevo_contexto = _merge_context(
            context,
            {"city": zona_nombre, "city_code": zona_code, "via": "search"},
        )
        set_state(numero, "ASK_ARRIVAL_DATE", nuevo_contexto)

        # ✅ Enviar links uno a uno (sin espera)
        if links:
            await enviar_links_uno_a_uno(numero, f"Glampings {zona_nombre}", links)
        else:
            await enviar_texto(
                numero,
                f"Perfecto ✅ Elegiste: *{zona_nombre}*.\n\n"
                "Aún no tengo un listado fijo para esta zona.\n"
                "Si quieres, escribe *humano* y te atiende un asesor.\n"
                "O escribe *menu* para volver."
            )

        await enviar_texto(numero, pedir_fecha_llegada())
        return JSONResponse({"status": "ok"})

    if state == "ASK_ARRIVAL_DATE":
        llegada = parsear_fecha_ddmmaaaa(texto)
        if not llegada:
            await enviar_texto(numero, "No pude leer la fecha 😅\n\n" + pedir_fecha_llegada())
            return JSONResponse({"status": "ok"})

        if not es_hoy_o_futura(llegada):
            await enviar_texto(
                numero,
                "Esa fecha ya pasó 🙂\n\n"
                "Por favor escribe una fecha *de hoy en adelante*.\n\n"
                + pedir_fecha_llegada(),
            )
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

        if not es_hoy_o_futura(salida):
            await enviar_texto(
                numero,
                "Esa fecha ya pasó 🙂\n\n"
                "Por favor escribe una fecha *de hoy en adelante*.\n\n"
                + pedir_fecha_salida(),
            )
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
        # Fuente viene del ID de la lista (FUENTE_...)
        fuente_id = texto or "FUENTE_CHATGPT"
        nuevo_contexto = _merge_context(context, {"source": fuente_id})

        set_state(numero, "DONE", nuevo_contexto)

        lead_id = guardar_lead(
            phone=numero,
            context=nuevo_contexto,
            property_id=nuevo_contexto.get("property_id"),
        )
        print(f"✅ Lead guardado en whatsapp_leads: {lead_id}")

        link = _link_humano_con_contexto(nuevo_contexto)

        if link:
            await enviar_texto(
                numero,
                "Perfecto ✅ Ya tengo toda la información 🙌\n\n"
                "Si quieres hablar con un asesor humano ahora mismo, entra aquí 👇\n\n"
                f"{link}\n\n"
                "Si deseas volver al inicio, escribe *menu*.",
            )
            set_state(
                numero,
                "REDIRECTED_TO_HUMAN",
                _merge_context(nuevo_contexto, {"redirected_at": datetime.utcnow().isoformat()}),
            )
        else:
            await enviar_texto(
                numero,
                "Perfecto ✅ Ya tengo la información 🙌\n"
                "En breve te compartimos opciones disponibles 🌄\n\n"
                "Si quieres reiniciar, escribe *menu*.",
            )

        return JSONResponse({"status": "ok"})

    # Fallback
    reset_state(numero)
    set_state(numero, "WAIT_OK", {})
    await enviar_boton_ok(numero, texto_inicio_glamperos(), button_id="OK_INICIO", button_title="OK")
    return JSONResponse({"status": "ok"})
