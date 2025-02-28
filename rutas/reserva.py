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
    # Nuevos campos para el manejo de pagos
    EstadoPago: str = "Pendiente"
    MetodoPago: str = None
    FechaPago: datetime = None
    ReferenciaPago: str = None

# Modelo para actualización de estado de reserva y comentarios
class ActualizarReserva(BaseModel):
    EstadoReserva: str
    ComentariosCancelacion: str

# Modelo para actualización del pago
class ActualizarPago(BaseModel):
    EstadoPago: str      # Por ejemplo: "Pagado" o "Pendiente"
    MetodoPago: str      # Ejemplo: "Transferencia Bancaria", "Nequi", "PayPal", etc.
    FechaPago: datetime
    ReferenciaPago: str

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
        "codigoReserva": reserva["codigoReserva"],
        "ComentariosCancelacion": reserva["ComentariosCancelacion"],
        "EstadoPago": reserva.get("EstadoPago", "Pendiente"),
        "MetodoPago": reserva.get("MetodoPago"),
        "FechaPago": reserva.get("FechaPago"),
        "ReferenciaPago": reserva.get("ReferenciaPago")
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
            "fechaCreacion": fecha_creacion_colombia,
            "codigoReserva": codigo_reserva,
            "ComentariosCancelacion": reserva.ComentariosCancelacion,
            # Inicializar los campos de pago
            "EstadoPago": reserva.EstadoPago,
            "MetodoPago": reserva.MetodoPago,
            "FechaPago": reserva.FechaPago,
            "ReferenciaPago": reserva.ReferenciaPago
        }
        
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
        documentos = base_datos.reservas.find({"idPropietario": idPropietario})
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
        documentos = base_datos.reservas.find({"idCliente": idCliente})
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
        try:
            object_id = ObjectId(reserva_id)
        except:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Formato de ID inválido"
            )
        update_data = {
            "EstadoReserva": actualizacion.EstadoReserva,
            "ComentariosCancelacion": actualizacion.ComentariosCancelacion
        }
        resultado = base_datos.reservas.update_one(
            {"_id": object_id},
            {"$set": update_data}
        )
        if resultado.modified_count == 0:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Reserva no encontrada"
            )
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

# Actualizar el estado de pago de una reserva
@ruta_reserva.put("/pago/{reserva_id}", response_model=dict)
async def actualizar_pago_reserva(
    reserva_id: str,
    pago: ActualizarPago = Body(...)
):
    try:
        try:
            object_id = ObjectId(reserva_id)
        except:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Formato de ID inválido"
            )
        update_data = {
            "EstadoPago": pago.EstadoPago,
            "MetodoPago": pago.MetodoPago,
            "FechaPago": pago.FechaPago,
            "ReferenciaPago": pago.ReferenciaPago
        }
        resultado = base_datos.reservas.update_one(
            {"_id": object_id},
            {"$set": update_data}
        )
        if resultado.modified_count == 0:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Reserva no encontrada o pago ya actualizado"
            )
        reserva_actualizada = base_datos.reservas.find_one({"_id": object_id})
        return {
            "mensaje": "Pago actualizado correctamente",
            "reserva": modelo_reserva(reserva_actualizada)
        }
    except HTTPException as he:
        raise he
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error al actualizar el pago: {str(e)}"
        )

# Obtener reservas pendientes de pago
@ruta_reserva.get("/pendientes_pago", response_model=list)
async def obtener_reservas_pendientes_pago():
    try:
        reservas_pendientes = base_datos.reservas.find({"EstadoPago": "Pendiente"})
        reservas_lista = [modelo_reserva(reserva) for reserva in reservas_pendientes]
        if not reservas_lista:
            raise HTTPException(
                status_code=404,
                detail="No hay reservas pendientes de pago"
            )
        return reservas_lista
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error al obtener reservas pendientes de pago: {str(e)}"
        )

# Consultar reserva por código de reserva
@ruta_reserva.get("/codigo/{codigoReserva}", response_model=dict)
async def obtener_reserva_por_codigo(codigoReserva: str):
    try:
        reserva = base_datos.reservas.find_one({"codigoReserva": codigoReserva})
        if not reserva:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"No se encontró una reserva con el código {codigoReserva}"
            )
        return {
            "mensaje": "Reserva encontrada",
            "reserva": modelo_reserva(reserva)
        }
    except HTTPException as he:
        raise he
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error al buscar la reserva: {str(e)}"
        )

# Solicitar pago por parte de los propietarios
@ruta_reserva.post("/solicitar_pago", response_model=dict)
async def solicitar_pago(payload: dict = Body(...)):
    try:
        idPropietario = payload.get("idPropietario")
        metodoPago = payload.get("metodoPago")
        if not idPropietario or not metodoPago:
            raise HTTPException(
                status_code=400,
                detail="Se requieren idPropietario y metodoPago"
            )

        # Obtener las reservas pendientes (completadas y sin pago)
        reservas_pendientes = base_datos.reservas.find({
            "idPropietario": idPropietario,
            "EstadoPago": "Pendiente",
            "EstadoReserva": "Completada"
        })

        saldo_disponible = sum(reserva["CostoGlamping"] for reserva in reservas_pendientes)

        if saldo_disponible <= 0:
            raise HTTPException(
                status_code=400,
                detail="No hay saldo disponible para retirar"
            )

        # Crear la solicitud de pago usando el saldo disponible
        nueva_solicitud = {
            "idPropietario": idPropietario,
            "MontoSolicitado": saldo_disponible,
            "Estado": "Pendiente",
            "MetodoPago": metodoPago,
            "FechaSolicitud": datetime.now().astimezone(ZONA_HORARIA_COLOMBIA),
            "FechaPago": None,
            "ReferenciaPago": None
        }

        result = base_datos.solicitudes_pago.insert_one(nueva_solicitud)

        return {"mensaje": "Solicitud de pago enviada exitosamente"}
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error al solicitar el pago: {str(e)}"
        )
