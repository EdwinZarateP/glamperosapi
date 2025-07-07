from fastapi import FastAPI, Request
from starlette.middleware.cors import CORSMiddleware
import os

from dotenv import load_dotenv
load_dotenv(override=True)

# Verificar variables necesarias
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
MONGO_URI = os.getenv("MONGO_URI")


if not OPENAI_API_KEY or not MONGO_URI:
    raise ValueError("❌ ERROR: Las variables DEEPSEEK_API_KEY o MONGO_URI no están configuradas.")

# Importación de rutas
from rutas.usuarios import ruta_usuario
from rutas.glamping import ruta_glampings
from rutas.enviarCorreo import ruta_correos
from rutas.favoritos import ruta_favoritos
from rutas.evaluacion import ruta_evaluaciones
from rutas.mensajeria import ruta_mensajes
from rutas.whatsapp import ruta_whatsapp
from rutas.reserva import ruta_reserva
from rutas.wompi import ruta_wompi
from rutas.openai import ruta_openai
from rutas.ical import  ruta_ical
from rutas.localizaciones import  ruta_localizaciones
from rutas.visitas import ruta_visitas
from rutas.bonos import ruta_bonos

app = FastAPI(title="Glamperos", version="1.0")

# Configuración de CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:4000",
        "https://tudominiofrontend.com",
        "*"
    ], 
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Middleware de seguridad
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
app.include_router(ruta_wompi)
app.include_router(ruta_openai)
app.include_router(ruta_ical)
app.include_router(ruta_localizaciones)
app.include_router(ruta_visitas)
app.include_router(ruta_bonos)

@app.get("/", tags=["Home"])
async def root():
    return {"message": "Hola Glampero"}
