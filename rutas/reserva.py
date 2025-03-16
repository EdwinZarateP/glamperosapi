from fastapi import APIRouter, HTTPException, status, Body
from pymongo import MongoClient
from bson import ObjectId
from pydantic import BaseModel
from datetime import datetime, timezone  # ✅ Importa datetime también # Para UTC
import pytz  # Para manejar zonas horarias específicas
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
    EstadoPagoProp: str = "Pendiente" 
    MetodoPago: str = None
    FechaPagoPropietario: datetime = None
    ReferenciaPago: str = None
    codigoReserva: str  # 🔥 Agrega esta línea para que FastAPI lo acepte


class ActualizarReserva(BaseModel):
    EstadoReserva: str
    ComentariosCancelacion: str

class ActualizarPago(BaseModel):
    EstadoPago: str
    MetodoPago: str
    EstadoPagoProp: str = "Pendiente" 
    FechaPagoPropietario: datetime
    ReferenciaPago: str

class ActualizarSolicitudPago(BaseModel):
    Estado: str
    FechaPagoPropietario: datetime
    ReferenciaPago: str

# ============================================================================
# CONVERTIR FECHAS A UTC
# ============================================================================
def convertir_a_utc(fecha: datetime) -> datetime:
    if fecha.tzinfo is None:
        return fecha.replace(tzinfo=timezone.utc)  # ✅ Esto ahora funcionará
    return fecha.astimezone(timezone.utc)

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
        "fechaCreacion": datetime.now(timezone.utc),
        "codigoReserva": reserva["codigoReserva"],
        "ComentariosCancelacion": reserva["ComentariosCancelacion"],
        "EstadoPago": reserva.get("EstadoPago", "Pendiente"),
        "EstadoPagoProp": reserva.get("EstadoPagoProp", "Pendiente"), 
        "MetodoPago": reserva.get("MetodoPago"),
        "FechaPagoPropietario": reserva.get("FechaPagoPropietario"),
        "ReferenciaPago": reserva.get("ReferenciaPago"),
    }

# ============================================================================
# CONFIGURACIÓN DE ZONA HORARIA
# ============================================================================
ZONA_HORARIA_COLOMBIA = pytz.timezone("America/Bogota")  # ✅ Esto funciona correctamente

# ============================================================================
# CREAR RESERVA
# ============================================================================
@ruta_reserva.post("/", response_model=dict)
async def crear_reserva(reserva: Reserva):
    try:
        # 🔹 Verificar si el codigoReserva ya existe
        if base_datos.reservas.find_one({"codigoReserva": reserva.codigoReserva}):
            raise HTTPException(
                status_code=400, detail="El código de reserva ya existe. Intenta nuevamente."
            )
        fecha_creacion_utc = datetime.now(timezone.utc)  # ✅ Ahora sí funcionará correctamente
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
            "fechaCreacion": fecha_creacion_utc ,
            "codigoReserva": reserva.codigoReserva,
            "ComentariosCancelacion": reserva.ComentariosCancelacion,
            "EstadoPago": reserva.EstadoPago,
             "EstadoPagoProp": reserva.EstadoPagoProp,
            "MetodoPago": reserva.MetodoPago,
            "FechaPagoPropietario": reserva.FechaPagoPropietario,
            "ReferenciaPago": reserva.ReferenciaPago,
        }

        result = base_datos.reservas.insert_one(nueva_reserva)
        nueva_reserva["_id"] = result.inserted_id

        return {
            "mensaje": "Reserva creada exitosamente",
            "reserva": modelo_reserva(nueva_reserva),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al crear la reserva: {str(e)}")

# ============================================================================
# CONSULTAR RESERVAS DEL PROPIETARIO
# ============================================================================
@ruta_reserva.get("/documentos/{idPropietario}", response_model=list)
async def obtener_documentos_por_propietario(idPropietario: str):

    try:
        documentos = base_datos.reservas.find({
            "idPropietario": idPropietario,
            "EstadoPago": "Pagado"  # ✅ CORRECTO: Se usa un string
        })

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
    try:
        documentos = base_datos.reservas.find({
            "idCliente": idCliente,
            "EstadoPago": "Pagado"  # ✅ CORRECTO
        })

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
@ruta_reserva.put("/pago_por_codigo/{codigoReserva}", response_model=dict)
async def actualizar_pago_reserva_por_codigo(
    codigoReserva: str,
    pago: ActualizarPago = Body(...)
):
    """
    Actualiza el pago de la reserva que tenga el codigoReserva indicado.
    Esto permite actualizar múltiples reservas iterando sobre codigosReserva.
    """
    try:
        # Buscar la reserva por su codigoReserva
        reserva = base_datos.reservas.find_one({"codigoReserva": codigoReserva})
        if not reserva:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"No se encontró la reserva con el código {codigoReserva}"
            )

        update_data = {
            "EstadoPago": pago.EstadoPago,
            "EstadoPagoProp": pago.EstadoPagoProp,
            "MetodoPago": pago.MetodoPago,
            "FechaPagoPropietario": pago.FechaPagoPropietario,
            "ReferenciaPago": pago.ReferenciaPago,
        }

        resultado = base_datos.reservas.update_one(
            {"codigoReserva": codigoReserva},
            {"$set": update_data}
        )

        if resultado.modified_count == 0:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No se pudo actualizar la reserva (ya está pagada o no coincide el código)."
            )

        reserva_actualizada = base_datos.reservas.find_one({"codigoReserva": codigoReserva})
        return {
            "mensaje": "Pago actualizado correctamente por codigoReserva",
            "reserva": modelo_reserva(reserva_actualizada),
        }

    except HTTPException as he:
        raise he
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error al actualizar el pago por codigoReserva: {str(e)}"
        )


# ============================================================================
# OBTENER RESERVAS PENDIENTES DE PAGO (COMPLETADAS) PARA UN PROPIETARIO
# ============================================================================
@ruta_reserva.get("/pendientes_pago/{idPropietario}", response_model=list)
async def obtener_reservas_pendientes_pago(idPropietario: str):

    try:
        reservas_pendientes = base_datos.reservas.find({
            "idPropietario": idPropietario,
            "EstadoPagoProp": "Pendiente",
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
    try:
        idPropietario = payload.get("idPropietario")
        metodoPago = payload.get("metodoPago")
        numeroCuenta = payload.get("numeroCuenta") 
        if not idPropietario or not metodoPago:
            raise HTTPException(
                status_code=400,
                detail="Se requieren idPropietario y metodoPago"
            )

        # Obtener reservas pendientes
        reservas_pendientes = list(base_datos.reservas.find({
            "idPropietario": idPropietario,
            "EstadoPagoProp": "Pendiente",
            "EstadoReserva": "Completada"
        }))

        saldo_disponible = sum(reserva.get("CostoGlamping", 0) for reserva in reservas_pendientes)
        if saldo_disponible <= 0:
            raise HTTPException(
                status_code=400,
                detail="No hay saldo disponible para retirar"
            )

        codigos_reserva = [reserva.get("codigoReserva") for reserva in reservas_pendientes]

        # Marcar reservas como "Solicitado"
        base_datos.reservas.update_many(
            {
                "idPropietario": idPropietario,
                "EstadoPagoProp": "Pendiente",
                "EstadoReserva": "Completada"
            },
            {"$set": {"EstadoPagoProp": "Solicitado"}}
        )

        # Crear solicitud de pago
        nueva_solicitud = {
            "idPropietario": idPropietario,
            "MontoSolicitado": saldo_disponible,
            "Estado": "Pendiente",
            "MetodoPago": metodoPago,
            "numeroCuenta": numeroCuenta, 
            "FechaSolicitud": datetime.now(timezone.utc),
            "FechaPagoPropietario": None,
            "ReferenciaPago": None,
            "codigosReserva": codigos_reserva if codigos_reserva else ["No disponibles"],
        }

        # Insertar en la base de datos y recuperar el ID
        result = base_datos.solicitudes_pago.insert_one(nueva_solicitud)
        nueva_solicitud["_id"] = str(result.inserted_id)  # Convertir ObjectId a string

        return {
            "mensaje": "Solicitud de pago enviada exitosamente",
            "solicitud": nueva_solicitud,  # 🔹 Ahora se devuelve el objeto completo
        }

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
    try:
        solicitudes = base_datos.solicitudes_pago.find({"idPropietario": idPropietario})
        solicitudes_lista = []
        for sol in solicitudes:
          sol["_id"] = str(sol["_id"])  # Convertir ObjectId a string
          sol["Estado"] = sol.get("Estado", "Pendiente")
          sol["FechaSolicitud"] = sol.get("FechaSolicitud", "No disponible")
          sol["FechaPagoPropietario"] = sol.get("FechaPagoPropietario", "Pendiente")
          sol["ReferenciaPago"] = sol.get("ReferenciaPago", "No disponible")
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
ZONA_HORARIA_COLOMBIA = pytz.timezone("America/Bogota")

@ruta_reserva.put("/actualizar_solicitud_pago/{solicitud_id}", response_model=dict)
async def actualizar_solicitud_pago(solicitud_id: str, actualizacion: ActualizarSolicitudPago = Body(...)):
    try:
        object_id = ObjectId(solicitud_id)

        # Convertimos la fecha actual a la zona horaria de Colombia
        fecha_pago_colombia = datetime.now().astimezone(ZONA_HORARIA_COLOMBIA)

        update_data = {
            "Estado": actualizacion.Estado,
            "FechaPagoPropietario": convertir_a_utc(actualizacion.FechaPagoPropietario),
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


# Devuelve todas las solicitudes de pago 
@ruta_reserva.get("/solicitudes_pago_pendientes", response_model=list)
async def obtener_solicitudes_pago_pendientes():
    """
    Devuelve todas las solicitudes de pago con estado "Pendiente"
    para que el área contable pueda procesarlas.
    """
    try:
        solicitudes = base_datos.solicitudes_pago.find({"Estado": "Pendiente"})
        solicitudes_lista = []
        
        for sol in solicitudes:
            sol["_id"] = str(sol["_id"])  # Convertir ObjectId a string
            sol["Estado"] = sol.get("Estado", "Pendiente")
            sol["FechaSolicitud"] = sol.get("FechaSolicitud", "No disponible")
            sol["FechaPagoPropietario"] = sol.get("FechaPagoPropietario", "Pendiente")
            sol["ReferenciaPago"] = sol.get("ReferenciaPago", "No disponible")
            sol["MetodoPago"] = sol.get("MetodoPago", "No registrado")
            solicitudes_lista.append(sol)

        return solicitudes_lista
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error al obtener solicitudes de pago pendientes: {str(e)}"
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
    try:
        resultado = base_datos.reservas.find_one_and_update(
            {"codigoReserva": data.codigoReserva},
            {"$set": {"EstadoReserva": "Solicitud Reagendamiento"}}
        )

        if not resultado:
            raise HTTPException(
                status_code=404,
                detail=f"No existe una reserva con el código {data.codigoReserva}"
            )

        nuevo_reagendamiento = {
            "codigoReserva": data.codigoReserva,
            "FechaIngreso": data.FechaIngreso.isoformat(),
            "FechaSalida": data.FechaSalida.isoformat(),
            "estado": "Pendiente Aprobacion",
            "fechaSolicitud": datetime.now().astimezone(ZONA_HORARIA_COLOMBIA).isoformat(),
        }
        result = base_datos.reagendamientos.insert_one(nuevo_reagendamiento)
        nuevo_reagendamiento["_id"] = str(result.inserted_id)  # 🔥 Convertir ObjectId a string

        return {
            "mensaje": "Reagendamiento solicitado exitosamente",
            "reagendamiento": nuevo_reagendamiento
        }

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
    try:
        reagendamiento = base_datos.reagendamientos.find_one({"codigoReserva": codigoReserva})
        if not reagendamiento:
            raise HTTPException(
                status_code=404,
                detail=f"No se encontró un reagendamiento para el código {codigoReserva}"
            )
        
        # 🔹 Actualizar el estado del reagendamiento en la colección 'reagendamientos'
        base_datos.reagendamientos.update_one(
            {"_id": reagendamiento["_id"]},
            {"$set": {"estado": actualizacion.estado}}
        )

        if actualizacion.estado.lower() == "aprobado":
            if "FechaIngreso" not in reagendamiento or "FechaSalida" not in reagendamiento:
                raise HTTPException(status_code=400, detail="Faltan fechas en el reagendamiento")

            nueva_entrada = reagendamiento["FechaIngreso"]
            nueva_salida = reagendamiento["FechaSalida"]

            # 🔹 Si se aprueba, actualizar fechas en la colección 'reservas' pero NO el estado
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

        else:  # 🔹 Si se rechaza, actualizar la reserva a "Reserva no reagendada"
            resultado_reserva = base_datos.reservas.update_one(
                {"codigoReserva": codigoReserva},
                {"$set": {"EstadoReserva": "Reserva no reagendada"}}
            )

            if resultado_reserva.modified_count == 0:
                raise HTTPException(
                    status_code=404,
                    detail="No se pudo actualizar la reserva tras rechazar el reagendamiento"
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

@ruta_reserva.put("/estado/{codigoReserva}", response_model=dict)
async def actualizar_estado_reserva_por_codigo(codigoReserva: str, actualizacion: dict = Body(...)):
    try:
        # 🔥 Buscar la reserva primero
        reserva_actual = base_datos.reservas.find_one({"codigoReserva": codigoReserva})
        if not reserva_actual:
            raise HTTPException(status_code=404, detail="No se encontró la reserva")

        # 🔥 Evitar actualizar si ya tiene el mismo estado
        if reserva_actual["EstadoReserva"] == actualizacion.get("EstadoReserva"):
            return {"mensaje": "El estado ya estaba actualizado", "reserva": modelo_reserva(reserva_actual)}

        # Actualizar solo si es necesario
        resultado = base_datos.reservas.update_one(
            {"codigoReserva": codigoReserva},
            {"$set": {"EstadoReserva": actualizacion.get("EstadoReserva")}}
        )

        # Obtener la reserva actualizada
        reserva_actualizada = base_datos.reservas.find_one({"codigoReserva": codigoReserva})
        return {
            "mensaje": "Estado de la reserva actualizado correctamente",
            "reserva": modelo_reserva(reserva_actualizada),
        }

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error al actualizar el estado de la reserva: {str(e)}"
        )

# ========================================================================
# ENDPOINT PARA ACTUALIZAR AUTOMÁTICAMENTE RESERVAS A "Completada"
# ========================================================================
@ruta_reserva.post("/actualizar-reservas", response_model=dict)
async def actualizar_reservas():
    """
    Este endpoint revisa todas las reservas con EstadoReserva "Reservada" cuya FechaSalida sea hoy o en el futuro
    y actualiza su EstadoReserva a "Completada".
    """
    try:
        # 🔹 Obtener la fecha actual en la zona horaria de Colombia
        ZONA_HORARIA_COLOMBIA = pytz.timezone("America/Bogota")
        hoy = datetime.now(ZONA_HORARIA_COLOMBIA).date()

        # 🔹 Buscar reservas cuya FechaSalida sea HOY o en el FUTURO y que sigan en "Reservada"
        filtro = {
            "FechaSalida": {
                "$gte": datetime(hoy.year, hoy.month, hoy.day, 0, 0, 0)
            },
            "EstadoReserva": "Reservada"  # Solo cambiar las que aún están en "Reservada"
        }

        # 🔹 Actualizar esas reservas a "Completada"
        resultado = base_datos.reservas.update_many(filtro, {"$set": {"EstadoReserva": "Completada"}})

        return {"message": f"✅ {resultado.modified_count} reservas han sido marcadas como 'Completada'."}
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"❌ Error al actualizar reservas: {str(e)}")