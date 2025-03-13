from fastapi import APIRouter, HTTPException, status, Body, Request
from pymongo import MongoClient
from datetime import datetime
from pydantic import BaseModel
import os
import requests
import hashlib
import time
import requests
import httpx
import asyncio


# ====================================================================
# CONFIGURACIÓN DE LA BASE DE DATOS
# ====================================================================
MONGO_URI = os.environ.get("MONGO_URI", "mongodb://localhost:27017")
ConexionMongo = MongoClient(MONGO_URI)
base_datos = ConexionMongo["glamperos"]
coleccion_transacciones = base_datos["transacciones_wompi"]

# ====================================================================
# CONFIGURACIÓN DE FASTAPI
# ====================================================================
# Definición única del router
ruta_wompi = APIRouter(
    prefix="/wompi",
    tags=["Wompi"],
    responses={status.HTTP_404_NOT_FOUND: {"message": "No encontrado"}},
)

# URL de la API de usuarios
GLAMPEROS_API_URL = "https://glamperosapi.onrender.com/usuarios"



async def obtener_usuario(id_usuario, intentos_maximos=3):
    """Consulta la API de usuarios con reintentos en caso de error."""
    url = f"{GLAMPEROS_API_URL}/{id_usuario}"
    
    async with httpx.AsyncClient() as client:
        for intento in range(intentos_maximos):
            try:
                print(f"🔍 Intento {intento + 1}/{intentos_maximos} - Consultando usuario {id_usuario} en {url}...")
                response = await client.get(url, timeout=10)
                
                if response.status_code == 200:
                    return response.json()
                
                print(f"⚠️ Error al obtener usuario {id_usuario}: {response.status_code} - {response.text}")
            except httpx.TimeoutException:
                print(f"⏳ Tiempo de espera agotado en intento {intento + 1}.")
            except httpx.RequestError as e:
                print(f"❌ Error en la solicitud a la API de usuarios: {e}")

            await asyncio.sleep(1)

    print(f"🚨 No se pudo obtener información del usuario {id_usuario} después de {intentos_maximos} intentos.")
    return None


# ====================================================================
# MODELOS DE DATOS
# ====================================================================
class CrearTransaccionRequest(BaseModel):
    """Modelo para la creación de transacciones con Wompi."""
    valorReserva: float
    moneda: str = "COP"
    referenciaInterna: str
    descripcion: str

class TransaccionDB(BaseModel):
    """Modelo que representa cómo guardaremos la transacción en nuestra DB."""
    referenciaInterna: str
    wompi_transaction_id: str = None
    monto: float
    currency: str
    status: str
    created_at: datetime = datetime.now()

def modelo_transaccion_db(doc) -> dict:
    """Convierte el documento de MongoDB a dict para devolverlo en la respuesta."""
    return {
        "id": str(doc["_id"]),
        "referenciaInterna": doc["referenciaInterna"],
        "wompi_transaction_id": doc.get("wompi_transaction_id"),
        "monto": doc["monto"],
        "currency": doc["currency"],
        "status": doc["status"],
        "created_at": doc["created_at"],
    }

# ====================================================================
# CONFIGURACIÓN WOMPI
# ====================================================================
WOMPI_PRIVATE_KEY = os.environ.get("WOMPI_PRIVATE_KEY", "tu_llave_privada_sandbox")
WOMPI_PUBLIC_KEY = os.environ.get("WOMPI_PUBLIC_KEY", "tu_llave_publica_sandbox")
WOMPI_API_URL = "https://sandbox.wompi.co/v1/transactions"
SECRETO_INTEGRIDAD = os.environ.get("WOMPI_INTEGRITY_SECRET", "test_integrity_Yrpy71FNU9fwbR8BrLPWBUHKHiu9hVua")

# ====================================================================
# ENDPOINT PARA GENERAR FIRMA DE INTEGRIDAD
# ====================================================================
@ruta_wompi.get("/generar-firma", response_model=dict)
async def generar_firma(referencia: str, monto: int, moneda: str = "COP"):
    """
    Genera la firma de integridad (SHA-256) para Wompi.
    Formato: <referencia><monto><moneda><secreto_integridad>
    """
    try:
        cadena_concatenada = f"{referencia}{monto}{moneda}{SECRETO_INTEGRIDAD}"
        firma_integridad = hashlib.sha256(cadena_concatenada.encode()).hexdigest()
        return {"firma_integridad": firma_integridad}
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error al generar la firma: {str(e)}"
        )

# ====================================================================
# ENDPOINT PARA CREAR TRANSACCIÓN
# ====================================================================
@ruta_wompi.post("/crear-transaccion", response_model=dict)
async def crear_transaccion(payload: CrearTransaccionRequest):
    """
    Crea un registro de transacción pendiente en la DB y llama a la API de Wompi.
    La reserva real se actualizará cuando se confirme el pago vía webhook.
    """
    try:
        monto_en_centavos = int(payload.valorReserva * 100)
        data_wompi = {
            "amount_in_cents": monto_en_centavos,
            "currency": payload.moneda,
            "customer_email": "correo@cliente.com",  # Ajusta según lo recibido desde el front
            "payment_method": {"installments": 1},
            "reference": payload.referenciaInterna,
            "payment_method_type": "CARD",
            "redirect_url": f"https://glamperos.com/gracias?referencia={payload.referenciaInterna}"
        }
        headers = {
            "Authorization": f"Bearer {WOMPI_PRIVATE_KEY}",
            "Content-Type": "application/json"
        }
        response = requests.post(WOMPI_API_URL, json=data_wompi, headers=headers)
        respuesta_wompi = response.json()

        if response.status_code not in [200, 201]:
            raise HTTPException(
                status_code=response.status_code,
                detail=f"Error Wompi: {respuesta_wompi}"
            )

        nueva_transaccion = {
            "referenciaInterna": payload.referenciaInterna,
            "wompi_transaction_id": respuesta_wompi["data"]["id"],
            "monto": payload.valorReserva,
            "currency": payload.moneda,
            "status": respuesta_wompi["data"]["status"],
            "created_at": datetime.now()
        }
        resultado = coleccion_transacciones.insert_one(nueva_transaccion)
        nueva_transaccion["_id"] = resultado.inserted_id

        return {
            "mensaje": "Transacción creada con éxito",
            "transaccion": modelo_transaccion_db(nueva_transaccion),
            "respuesta_wompi": respuesta_wompi
        }
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error al crear la transacción: {str(e)}"
        )

# ====================================================================
# ENDPOINT PARA WEBHOOK DE WOMPI CON ENVÍO DE CORREO
# ====================================================================
# URL de la API de correos (ajústala según tu configuración)
CORREO_API_URL = "https://glamperosapi.onrender.com/correos/send-email"

@ruta_wompi.post("/webhook", response_model=dict)
async def webhook_wompi(request: Request):
    try:
        evento = await request.json()
        print("📩 Webhook recibido:", evento)

        transaction = evento.get("data", {}).get("transaction", {})
        transaction_id = transaction.get("id")
        status = transaction.get("status")
        referencia_interna = transaction.get("reference")

        if not transaction_id or not status or not referencia_interna:
            raise HTTPException(status_code=400, detail="Faltan datos en el webhook de Wompi")

        # 🔄 Intentar buscar la reserva hasta 5 veces con un delay de 2 segundos entre cada intento
        reserva = None
        intentos = 5
        for _ in range(intentos):
            reserva = base_datos.reservas.find_one({"codigoReserva": referencia_interna})
            if reserva:
                break
            print("🔄 Esperando a que la reserva aparezca en la BD")
            time.sleep(2)

        if reserva:
            print(f"✅ Reserva {referencia_interna} encontrada, actualizando EstadoPago a '{status}'.")
            base_datos.reservas.update_one(
                {"codigoReserva": referencia_interna},
                {"$set": {"EstadoPago": "Pagado"}}
            )
            print("🔄 Estado de la reserva actualizado a 'Pagado'")

            # Obtener datos del propietario y del cliente desde la API de usuarios
            id_propietario = reserva.get("idPropietario")
            id_cliente = reserva.get("idCliente")

            print(f"📌 ID Propietario recibido: {id_propietario}, ID Cliente recibido: {id_cliente}")

            propietario = await obtener_usuario(id_propietario)
            cliente = await obtener_usuario(id_cliente)

            if propietario and cliente:
                print("📧 Enviando correos de confirmación")

                # Convertir fechas a formato amigable con validaciones
                fecha_inicio_raw = reserva.get("FechaIngreso")
                fecha_fin_raw = reserva.get("FechaSalida")

                try:
                    fecha_inicio = datetime.strptime(fecha_inicio_raw, "%Y-%m-%d").strftime("%d %b %Y") if fecha_inicio_raw else "Fecha no disponible"
                except Exception as e:
                    print(f"⚠️ Error al formatear FechaIngreso: {e}")
                    fecha_inicio = "Fecha no disponible"

                try:
                    fecha_fin = datetime.strptime(fecha_fin_raw, "%Y-%m-%d").strftime("%d %b %Y") if fecha_fin_raw else "Fecha no disponible"
                except Exception as e:
                    print(f"⚠️ Error al formatear FechaSalida: {e}")
                    fecha_fin = "Fecha no disponible"

                # Formato de correo del propietario
                correo_propietario = {
                    "from_email": "reservaciones@glamperos.com",
                    "email": propietario.get("email", ""),
                    "name": propietario.get("nombre", "Propietario"),
                    "subject": f"🎫 Reserva Confirmada - {reserva.get('glampingNombre', 'Tu Glamping')}",
                    "html_content": f"""
                        <h2 style="color: #2F6B3E;">🎉 ¡Tienes una nueva reserva!</h2>
                        <p>Hola {propietario.get('nombre', 'Propietario').split(' ')[0]},</p>
                        <p>¡Han reservado <strong>{reserva.get('glampingNombre', 'Tu Glamping')}</strong> a través de Glamperos!</p>
                        <p><strong>Código de Reserva:</strong> {reserva.get('codigoReserva')}</p>
                        <p><strong>Check-In:</strong> {fecha_inicio}</p>
                        <p><strong>Check-Out:</strong> {fecha_fin}</p>
                        <p><strong>Adultos:</strong> {reserva.get('adultos', 0)}</p>
                        <p><strong>Niños:</strong> {reserva.get('ninos', 0)}</p>
                        <p><strong>Mascotas:</strong> {reserva.get('mascotas', 0)}</p>
                        <p><strong>Huésped:</strong> {cliente.get('nombre', 'Cliente')}</p>
                        <p><strong>Teléfono:</strong> {cliente.get('telefono', 'No disponible')}</p>
                        <p><strong>Correo:</strong> {cliente.get('email', 'No disponible')}</p>
                        <hr>
                        <p style="color: #777;">Si tienes preguntas, contacta a nuestro equipo en Glamperos.</p>
                    """
                }

                # Formato de correo del cliente
                correo_cliente = {
                    "from_email": "reservas@glamperos.com",
                    "email": cliente.get("email", ""),
                    "name": cliente.get("nombre", "Cliente"),
                    "subject": f"🧳 Confirmación Reserva Glamping - {reserva.get('glampingNombre', 'Tu Glamping')}",
                    "html_content": f"""
                        <h2 style="color: #2F6B3E;">🎉 ¡Hora de relajarse!</h2>
                        <p>Hola {cliente.get('nombre', 'Cliente').split(' ')[0]},</p>
                        <p>¡Gracias por reservar con Glamperos! 🎉 Aquí están los detalles de tu reserva:</p>
                        <p><strong>Código de Reserva:</strong> {reserva.get('codigoReserva')}</p>
                        <p><strong>Check-In:</strong> {fecha_inicio}</p>
                        <p><strong>Check-Out:</strong> {fecha_fin}</p>
                        <p><strong>Adultos:</strong> {reserva.get('adultos', 0)}</p>
                        <p><strong>Niños:</strong> {reserva.get('ninos', 0)}</p>
                        <p><strong>Mascotas:</strong> {reserva.get('mascotas', 0)}</p>
                        <p>Si necesitas ayuda, nuestro equipo siempre estará aquí para ti.</p>
                        <hr>
                        <p style="color: #777;">Cualquier duda, puedes contactarnos en Glamperos.</p>
                    """
                }

                # 🚀 Enviar correos usando la API
                try:
                    async with httpx.AsyncClient() as client:
                        response_propietario = await client.post(CORREO_API_URL, json=correo_propietario)
                        response_cliente = await client.post(CORREO_API_URL, json=correo_cliente)

                    print("📧 Respuesta API Correo Propietario:", response_propietario.status_code, response_propietario.text)
                    print("📧 Respuesta API Correo Cliente:", response_cliente.status_code, response_cliente.text)
                except Exception as emailError:
                    print("❌ Error al enviar correos:", emailError)

            return {"mensaje": "Webhook recibido correctamente", "estado": status}

        else:
            print(f"⚠️ No se encontró la reserva en la BD después de {intentos} intentos.")

    except Exception as e:
        print(f"⚠️ Error en el webhook: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error en webhook: {str(e)}")

# ====================================================================
# ENDPOINT PARA CONSULTAR TRANSACCIÓN (opcional)
# ====================================================================
@ruta_wompi.get("/transaccion/{referencia}", response_model=dict)
async def obtener_transaccion_por_referencia(referencia: str):
    """
    Devuelve la info de una transacción registrada en la DB usando la referencia.
    """
    try:
        transaccion = coleccion_transacciones.find_one({"referenciaInterna": referencia})
        if not transaccion:
            raise HTTPException(
                status_code=404,
                detail=f"No se encontró transacción con la referencia {referencia}"
            )
        return {
            "mensaje": "Transacción encontrada",
            "transaccion": modelo_transaccion_db(transaccion)
        }
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error al consultar la transacción: {str(e)}"
        )
