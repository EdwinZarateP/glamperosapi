from fastapi import APIRouter, HTTPException, status, Body
from pymongo import MongoClient
from bson import ObjectId
from datetime import datetime
from pydantic import BaseModel
import os

# Configuración de la base de datos
MONGO_URI = os.environ.get("MONGO_URI", "mongodb://localhost:27017")
ConexionMongo = MongoClient(MONGO_URI)
base_datos = ConexionMongo["glamperos"]

# Configuración de FastAPI
ruta_reserva = APIRouter(
    prefix="/reservas",
    tags=["Reservas"],
    responses={status.HTTP_404_NOT_FOUND: {"message": "No encontrado"}},
)

# Modelo de reserva
class Reserva(BaseModel):
    idCliente: str
    idPropietario: str
    idGlamping: str
    FechaIngreso: datetime
    FechaSalida: datetime
    ValorReserva: float
    CostoGlamping: float
    ComisionGlamperos: float
    adultos: int
    niños: int
    bebes: int
    mascotas: int
    EstadoReserva: str

# Modelo de respuesta de reserva
def modelo_reserva(reserva) -> dict:
    return {
        "id": str(reserva["_id"]),
        "idCliente": reserva["idCliente"],
        "idPropietario": reserva["idPropietario"],        
        "idGlamping": reserva["idGlamping"],
        "FechaIngreso": reserva["FechaIngreso"],
        "FechaSalida": reserva["FechaSalida"],
        "ValorReserva": reserva["ValorReserva"],
        "CostoGlamping": reserva["CostoGlamping"],
        "ComisionGlamperos": reserva["ComisionGlamperos"],
        "adultos": reserva["adultos"],
        "niños": reserva["niños"],
        "bebes": reserva["bebes"],
        "mascotas": reserva["mascotas"],
        "EstadoReserva": reserva["EstadoReserva"],
        "fechaCreacion": reserva["fechaCreacion"],

    }

# Crear una nueva reserva
@ruta_reserva.post("/", response_model=dict)
async def crear_reserva(reserva: Reserva):
    try:
        nueva_reserva = {
            "idCliente": reserva.idCliente,
            "idPropietario": reserva.idPropietario,
            "idGlamping": reserva.idGlamping,
            "FechaIngreso": reserva.FechaIngreso,
            "FechaSalida": reserva.FechaSalida,
            "ValorReserva": reserva.ValorReserva,
            "CostoGlamping": reserva.CostoGlamping,
            "ComisionGlamperos": reserva.ComisionGlamperos,
            "adultos": reserva.adultos,
            "niños": reserva.niños,
            "bebes": reserva.bebes,
            "mascotas": reserva.mascotas,
            "EstadoReserva": reserva.EstadoReserva,
            "fechaCreacion": datetime.now(),
        }

        # Insertar en la base de datos
        result = base_datos.reservas.insert_one(nueva_reserva)
        nueva_reserva["_id"] = result.inserted_id

        return {"mensaje": "Reserva creada exitosamente", "reserva": modelo_reserva(nueva_reserva)}
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error al crear la reserva: {str(e)}"
        )
