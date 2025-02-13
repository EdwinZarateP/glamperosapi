from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response
import requests
import os

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
app.version = "1"

# Configuración de CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Cambia "*" por dominios específicos si es necesario
    allow_credentials=True,
    allow_methods=["*"],  # Permite todos los métodos (GET, POST, PUT, DELETE, etc.)
    allow_headers=["*"],  # Permite todos los encabezados
)

# Token de Prerender.io
PRERENDER_TOKEN = os.getenv("PRERENDER_TOKEN", "KNtCIH1CTMX2w5K9XMT4")

# Lista de bots que deben recibir la versión pre-renderizada
BOT_USER_AGENTS = [
    "Googlebot", "Bingbot", "Yahoo", "Twitterbot", "FacebookExternalHit",
    "LinkedInBot", "Slackbot"
]

def is_bot(user_agent: str) -> bool:
    """Verifica si la petición proviene de un bot de búsqueda."""
    return any(bot in user_agent for bot in BOT_USER_AGENTS)

@app.middleware("http")
async def prerender_middleware(request: Request, call_next):
    """Intercepta peticiones de bots y las redirige a Prerender.io."""
    user_agent = request.headers.get("User-Agent", "")

    if is_bot(user_agent):
        prerender_url = f"https://service.prerender.io/{request.url.path}"
        headers = {"X-Prerender-Token": PRERENDER_TOKEN}

        try:
            response = requests.get(prerender_url, headers=headers)
            return Response(content=response.content, media_type="text/html")
        except requests.exceptions.RequestException:
            pass  # Si falla, servimos la versión normal

    return await call_next(request)

# Middleware para agregar encabezados de seguridad (COOP y COEP)
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

# Ejecuta el servidor
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=10000,
        log_level="info",
        timeout_keep_alive=120,  # Tiempo de espera extendido
        limit_concurrency=100,   # Limita la concurrencia a 100 solicitudes simultáneas
    )
