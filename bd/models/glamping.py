from pydantic import BaseModel, HttpUrl, Field
from typing import Optional, List, Dict
from datetime import datetime

class ModeloGlamping(BaseModel):
    id: Optional[str] = Field(None, alias="_id")
    habilitado: Optional[bool] = Field(False)
    nombreGlamping: str = "Glamping Estrella Verde" 
    tipoGlamping: str = "choza"
    Acepta_Mascotas: bool = True     
    ubicacion: Optional[Dict[str, float]] = {"latitud": 4.5981, "longitud": -74.0758}
    direccionCompleta: str = "calle falsa 123" 
    precioEstandar: float = 0
    precioEstandarAdicional:float = 0
    Cantidad_Huespedes: float = 1  
    Cantidad_Huespedes_Adicional: float = 0 
    descuento:float = 0 
    descripcionGlamping: str = "Un lugar increíble rodeado de naturaleza."
    imagenes: List[str] = ["https://example.com/image1.jpg", "https://example.com/image2.jpg"]  # Ejemplo de URLs de imágenes
    video_youtube: Optional[str] = "https://youtube.com"
    calificacion: Optional[float] = 4.5
    amenidadesGlobal: List[str] = ["WiFi", "Jacuzzi", "Piscina"]
    ciudad_departamento: str = "Bogotá, Cundinamarca"
    fechasReservadas: Optional[List[str]] = Field(default_factory=list)
    creado: Optional[datetime] = datetime.now()
    propietario_id: str = "6482ac77b9f19f39d67891b2"

    class Config:
        allow_population_by_field_name = True 