from fastapi import APIRouter, HTTPException, status, Body
from pymongo import MongoClient
from bson import ObjectId
from datetime import datetime
from pydantic import BaseModel
from pytz import timezone
import os

# ============================================================================
# CONFIGURACIÓN DE LA BASE DE DATOS
# ============================================================================
MONGO_URI = os.environ.get("MONGO_URI", "mongodb://localhost:27017")
ConexionMongo = MongoClient(MONGO_URI)
base_datos = ConexionMongo["glamperos"]

# ============================================================================
# CONFIGURACIÓN DE FASTAPI
# ============================================================================
ruta_reserva = APIRouter(
    prefix="/reservas",
    tags=["Reservas"],
    responses={status.HTTP_404_NOT_FOUND: {"message": "No encontrado"}},
)

# ============================================================================
# MODELOS DE DATOS
# ============================================================================
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
    EstadoPago: str = "Pendiente"
    MetodoPago: str = None
    FechaPago: datetime = None
    ReferenciaPago: str = None

class ActualizarReserva(BaseModel):
    EstadoReserva: str
    ComentariosCancelacion: str

class ActualizarPago(BaseModel):
    EstadoPago: str
    MetodoPago: str
    FechaPago: datetime
    ReferenciaPago: str

class ActualizarSolicitudPago(BaseModel):
    Estado: str
    FechaPago: datetime
    ReferenciaPago: str

def modelo_reserva(reserva) -> dict:
    """
    Convierte un documento de MongoDB a un diccionario Python
    con las claves en formato legible y el id como string.
    """
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
        "ReferenciaPago": reserva.get("ReferenciaPago"),
    }

# ============================================================================
# CONFIGURACIÓN DE ZONA HORARIA
# ============================================================================
ZONA_HORARIA_COLOMBIA = timezone("America/Bogota")

# ============================================================================
# CREAR RESERVA
# ============================================================================
@ruta_reserva.post("/", response_model=dict)
async def crear_reserva(reserva: Reserva):
    """
    Crea una nueva reserva en la colección 'reservas'.
    Genera un codigoReserva automático usando ObjectId.
    """
    try:
        codigo_reserva = str(ObjectId())[:8]
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
            "EstadoPago": reserva.EstadoPago,
            "MetodoPago": reserva.MetodoPago,
            "FechaPago": reserva.FechaPago,
            "ReferenciaPago": reserva.ReferenciaPago,
        }

        result = base_datos.reservas.insert_one(nueva_reserva)
        nueva_reserva["_id"] = result.inserted_id

        return {
            "mensaje": "Reserva creada exitosamente",
            "reserva": modelo_reserva(nueva_reserva),
        }

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error al crear la reserva: {str(e)}"
        )

# ============================================================================
# CONSULTAR RESERVAS DEL PROPIETARIO
# ============================================================================
@ruta_reserva.get("/documentos/{idPropietario}", response_model=list)
async def obtener_documentos_por_propietario(idPropietario: str):
    """
    Obtiene todas las reservas donde 'idPropietario' sea igual al propietario recibido.
    """
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

# ============================================================================
# CONSULTAR RESERVAS DEL CLIENTE
# ============================================================================
@ruta_reserva.get("/documentos_cliente/{idCliente}", response_model=list)
async def obtener_documentos_por_cliente(idCliente: str):
    """
    Obtiene todas las reservas donde 'idCliente' sea igual al cliente recibido.
    """
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

# ============================================================================
# ACTUALIZAR ESTADO DE RESERVA Y COMENTARIOS
# ============================================================================
@ruta_reserva.put("/{reserva_id}", response_model=dict)
async def actualizar_estado_reserva(
    reserva_id: str,
    actualizacion: ActualizarReserva = Body(...)
):
    """
    Actualiza el EstadoReserva y ComentariosCancelacion de la reserva con _id = reserva_id.
    """
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
            "reserva": modelo_reserva(reserva_actualizada),
        }

    except HTTPException as he:
        raise he
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error al actualizar reserva: {str(e)}"
        )

# ============================================================================
# ACTUALIZAR EL ESTADO DE PAGO DE UNA RESERVA
# ============================================================================
@ruta_reserva.put("/pago/{reserva_id}", response_model=dict)
async def actualizar_pago_reserva(
    reserva_id: str,
    pago: ActualizarPago = Body(...)
):
    """
    Actualiza el EstadoPago, MetodoPago, FechaPago y ReferenciaPago de la reserva.
    """
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
            "ReferenciaPago": pago.ReferenciaPago,
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
            "reserva": modelo_reserva(reserva_actualizada),
        }

    except HTTPException as he:
        raise he
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error al actualizar el pago: {str(e)}"
        )

# ============================================================================
# OBTENER RESERVAS PENDIENTES DE PAGO (COMPLETADAS) PARA UN PROPIETARIO
# ============================================================================
@ruta_reserva.get("/pendientes_pago/{idPropietario}", response_model=list)
async def obtener_reservas_pendientes_pago(idPropietario: str):
    """
    Encuentra todas las reservas de un propietario que tengan EstadoPago="Pendiente" y EstadoReserva="Completada".
    """
    try:
        reservas_pendientes = base_datos.reservas.find({
            "idPropietario": idPropietario,
            "EstadoPago": "Pendiente",
            "EstadoReserva": "Completada"
        })
        reservas_lista = [modelo_reserva(reserva) for reserva in reservas_pendientes]
        if not reservas_lista:
            raise HTTPException(
                status_code=404,
                detail="No hay reservas pendientes de pago para este propietario"
            )
        return reservas_lista
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error al obtener reservas pendientes de pago: {str(e)}"
        )

# ============================================================================
# CONSULTAR RESERVA POR CÓDIGO DE RESERVA
# ============================================================================
@ruta_reserva.get("/codigo/{codigoReserva}", response_model=dict)
async def obtener_reserva_por_codigo(codigoReserva: str):
    """
    Obtiene la reserva cuyo 'codigoReserva' coincide con el proporcionado.
    """
    try:
        reserva = base_datos.reservas.find_one({"codigoReserva": codigoReserva})
        if not reserva:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"No se encontró una reserva con el código {codigoReserva}"
            )
        return {
            "mensaje": "Reserva encontrada",
            "reserva": modelo_reserva(reserva),
        }
    except HTTPException as he:
        raise he
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error al buscar la reserva: {str(e)}"
        )

# ============================================================================
# SOLICITAR PAGO (ACTUALIZA RESERVAS A "SOLICITADO" Y CREA SOLICITUD)
# ============================================================================
@ruta_reserva.post("/solicitar_pago", response_model=dict)
async def solicitar_pago(payload: dict = Body(...)):
    """
    Marca como "Solicitado" las reservas "Pendientes" y "Completadas" de un propietario,
    y crea un documento en la colección 'solicitudes_pago'.
    """
    try:
        idPropietario = payload.get("idPropietario")
        metodoPago = payload.get("metodoPago")
        if not idPropietario or not metodoPago:
            raise HTTPException(
                status_code=400,
                detail="Se requieren idPropietario y metodoPago"
            )

        reservas_pendientes = list(base_datos.reservas.find({
            "idPropietario": idPropietario,
            "EstadoPago": "Pendiente",
            "EstadoReserva": "Completada"
        }))
        saldo_disponible = sum(reserva.get("CostoGlamping", 0) for reserva in reservas_pendientes)
        if saldo_disponible <= 0:
            raise HTTPException(
                status_code=400,
                detail="No hay saldo disponible para retirar"
            )

        codigos_reserva = [reserva.get("codigoReserva") for reserva in reservas_pendientes]

        update_result = base_datos.reservas.update_many(
            {
                "idPropietario": idPropietario,
                "EstadoPago": "Pendiente",
                "EstadoReserva": "Completada"
            },
            {"$set": {"EstadoPago": "Solicitado"}}
        )

        nueva_solicitud = {
            "idPropietario": idPropietario,
            "MontoSolicitado": saldo_disponible,
            "Estado": "Pendiente",
            "MetodoPago": metodoPago,
            "FechaSolicitud": datetime.now().astimezone(ZONA_HORARIA_COLOMBIA),
            "FechaPago": None,
            "ReferenciaPago": None,
            "codigosReserva": codigos_reserva
        }
        result = base_datos.solicitudes_pago.insert_one(nueva_solicitud)
        return {"mensaje": "Solicitud de pago enviada exitosamente"}

    except HTTPException as he:
        raise he
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error al solicitar el pago: {str(e)}"
        )

# ============================================================================
# HISTÓRICO DE SOLICITUDES DE PAGO PARA UN PROPIETARIO
# ============================================================================
@ruta_reserva.get("/solicitudes_pago/{idPropietario}", response_model=list)
async def obtener_solicitudes_pago(idPropietario: str):
    """
    Obtiene todas las solicitudes de pago realizadas por un propietario.
    """
    try:
        solicitudes = base_datos.solicitudes_pago.find({"idPropietario": idPropietario})
        solicitudes_lista = []
        for sol in solicitudes:
            sol["_id"] = str(sol["_id"])
            solicitudes_lista.append(sol)
        return solicitudes_lista
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error al obtener solicitudes de pago: {str(e)}"
        )

# ============================================================================
# ACTUALIZAR SOLICITUD DE PAGO (ÁREA FINANCIERA)
# ============================================================================
@ruta_reserva.put("/actualizar_solicitud_pago/{solicitud_id}", response_model=dict)
async def actualizar_solicitud_pago(solicitud_id: str, actualizacion: ActualizarSolicitudPago = Body(...)):
    """
    El área financiera actualiza la solicitud de pago, estableciendo su estado
    (por ejemplo 'Aprobada' o 'Rechazada'), FechaPago y ReferenciaPago.
    """
    try:
        try:
            object_id = ObjectId(solicitud_id)
        except:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Formato de ID inválido"
            )

        update_data = {
            "Estado": actualizacion.Estado,
            "FechaPago": actualizacion.FechaPago,
            "ReferenciaPago": actualizacion.ReferenciaPago
        }

        resultado = base_datos.solicitudes_pago.update_one(
            {"_id": object_id},
            {"$set": update_data}
        )
        if resultado.modified_count == 0:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Solicitud de pago no encontrada o ya actualizada"
            )

        solicitud_actualizada = base_datos.solicitudes_pago.find_one({"_id": object_id})
        solicitud_actualizada["_id"] = str(solicitud_actualizada["_id"])
        return {
            "mensaje": "Solicitud de pago actualizada correctamente",
            "solicitud": solicitud_actualizada
        }

    except HTTPException as he:
        raise he
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error al actualizar la solicitud de pago: {str(e)}"
        )

# ============================================================================
#                      NUEVOS ENDPOINTS: REAGENDAR
# ============================================================================
class ReagendamientoRequest(BaseModel):
    codigoReserva: str
    FechaIngreso: datetime
    FechaSalida: datetime

class ActualizarReagendamiento(BaseModel):
    estado: str  # "Aprobado" o "Rechazado"

# ------------------------------
#  1) CREAR REAGENDAMIENTO
# ------------------------------
@ruta_reserva.post("/reagendamientos", response_model=dict)
async def solicitar_reagendamiento(data: ReagendamientoRequest):
    """
    Crea un documento en la colección 'reagendamientos' con estado='Pendiente Aprobacion',
    relacionado a la reserva indicada por 'codigoReserva'.
    """
    try:
        reserva_original = base_datos.reservas.find_one({"codigoReserva": data.codigoReserva})
        if not reserva_original:
            raise HTTPException(
                status_code=404,
                detail=f"No existe una reserva con el código {data.codigoReserva}"
            )
        
        nuevo_reagendamiento = {
            "codigoReserva": data.codigoReserva,
            "FechaIngreso": data.FechaIngreso,
            "FechaSalida": data.FechaSalida,
            "estado": "Pendiente Aprobacion",
            "fechaSolicitud": datetime.now().astimezone(ZONA_HORARIA_COLOMBIA),
        }

        resultado = base_datos.reagendamientos.insert_one(nuevo_reagendamiento)
        nuevo_reagendamiento["_id"] = str(resultado.inserted_id)

        return {
            "mensaje": "Reagendamiento solicitado exitosamente",
            "reagendamiento": nuevo_reagendamiento
        }
    except HTTPException as he:
        raise he
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error al solicitar el reagendamiento: {str(e)}"
        )

# ------------------------------
#  2) APROBAR O RECHAZAR REAGENDAMIENTO
# ------------------------------
@ruta_reserva.put("/reagendamientos/{codigoReserva}", response_model=dict)
async def responder_reagendamiento(
    codigoReserva: str,
    actualizacion: ActualizarReagendamiento = Body(...)
):
    """
    Cambia el estado de un reagendamiento a 'Aprobado' o 'Rechazado'.
    Si es 'Aprobado', también actualiza la reserva original con las nuevas fechas y
    marca su EstadoReserva como 'Reagendado'.
    """
    try:
        reagendamiento = base_datos.reagendamientos.find_one({"codigoReserva": codigoReserva})
        if not reagendamiento:
            raise HTTPException(
                status_code=404,
                detail=f"No se encontró un reagendamiento para el código {codigoReserva}"
            )
        
        # Actualizar el estado del reagendamiento
        base_datos.reagendamientos.update_one(
            {"_id": reagendamiento["_id"]},
            {"$set": {"estado": actualizacion.estado}}
        )

        if actualizacion.estado.lower() == "aprobado":
            nueva_entrada = reagendamiento["FechaIngreso"]
            nueva_salida = reagendamiento["FechaSalida"]

            # Actualizar la reserva con las nuevas fechas y estado
            resultado_reserva = base_datos.reservas.update_one(
                {"codigoReserva": codigoReserva},
                {
                    "$set": {
                        "FechaIngreso": nueva_entrada,
                        "FechaSalida": nueva_salida,
                        "EstadoReserva": "Reagendado"
                    }
                }
            )
            
            if resultado_reserva.modified_count == 0:
                raise HTTPException(
                    status_code=404,
                    detail="No se pudo actualizar la reserva (¿código no coincide?)"
                )

        reagendamiento_actualizado = base_datos.reagendamientos.find_one({"_id": reagendamiento["_id"]})
        reagendamiento_actualizado["_id"] = str(reagendamiento_actualizado["_id"])

        return {
            "mensaje": f"Reagendamiento {actualizacion.estado} correctamente",
            "reagendamiento": reagendamiento_actualizado
        }

    except HTTPException as he:
        raise he
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error al responder al reagendamiento: {str(e)}"
        )

# ------------------------------
#  3) OBTENER REAGENDAMIENTOS PENDIENTES
# ------------------------------
@ruta_reserva.get("/reagendamientos/todos", response_model=list)
async def obtener_reagendamientos_pendientes():
    """
    Devuelve todos los reagendamientos en estado 'Pendiente Aprobacion'.
    """
    try:
        reagendamientos = base_datos.reagendamientos.find({"estado": "Pendiente Aprobacion"})
        reagendamientos_lista = [
            {
                "_id": str(r["_id"]),
                "codigoReserva": r["codigoReserva"],
                "FechaIngreso": r["FechaIngreso"],
                "FechaSalida": r["FechaSalida"],
                "estado": r["estado"],
                "fechaSolicitud": r["fechaSolicitud"]
            }
            for r in reagendamientos
        ]
        return reagendamientos_lista
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error al obtener los reagendamientos pendientes: {str(e)}"
        )
