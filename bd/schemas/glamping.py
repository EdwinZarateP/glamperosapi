# from pydantic import BaseModel, HttpUrl
# from typing import Optional, List, Dict
# from datetime import datetime

# class SchemaGlamping(BaseModel):
#     id: Optional[str] = None                           # ID convertido a string
#     nombre: str = "Glamping Estrella Verde"            # Ejemplo de nombre del glamping
#     ubicacion: Optional[Dict[str, float]] = {"latitud": 4.5981, "longitud": -74.0758}  # Ejemplo de ubicación
#     precioEstandar: float = 150.0                        # Precio por noche de ejemplo
#     descuento:float = 0 
#     descripcion: str = "Un lugar increíble rodeado de naturaleza."  # Descripción de ejemplo
#     imagenes: List[str] = ["https://example.com/image1.jpg", "https://example.com/image2.jpg"]  # Ejemplo de URLs de imágenes
#     video_youtube: Optional[HttpUrl] = "https://www.youtube.com/watch?v=_E9quCgwClA"  # Ejemplo de video
#     calificacion: Optional[float] = 4.5               # Promedio de calificaciones de ejemplo
#     caracteristicas: List[str] = ["WiFi", "Jacuzzi", "Piscina"]  # Características de ejemplo
#     ciudad_departamento: str = "Bogotá, Cundinamarca"  # Ejemplo de ciudad y departamento
#     creado: Optional[datetime] = datetime.now()       # Fecha de creación automática
#     propietario_id: str = "6482ac77b9f19f39d67891b2"  # Ejemplo de propietario ID
