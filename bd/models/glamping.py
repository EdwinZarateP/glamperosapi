from pydantic import BaseModel, HttpUrl
from typing import Optional, List, Dict
from datetime import datetime


class ModeloGlamping(BaseModel):
    id: Optional[str] = None                          # ID generado por MongoDB
    nombre: str                                       # Nombre del glamping
    ubicacion: Dict[str, float]                      # Ubicación (latitud y longitud)
    precio_noche: float                               # Precio por noche
    descripcion: str                                  # Descripción
    imagenes: List[str]                               # Lista de rutas/URLs de imágenes
    video_youtube: Optional[HttpUrl] = None          # Video de YouTube (opcional)
    calificacion: Optional[float] = None             # Promedio de calificaciones (1.0 a 5.0)
    caracteristicas: List[str]                       # Características del glamping
    servicios: List[str]                              # Servicios adicionales
    propietario_id: Optional[str] = None             # ID del propietario
    ciudad_departamento: str                         # Ciudad y departamento del glamping
    creado: Optional[datetime] = None                # Fecha de creación (opcional)
