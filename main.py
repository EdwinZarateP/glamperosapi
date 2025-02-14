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
app.version = "1.0"

# Configuración de CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Puedes restringir a dominios específicos si lo deseas
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Token de Prerender.io
PRERENDER_TOKEN = os.getenv("PRERENDER_TOKEN", "KNtCIH1CTMX2w5K9XMT4")

# Lista de bots que deben recibir la versión pre-renderizada
BOT_USER_AGENTS = [
    "Googlebot", "Bingbot", "Yahoo", "Twitterbot", "FacebookExternalHit",
    "LinkedInBot", "Slackbot"
]

# Lista de IPs permitidas para Prerender.io (actualizadas)
PRERENDER_IPS = [
    "54.241.5.235", "54.241.5.236", "54.241.5.237",
    "104.224.12.0/22", "103.207.40.0/22", "157.90.99.0/27",
    "159.69.172.160/27", "168.119.133.64/27", "188.34.148.112/28"
]

def is_bot(user_agent: str) -> bool:
    """Verifica si la petición proviene de un bot de búsqueda."""
    return any(bot in user_agent for bot in BOT_USER_AGENTS)

def is_prerender_request(request: Request) -> bool:
    """Verifica si la solicitud viene de Prerender.io según su IP o parámetros en la URL."""
    client_ip = request.client.host or ""
    return client_ip in PRERENDER_IPS or "_escaped_fragment_" in request.url.path

class PrerenderMiddleware(BaseHTTPMiddleware):
    """Middleware que intercepta bots y redirige a Prerender.io."""
    
    async def dispatch(self, request: Request, call_next):
        user_agent = request.headers.get("User-Agent", "")
        client_ip = request.client.host or ""

        print(f"🕵️‍♂️ Request recibida: {request.method} {request.url} - User-Agent: {user_agent} - IP: {client_ip}")
        
        if is_bot(user_agent) or is_prerender_request(request):
            prerender_url = f"https://service.prerender.io/{request.url}"
            headers = {"X-Prerender-Token": PRERENDER_TOKEN}

            print(f"🕷️ Prerender activado para {user_agent} - URL: {prerender_url}")

            try:
                response = requests.get(prerender_url, headers=headers, timeout=5)
                print(f"🔄 Respuesta de Prerender: {response.status_code}")

                if response.status_code == 200:
                    print(f"📢 Respondiendo con Prerender.io para: {request.url}")
                    return Response(content=response.content, media_type="text/html")
                else:
                    print(f"⚠️ Prerender.io devolvió estado {response.status_code}")
                    return Response(content="Error en Prerender.io", status_code=500)

            except requests.exceptions.RequestException as e:
                print(f"❌ Error al conectar con Prerender.io: {e}")
                return Response(content=f"Error en prerender: {str(e)}", status_code=500)

        return await call_next(request)

# Agregar el middleware de Prerender.io antes que cualquier otro middleware
app.add_middleware(PrerenderMiddleware)

# Middleware para loguear todas las peticiones y ver si Render recibe Prerender.io
@app.middleware("http")
async def log_all_requests(request: Request, call_next):
    user_agent = request.headers.get("User-Agent", "")
    client_ip = request.client.host or ""
    
    print(f"🚀 Request recibida: {request.method} {request.url} - User-Agent: {user_agent} - IP: {client_ip}")
    
    response = await call_next(request)
    
    print(f"📡 Respuesta enviada: {response.status_code}")
    
    return response

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
        port=int(os.getenv("PORT", 10000)),  # Usa el puerto que Render proporciona si existe
        log_level="info",
        timeout_keep_alive=120,  
        limit_concurrency=100,
    )