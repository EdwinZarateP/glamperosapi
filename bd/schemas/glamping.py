from pydantic import BaseModel, HttpUrl
from typing import Optional, List, Dict
from datetime import datetime

class SchemaGlamping(BaseModel):
    id: Optional[str] = None                           # ID convertido a string
    nombre: str                                        # Nombre del glamping
    ubicacion: Dict[str, float]                        # Latitud y longitud
    precio_noche: float                                # Precio por noche
    descripcion: str                                   # Descripción del glamping
    imagenes: List[HttpUrl]                            # Lista de URLs de imágenes
    video_youtube: Optional[HttpUrl] = None           # URL del video de YouTube (opcional)
    calificacion: Optional[float] = None              # Promedio de calificaciones (1.0 a 5.0)
    caracteristicas: List[str]                        # Características del glamping
    creado: Optional[datetime] = None                 # Fecha de creación (opcional)
