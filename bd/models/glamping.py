from pydantic import BaseModel, HttpUrl
from typing import Optional, List, Dict
from datetime import datetime

class ModeloGlamping(BaseModel):
    id: Optional[str] = None 
    nombreGlamping: str = "Glamping Estrella Verde" 
    tipoGlamping: str = "choza"
    Acepta_Mascotas: bool = True     
    ubicacion: Optional[Dict[str, float]] = {"latitud": 4.5981, "longitud": -74.0758}  # Ejemplo de ubicación
    precioEstandar: float = 150.0
    Cantidad_Huespedes: float = 1     
    descuento:float = 0 
    descripcionGlamping: str = "Un lugar increíble rodeado de naturaleza."
    imagenes: List[str] = ["https://example.com/image1.jpg", "https://example.com/image2.jpg"]  # Ejemplo de URLs de imágenes
    video_youtube: Optional[HttpUrl] = "https://www.youtube.com/watch?v=_E9quCgwClA"
    calificacion: Optional[float] = 4.5
    amenidadesGlobal: List[str] = ["WiFi", "Jacuzzi", "Piscina"]  # Características de ejemplo
    ciudad_departamento: str = "Bogotá, Cundinamarca"
    creado: Optional[datetime] = datetime.now()
    propietario_id: str = "6482ac77b9f19f39d67891b2"
