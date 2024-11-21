from pydantic import BaseModel, HttpUrl
from typing import Optional, List, Dict
from datetime import datetime

class SchemaGlamping(BaseModel):
    id: Optional[str] = None
    nombre: str = "Glamping Aventura"                 # Nombre del glamping
    ubicacion: Dict[str, float] = {"lat": 4.711, "lng": -74.0721}  # Ubicación con latitud y longitud
    precio_noche: float = 200000                     # Precio por noche en COP
    descripcion: str = "Un lugar mágico en la montaña."  # Descripción del glamping
    imagenes: List[HttpUrl] = [                      # Lista de URLs de imágenes
        "https://example.com/img1.jpg", 
        "https://example.com/img2.jpg"
    ]
    video_youtube: Optional[HttpUrl] = None          # URL del video de YouTube (opcional)
    calificacion: Optional[float] = 4.5             # Promedio de calificaciones (1.0 a 5.0)
    caracteristicas: List[str] = ["WiFi", "Piscina", "Pet-friendly"]  # Características del glamping
    creado: Optional[datetime] = datetime.now()      # Fecha de creación
