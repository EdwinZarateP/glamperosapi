from fastapi import APIRouter, HTTPException, status, Body
from pymongo import MongoClient
from bson import ObjectId
from datetime import datetime
from pydantic import BaseModel
from pytz import timezone
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
    ciudad_departamento: str
    FechaIngreso: datetime
    FechaSalida: datetime
    Noches: float
    ValorReserva: float
    CostoGlamping: float
    ComisionGlamperos: float
    adultos: int
    ninos: int
    bebes: int
    mascotas: int
    EstadoReserva: str
    ComentariosCancelacion: str

# Modelo para actualización
class ActualizarReserva(BaseModel):
    EstadoReserva: str
    ComentariosCancelacion: str

# Modelo de respuesta de reserva
def modelo_reserva(reserva) -> dict:
    return {
        "id": str(reserva["_id"]),
        "idCliente": reserva["idCliente"],
        "idPropietario": reserva["idPropietario"],
        "idGlamping": reserva["idGlamping"],
        "ciudad_departamento": reserva["ciudad_departamento"],
        "FechaIngreso": reserva["FechaIngreso"],
        "FechaSalida": reserva["FechaSalida"],
        "Noches": reserva["Noches"],
        "ValorReserva": reserva["ValorReserva"],
        "CostoGlamping": reserva["CostoGlamping"],
        "ComisionGlamperos": reserva["ComisionGlamperos"],
        "adultos": reserva["adultos"],
        "ninos": reserva["ninos"],
        "bebes": reserva["bebes"],
        "mascotas": reserva["mascotas"],
        "EstadoReserva": reserva["EstadoReserva"],
        "fechaCreacion": reserva["fechaCreacion"],         
        "ComentariosCancelacion": reserva["ComentariosCancelacion"],          
    }

# Definir la zona horaria de Colombia
ZONA_HORARIA_COLOMBIA = timezone("America/Bogota")

# Crear una nueva reserva
@ruta_reserva.post("/", response_model=dict)
async def crear_reserva(reserva: Reserva):
    try:
        # Generar un código único con los primeros 8 caracteres del ObjectId
        codigo_reserva = str(ObjectId())[:8]
        
        # Convertir la fecha de creación a la hora de Colombia (UTC-5)
        fecha_creacion_colombia = datetime.now().astimezone(ZONA_HORARIA_COLOMBIA)

        nueva_reserva = {
            "idCliente": reserva.idCliente,
            "idPropietario": reserva.idPropietario,
            "idGlamping": reserva.idGlamping,
            "ciudad_departamento": reserva.ciudad_departamento,
            "FechaIngreso": reserva.FechaIngreso,
            "FechaSalida": reserva.FechaSalida,
            "Noches": reserva.Noches,
            "ValorReserva": reserva.ValorReserva,
            "CostoGlamping": reserva.CostoGlamping,
            "ComisionGlamperos": reserva.ComisionGlamperos,
            "adultos": reserva.adultos,
            "ninos": reserva.ninos,
            "bebes": reserva.bebes,
            "mascotas": reserva.mascotas,
            "EstadoReserva": reserva.EstadoReserva,
            "fechaCreacion":fecha_creacion_colombia,
            "codigoReserva": codigo_reserva,             
            "ComentariosCancelacion": reserva.ComentariosCancelacion, 
            
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

# Consultar reservas del propietario
@ruta_reserva.get("/documentos/{idPropietario}", response_model=list)
async def obtener_documentos_por_propietario(idPropietario: str):
    try:
        # Consulta los documentos asociados al propietario
        documentos = base_datos.reservas.find({"idPropietario": idPropietario})
        
        # Verifica si existen documentos
        documentos_lista = [modelo_reserva(doc) for doc in documentos]
        if not documentos_lista:
            raise HTTPException(
                status_code=404,
                detail=f"No se encontraron documentos para el propietario con ID {idPropietario}"
            )
        
        return documentos_lista
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error al obtener los documentos del propietario: {str(e)}"
        )

# Consultar reservas del cliente
@ruta_reserva.get("/documentos_cliente/{idCliente}", response_model=list)
async def obtener_documentos_por_cliente(idCliente: str):
    try:
        # Consulta los documentos asociados al cliente
        documentos = base_datos.reservas.find({"idCliente": idCliente})
        
        # Verifica si existen documentos
        documentos_lista = [modelo_reserva(doc) for doc in documentos]
        if not documentos_lista:
            raise HTTPException(
                status_code=404,
                detail=f"No se encontraron documentos para el cliente con ID {idCliente}"
            )
        
        return documentos_lista
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error al obtener los documentos del cliente: {str(e)}"
        )

# Actualizar estado de reserva y comentarios
@ruta_reserva.put("/{reserva_id}", response_model=dict)
async def actualizar_estado_reserva(
    reserva_id: str,
    actualizacion: ActualizarReserva = Body(...)
):
    try:
        # Validar formato del ID
        try:
            object_id = ObjectId(reserva_id)
        except:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Formato de ID inválido"
            )

        # Construir actualización
        update_data = {
            "EstadoReserva": actualizacion.EstadoReserva,
            "ComentariosCancelacion": actualizacion.ComentariosCancelacion
        }

        # Ejecutar actualización
        resultado = base_datos.reservas.update_one(
            {"_id": object_id},
            {"$set": update_data}
        )

        if resultado.modified_count == 0:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Reserva no encontrada"
            )

        # Obtener reserva actualizada
        reserva_actualizada = base_datos.reservas.find_one({"_id": object_id})
        
        return {
            "mensaje": "Reserva actualizada correctamente",
            "reserva": modelo_reserva(reserva_actualizada)
        }
        
    except HTTPException as he:
        raise he
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error al actualizar reserva: {str(e)}"
        )