from pydantic import BaseModel, HttpUrl
from typing import Optional, List, Dict
from datetime import datetime

class ModeloGlamping(BaseModel):
    id: Optional[str] = None                          # ID generado por MongoDB
    nombre: str                                       # Nombre del glamping
    ubicacion: Dict[str, float]                       # Ubicación (latitud y longitud)
    precio_noche: float                               # Precio por noche
    descripcion: str                                  # Descripción
    imagenes: List[str]                               # Lista de rutas/URLs de imágenes
    video_youtube: Optional[str] = None              # Video de YouTube (opcional)
    calificacion: Optional[float] = 0.0              # Promedio de calificaciones
    caracteristicas: List[str]                       # Características
    ciudad_departamento: str                         # Ciudad y departamento del glamping
    creado: Optional[datetime] = datetime.now()      # Fecha de creación por defecto
