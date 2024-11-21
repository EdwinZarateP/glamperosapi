from pydantic import BaseModel, HttpUrl
from typing import Optional, List
from datetime import datetime

class ModeloGlamping(BaseModel):
    id: Optional[str] = None  # ID generado por MongoDB
    nombre: str               # Nombre del glamping
    ubicacion: dict           # Ubicación del glamping (latitud y longitud)
    precio_noche: float       # Precio por noche en COP
    descripcion: str          # Descripción detallada del glamping
    imagenes: List[HttpUrl]   # URLs de imágenes del glamping
    video_youtube: Optional[HttpUrl] = None  # URL del video de YouTube (opcional)
    calificacion: Optional[float] = 0.0  # Promedio de calificaciones (1.0 a 5.0)
    caracteristicas: List[str]  # Lista de características (ej. WiFi, piscina, etc.)
    creado: Optional[datetime] = datetime.now()  # Fecha de creación
