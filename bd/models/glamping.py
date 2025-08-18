from pydantic import BaseModel, Field
from typing import Optional, List, Any
from datetime import datetime


class ModeloGlamping(BaseModel):
    # ─────────────────────────────────────────────────────────────
    # Identificación / Metadatos
    # ─────────────────────────────────────────────────────────────
    id: Optional[str] = Field(None, alias="_id")
    creado: Optional[datetime] = None
    propietario_id: Optional[str] = None
    habilitado: Optional[bool] = True

    # ─────────────────────────────────────────────────────────────
    # Información principal
    # ─────────────────────────────────────────────────────────────
    nombreGlamping: Optional[str] = None
    tipoGlamping: Optional[str] = None
    descripcionGlamping: Optional[str] = None
    imagenes: Optional[List[str]] = None
    video_youtube: Optional[str] = None
    calificacion: Optional[float] = None

    # ─────────────────────────────────────────────────────────────
    # Ubicación
    # (puede venir dict {"lat":..., "lng":...} o string JSON)
    # ─────────────────────────────────────────────────────────────
    ubicacion: Optional[Any] = None
    direccion: Optional[str] = None
    ciudad_departamento: Optional[str] = None

    # ─────────────────────────────────────────────────────────────
    # Políticas / Reglas
    # ─────────────────────────────────────────────────────────────
    Acepta_Mascotas: Optional[bool] = None
    politicas_casa: Optional[str] = None
    horarios: Optional[str] = None
    diasCancelacion: Optional[float] = None
    minimoNoches: Optional[float] = None

    # ─────────────────────────────────────────────────────────────
    # Capacidad y Precios
    # ─────────────────────────────────────────────────────────────
    Cantidad_Huespedes: Optional[float] = None
    Cantidad_Huespedes_Adicional: Optional[float] = None
    precioEstandar: Optional[float] = None
    precioEstandarAdicional: Optional[float] = None
    descuento: Optional[float] = None

    # ─────────────────────────────────────────────────────────────
    # Amenidades
    # ─────────────────────────────────────────────────────────────
    amenidadesGlobal: Optional[List[str]] = None

    # ─────────────────────────────────────────────────────────────
    # Fechas / Sincronización
    # ─────────────────────────────────────────────────────────────
    fechasReservadas: Optional[List[str]] = None
    fechasReservadasManual: Optional[List[str]] = None
    fechasReservadasAirbnb: Optional[List[str]] = None
    fechasReservadasBooking: Optional[List[str]] = None
    urlIcal: Optional[str] = None
    urlIcalBooking: Optional[str] = None

    # ─────────────────────────────────────────────────────────────
    # Servicios adicionales (agrupados por temática)
    # ─────────────────────────────────────────────────────────────

    # Romance / Experiencias especiales
    cena_estandar: Optional[str] = None
    valor_cena_estandar: Optional[float] = None
    cena_romantica: Optional[str] = None
    valor_cena_romantica: Optional[float] = None
    picnic_romantico: Optional[str] = None
    valor_picnic_romantico: Optional[float] = None
    proyeccion_pelicula: Optional[str] = None
    valor_proyeccion_pelicula: Optional[float] = None
    masaje_pareja: Optional[str] = None
    valor_masaje_pareja: Optional[float] = None
    terapia_facial: Optional[str] = None
    valor_terapia_facial: Optional[float] = None
    decoracion_sencilla: Optional[str] = None
    valor_decoracion_sencilla: Optional[float] = None
    decoracion_especial: Optional[str] = None
    valor_decoracion_especial: Optional[float] = None

    # Aventura en tierra
    caminata: Optional[str] = None
    valor_caminata: Optional[float] = None
    torrentismo: Optional[str] = None
    valor_torrentismo: Optional[float] = None
    paseo_cuatrimoto: Optional[str] = None
    valor_paseo_cuatrimoto: Optional[float] = None
    paseo_caballo: Optional[str] = None
    valor_paseo_caballo: Optional[float] = None
    paseo_bicicleta: Optional[str] = None
    valor_paseo_bicicleta: Optional[float] = None

    # Aventura aérea
    parapente: Optional[str] = None
    valor_parapente: Optional[float] = None

    # Actividades acuáticas
    paseo_lancha: Optional[str] = None
    valor_paseo_lancha: Optional[float] = None
    kayak: Optional[str] = None
    valor_kayak: Optional[float] = None
    jet_ski: Optional[str] = None
    valor_jet_ski: Optional[float] = None    
    paseo_vela: Optional[str] = None
    valor_paseo_vela: Optional[float] = None

    # Otros complementos
    dia_sol: Optional[str] = None
    valor_dia_sol: Optional[float] = None
    kit_fogata: Optional[str] = None
    valor_kit_fogata: Optional[float] = None
    mascota_adicional: Optional[str] = None
    valor_mascota_adicional: Optional[float] = None

    class Config:
        allow_population_by_field_name = True
        extra = "ignore"
