from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# Importación de rutas
from rutas.usuarios import ruta_usuario
from rutas.glamping import ruta_glampings

app = FastAPI()
app.title = "Glamperos"
app.version = "1"

# Configuración de CORS
app.add_middleware(
    CORSMiddleware,
    # allow_origins=["*"],  
    allow_origins=["*"],  
    allow_credentials=True,
    allow_methods=["*"],  # Permite todos los métodos (GET, POST, PUT, DELETE, etc.)
    allow_headers=["*"],  # Permite todos los encabezados
)

app.include_router(ruta_usuario)
app.include_router(ruta_glampings)


@app.get("/", tags=['Home'])
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
        limit_concurrency=10,   # Limita la concurrencia a 10 solicitudes simultáneas
    )


