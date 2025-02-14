from fastapi import FastAPI, Request
from starlette.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response
import requests
import os
import re

# Importación de rutas
from rutas.usuarios import ruta_usuario
from rutas.glamping import ruta_glampings
from rutas.enviarCorreo import ruta_correos
from rutas.favoritos import ruta_favoritos
from rutas.evaluacion import ruta_evaluaciones
from rutas.mensajeria import ruta_mensajes
from rutas.whatsapp import ruta_whatsapp
from rutas.reserva import ruta_reserva

app = FastAPI()
app.title = "Glamperos"
app.version = "1.0"

# Token de Prerender.io
PRERENDER_TOKEN = os.getenv("PRERENDER_TOKEN", "KNtCIH1CTMX2w5K9XMT4")

# Lista de bots y palabras clave
BOT_KEYWORDS = [
    r"\b(bot|crawler|spider|Googlebot|Bingbot|Yahoo|Twitterbot|FacebookExternalHit|LinkedInBot|Slackbot|Prerender|HeadlessChrome)\b"
]

def is_bot(user_agent: str) -> bool:
    """Verifica si el User-Agent pertenece a un bot usando expresiones regulares."""
    if not user_agent:
        return False
    
    # 🔍 Detección con regex para capturar "Prerender" incluso dentro de paréntesis
    detected = any(re.search(pattern, user_agent, re.IGNORECASE) for pattern in BOT_KEYWORDS)
    
    print(f"🕵️‍♂️ Analizando User-Agent: {user_agent} → Bot detectado: {detected}")
    return detected

class PrerenderMiddleware(BaseHTTPMiddleware):
    """Middleware que intercepta bots y redirige a Prerender.io."""
    
    async def dispatch(self, request: Request, call_next):
        # Evitar bucle: si la solicitud viene de Prerender, no procesar
        if request.headers.get("X-Prerender"):
            return await call_next(request)
        
        user_agent = request.headers.get("User-Agent", "")
        url = request.url.path

        print(f"🔍 Recibida solicitud: {url} - User-Agent: {user_agent}")

        if is_bot(user_agent):
            prerender_url = f"https://service.prerender.io/{request.url}"
            headers = {"X-Prerender-Token": PRERENDER_TOKEN}

            print(f"🕷️ Redirigiendo a Prerender.io -> {prerender_url}")

            try:
                response = requests.get(prerender_url, headers=headers, timeout=5)
                print(f"🔍 Respuesta de Prerender.io: {response.status_code}")

                if response.status_code == 200:
                    return Response(content=response.content, media_type="text/html")
                else:
                    print(f"⚠️ Error en Prerender.io: {response.status_code}")
                    return Response(content=f"⚠️ Error en prerenderizado: {response.status_code}", status_code=500)

            except requests.exceptions.RequestException as e:
                print(f"❌ Error al conectar con Prerender.io: {str(e)}")
                return Response(content=f"❌ Error en prerender: {str(e)}", status_code=500)

        return await call_next(request)

# Agregar el middleware de Prerender.io antes que cualquier otro middleware
app.add_middleware(PrerenderMiddleware)

# Configuración de CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Middleware para agregar encabezados de seguridad
@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["Cross-Origin-Opener-Policy"] = "same-origin"
    return response

# Registro de rutas
app.include_router(ruta_usuario)
app.include_router(ruta_glampings)
app.include_router(ruta_correos)
app.include_router(ruta_favoritos)
app.include_router(ruta_evaluaciones)
app.include_router(ruta_mensajes)
app.include_router(ruta_whatsapp)
app.include_router(ruta_reserva)

@app.get("/", tags=["Home"])
async def root():
    return {"message": "Hola Glampero"}

# ✅ Debug: Ruta para verificar detección de bots
@app.get("/check-bot")
async def check_bot(request: Request):
    user_agent = request.headers.get("User-Agent", "")
    is_bot_detected = is_bot(user_agent)
    return {"user_agent": user_agent, "is_bot": is_bot_detected}

# ✅ Debug: Ruta para probar la integración con Prerender.io
@app.get("/debug-prerender")
async def debug_prerender():
    prerender_url = "https://service.prerender.io/https://glamperos.com"
    headers = {"X-Prerender-Token": PRERENDER_TOKEN}

    try:
        response = requests.get(prerender_url, headers=headers, timeout=5)
        return {"status": response.status_code, "content": response.text[:500]}
    except requests.exceptions.RequestException as e:
        return {"error": str(e)}

# Ejecuta el servidor
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=int(os.getenv("PORT", 10000)),
        log_level="info",
        timeout_keep_alive=120,  
        limit_concurrency=100,
    )