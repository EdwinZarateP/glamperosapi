from pydantic import BaseModel, Field
from typing import Optional, List, Any
from datetime import datetime

class ModeloGlamping(BaseModel):
    # MongoDB id
    id: Optional[str] = Field(None, alias="_id")

    # — Datos base —
    habilitado: Optional[bool] = True
    nombreGlamping: Optional[str] = None
    tipoGlamping: Optional[str] = None
    Acepta_Mascotas: Optional[bool] = None
    # Puede venir como dict {"lat": ..., "lng": ...} o como string JSON
    ubicacion: Optional[Any] = None
    direccion: Optional[str] = None

    precioEstandar: Optional[float] = None
    precioEstandarAdicional: Optional[float] = None
    diasCancelacion: Optional[float] = None
    Cantidad_Huespedes: Optional[float] = None
    Cantidad_Huespedes_Adicional: Optional[float] = None
    minimoNoches: Optional[float] = None
    descuento: Optional[float] = None

    descripcionGlamping: Optional[str] = None
    imagenes: Optional[List[str]] = None
    video_youtube: Optional[str] = None
    calificacion: Optional[float] = None
    amenidadesGlobal: Optional[List[str]] = None
    ciudad_departamento: Optional[str] = None

    # Fechas
    fechasReservadas: Optional[List[str]] = None
    fechasReservadasManual: Optional[List[str]] = None
    fechasReservadasAirbnb: Optional[List[str]] = None
    fechasReservadasBooking: Optional[List[str]] = None

    creado: Optional[datetime] = None
    propietario_id: Optional[str] = None
    urlIcal: Optional[str] = None
    urlIcalBooking: Optional[str] = None

    # — Ten en cuenta —
    politicas_casa: Optional[str] = None
    horarios: Optional[str] = None

    # — Servicios adicionales —
    decoracion_sencilla: Optional[str] = None
    valor_decoracion_sencilla: Optional[float] = None

    decoracion_especial: Optional[str] = None
    valor_decoracion_especial: Optional[float] = None

    paseo_cuatrimoto: Optional[str] = None
    valor_paseo_cuatrimoto: Optional[float] = None

    paseo_caballo: Optional[str] = None
    valor_paseo_caballo: Optional[float] = None

    masaje_pareja: Optional[str] = None
    valor_masaje_pareja: Optional[float] = None

    dia_sol: Optional[str] = None
    valor_dia_sol: Optional[float] = None

    caminata: Optional[str] = None
    valor_caminata: Optional[float] = None

    kit_fogata: Optional[str] = None
    valor_kit_fogata: Optional[float] = None

    cena_romantica: Optional[str] = None
    valor_cena_romantica: Optional[float] = None

    mascota_adicional: Optional[str] = None
    valor_mascota_adicional: Optional[float] = None

    class Config:
        allow_population_by_field_name = True
        extra = "ignore"
