from pydantic import BaseModel, HttpUrl, Field
from typing import Optional, List, Dict
from datetime import datetime

class ModeloGlamping(BaseModel):
    id: Optional[str] = Field(None, alias="_id")
    habilitado: Optional[bool] = Field(True)
    nombreGlamping: str = "Glamping Estrella Verde" 
    tipoGlamping: str = "choza"
    Acepta_Mascotas: bool = True     
    ubicacion: Optional[Dict[str, float]] = {"latitud": 4.5981, "longitud": -74.0758}
    direccion: str = "Plaza Bolivar, Bogota, Colombia" 
    precioEstandar: float = 0
    precioEstandarAdicional:float = 0
    diasCancelacion:Optional[float] = 3
    Cantidad_Huespedes: float = 1  
    Cantidad_Huespedes_Adicional: float = 0 
    minimoNoches: float = 1 
    descuento:float = 0 
    descripcionGlamping: str = "Un lugar increíble rodeado de naturaleza."
    imagenes: List[str] = ["https://example.com/image1.jpg", "https://example.com/image2.jpg"]  # Ejemplo de URLs de imágenes
    video_youtube: Optional[str] = "sin video"
    calificacion: Optional[float] = 5
    amenidadesGlobal: List[str] = ["WiFi", "Jacuzzi", "Piscina"]
    ciudad_departamento: str = "Bogotá, Cundinamarca"
    fechasReservadas: Optional[List[str]] = Field(default_factory=list)
    creado: Optional[datetime] = datetime.now()
    propietario_id: str = "6482ac77b9f19f39d67891b2"
    urlIcal: Optional[str] = None
    urlIcalBooking: Optional[str] = None

    class Config:
        allow_population_by_field_name = True 