from pydantic import BaseModel, HttpUrl, Field
from typing import Optional, List, Dict
from datetime import datetime

class ModeloGlamping(BaseModel):
    id: Optional[str] = Field(None, alias="_id") 
    nombreGlamping: str = "Glamping Estrella Verde" 
    tipoGlamping: str = "choza"
    Acepta_Mascotas: bool = True     
    ubicacion: Optional[Dict[str, float]] = {"latitud": 4.5981, "longitud": -74.0758}  # Ejemplo de ubicación
    precioEstandar: float = 150.0
    Cantidad_Huespedes: float = 1     
    descuento:float = 0 
    descripcionGlamping: str = "Un lugar increíble rodeado de naturaleza."
    imagenes: List[str] = ["https://example.com/image1.jpg", "https://example.com/image2.jpg"]  # Ejemplo de URLs de imágenes
    video_youtube: Optional[str] = "https://youtube.com"
    calificacion: Optional[float] = 4.5
    amenidadesGlobal: List[str] = ["WiFi", "Jacuzzi", "Piscina"]
    ciudad_departamento: str = "Bogotá, Cundinamarca"
    fechasReservadas: Optional[List[str]] = ["01/03/2024", "01/05/2024", "01/06/2024"]
    creado: Optional[datetime] = datetime.now()
    propietario_id: str = "6482ac77b9f19f39d67891b2"

    class Config:
        allow_population_by_field_name = True 