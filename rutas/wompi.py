from fastapi import APIRouter, HTTPException, status, Body, Request
from pymongo import MongoClient
from datetime import datetime, timedelta
from pydantic import BaseModel
import os
import requests
import hashlib
import time
import httpx
import asyncio

# Importar funciones de WhatsApp desde el módulo whatsapp_utils
from rutas.whatsapp_utils import enviar_whatsapp_cliente, enviar_whatsapp_propietario

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

ACTUALIZAR_FECHAS_API_URL = "https://glamperosapi.onrender.com/glampings"

async def reservar_fechas_glamping(id_glamping, fecha_ingreso, fecha_salida):
    """Genera las fechas de la reserva y las actualiza en la API (excluyendo la fecha de salida)."""
    try:
        # Si las fechas son datetime, convertirlas a string ISO
        if isinstance(fecha_ingreso, datetime):
            fecha_ingreso = fecha_ingreso.isoformat()
        if isinstance(fecha_salida, datetime):
            fecha_salida = fecha_salida.isoformat()
        if not isinstance(fecha_ingreso, str) or not isinstance(fecha_salida, str):
            raise ValueError(f"Las fechas no son cadenas de texto válidas: {fecha_ingreso}, {fecha_salida}")
        fecha_actual = datetime.fromisoformat(fecha_ingreso)
        fecha_fin = datetime.fromisoformat(fecha_salida)
        if fecha_actual >= fecha_fin:
            raise ValueError(f"Fecha de ingreso {fecha_ingreso} no puede ser mayor o igual a fecha de salida {fecha_salida}")
        fechas_a_reservar = []
        # Generar fechas hasta (pero sin incluir) la fecha de salida
        while fecha_actual < fecha_fin:
            fechas_a_reservar.append(fecha_actual.strftime("%Y-%m-%d"))
            fecha_actual += timedelta(days=1)
        print(f"📅 Fechas reservadas para el glamping {id_glamping}: {fechas_a_reservar}")
        async with httpx.AsyncClient() as client:
            response = await client.patch(
                f"{ACTUALIZAR_FECHAS_API_URL}/{id_glamping}/fechasReservadas",
                json={"fechas": fechas_a_reservar},
            )
            if response.status_code == 200:
                print("✅ Fechas reservadas correctamente en la API.")
            else:
                print(f"⚠️ Error al reservar fechas: {response.status_code} - {response.text}")
    except ValueError as e:
        print(f"❌ Error en las fechas proporcionadas: {str(e)}")
    except Exception as e:
        print(f"❌ Error general al generar las fechas de reserva: {str(e)}")

GLAMPEROS_GLAMPINGS_API_URL = "https://glamperosapi.onrender.com/glampings"

async def obtener_glamping(id_glamping):
    """Consulta la API de glampings para obtener la ubicación del glamping."""
    url = f"{GLAMPEROS_GLAMPINGS_API_URL}/{id_glamping}"
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(url, timeout=10)
            if response.status_code == 200:
                return response.json()
        except httpx.HTTPError:
            print(f"⚠️ Error al obtener datos del glamping {id_glamping}")
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
            "customer_email": "correo@cliente.com",  # Se debe cambiar por el real
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
            "transaccion": nueva_transaccion,
            "respuesta_wompi": respuesta_wompi
        }

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error al crear la transacción: {str(e)}"
        )

# ====================================================================
# ENDPOINT PARA WEBHOOK DE WOMPI CON ENVÍO DE CORREO Y WHATSAPP
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
        metodo_pago = transaction.get("payment_method_type", "Desconocido")
        if not transaction_id or not status or not referencia_interna:
            raise HTTPException(status_code=400, detail="Faltan datos en el webhook de Wompi")
        
        # ❌ Si la transacción no fue aprobada, registramos el error y terminamos
        if status != "APPROVED":
            print(f"❌ Transacción {transaction_id} fallida con estado: {status}. No se actualizará la reserva.")
            return {"mensaje": f"Transacción {transaction_id} fallida con estado {status}"}

        reserva = None
        for _ in range(5):
            reserva = base_datos.reservas.find_one({"codigoReserva": referencia_interna})
            if reserva:
                break
            print("🔄 Esperando a que la reserva aparezca en la BD")
            time.sleep(2)
        if reserva:
            print(f"✅ Reserva {referencia_interna} encontrada, actualizando EstadoPago a '{status}'.")
            base_datos.reservas.update_one(
                {"codigoReserva": referencia_interna},
                {
                    "$set": {
                        "EstadoPago": "Pagado",
                    }
                }
            )
            # Obtener datos del propietario, cliente y glamping desde la API
            id_propietario = reserva.get("idPropietario")
            id_cliente = reserva.get("idCliente")
            id_glamping = reserva.get("idGlamping")
            propietario = await obtener_usuario(id_propietario)
            cliente = await obtener_usuario(id_cliente)
            glamping = await obtener_glamping(id_glamping)
            # ✅ Reservar las fechas en la API (excluyendo la fecha de salida)
            if "FechaIngreso" in reserva and "FechaSalida" in reserva:
                await reservar_fechas_glamping(id_glamping, reserva["FechaIngreso"], reserva["FechaSalida"])
            if propietario and cliente:
                print("📧 Enviando correos de confirmación")
                def limpiar_numero(numero: str) -> str:
                    return numero[2:] if numero and numero.startswith("57") else numero
                telefono_propietario = limpiar_numero(propietario.get("telefono", "No disponible"))
                telefono_cliente = limpiar_numero(cliente.get("telefono", "No disponible"))
                if glamping and "ubicacion" in glamping:
                    latitud = glamping["ubicacion"].get("lat")
                    longitud = glamping["ubicacion"].get("lng")
                    print(f"📍 Latitud obtenida: {latitud}")
                    print(f"📍 Longitud obtenida: {longitud}")
                    if latitud and longitud:
                        ubicacion_link = f"https://www.google.com/maps?q={latitud},{longitud}"
                    else:
                        ubicacion_link = "Ubicación no disponible"
                else:
                    ubicacion_link = "Ubicación no disponible"
                    print("⚠️ No se encontró la ubicación del glamping en la API.")
                def convertir_fecha(fecha_raw):
                    if fecha_raw:
                        try:
                            return datetime.fromisoformat(str(fecha_raw)).strftime("%d %b %Y")
                        except ValueError:
                            return "Fecha no disponible"
                    return "Fecha no disponible"
                fecha_inicio = convertir_fecha(reserva.get("FechaIngreso"))
                fecha_fin = convertir_fecha(reserva.get("FechaSalida"))
                ocupacion = []
                if reserva.get("adultos", 0) > 0:
                    ocupacion.append(f"{reserva.get('adultos', 0)} Adultos")
                if reserva.get("ninos", 0) > 0:
                    ocupacion.append(f"{reserva.get('ninos', 0)} Niños")
                if reserva.get("bebes", 0) > 0:
                    ocupacion.append(f"{reserva.get('bebes', 0)} Bebés")
                if reserva.get("mascotas", 0) > 0:
                    ocupacion.append(f"{reserva.get('mascotas', 0)} Mascotas")
                ocupacion_texto = ", ".join(ocupacion) if ocupacion else "Sin información"
                mensaje_contacto = "<p>Si tienes preguntas, contacta a nuestro equipo en Glamperos al <strong>3218695196</strong>.</p>"
                correo_propietario = {
                    "from_email": "reservaciones@glamperos.com",
                    "email": propietario.get("email", ""),
                    "name": propietario.get("nombre", "Propietario"),
                    "subject": f"🎫 Reserva Confirmada - {glamping.get('nombreGlamping', 'Tu Glamping')}",
                    "html_content": f"""
                        <h2 style="color: #2F6B3E;">🎉 ¡Tienes una nueva reserva!</h2>
                        <p>Hola {propietario.get('nombre', 'Propietario').split(' ')[0]},</p>
                        <p>¡Han reservado <strong>{glamping.get('nombreGlamping', 'Tu Glamping')}</strong> a través de Glamperos!</p>
                        <p><strong>Código de Reserva:</strong> {reserva.get('codigoReserva')}</p>
                        <p><strong>Check-In:</strong> {fecha_inicio}</p>
                        <p><strong>Check-Out:</strong> {fecha_fin}</p>
                        <p><strong>Ocupación:</strong> {ocupacion_texto}</p>
                        <p><strong>Huésped:</strong> {cliente.get('nombre', 'Cliente')}</p>
                        <p><strong>Teléfono:</strong> {telefono_cliente}</p>
                        <p><strong>Correo:</strong> {cliente.get('email', 'No disponible')}</p>
                        <hr>
                        {mensaje_contacto}
                    """
                }
                correo_cliente = {
                    "from_email": "reservas@glamperos.com",
                    "email": cliente.get("email", ""),
                    "name": cliente.get("nombre", "Cliente"),
                    "subject": f"🧳 Confirmación Reserva Glamping - {glamping.get('nombreGlamping', 'Tu Glamping')}",
                    "html_content": f"""
                        <h2 style="color: #2F6B3E;">🎉 ¡Hora de relajarse!</h2>
                        <p>Hola {cliente.get('nombre', 'Cliente').split(' ')[0]},</p>
                        <p>¡Gracias por reservar con Glamperos! 🎉 Aquí están los detalles de tu reserva:</p>
                        <p><strong>Código de Reserva:</strong> {reserva.get('codigoReserva', 'No disponible')}</p>
                        <p><strong>Check-In:</strong> {fecha_inicio}</p>
                        <p><strong>Check-Out:</strong> {fecha_fin}</p>
                        <p><strong>Ocupación:</strong> {ocupacion_texto}</p>
                        <p><strong>Teléfono de tu anfitrión:</strong> {telefono_propietario}</p>
                        <p><strong>Ubicación:</strong> <a href="{ubicacion_link}" target="_blank">Ver en Google Maps</a></p>
                        <hr>
                        {mensaje_contacto}
                    """
                }
                async with httpx.AsyncClient() as client:
                    await client.post(CORREO_API_URL, json=correo_propietario)
                    await client.post(CORREO_API_URL, json=correo_cliente)
                # Enviar mensajes de WhatsApp utilizando las funciones importadas

                print(f"📲 Enviando WhatsApp...")
                print(f"📩 Teléfono del cliente: {telefono_cliente}")
                print(f"🏡 Teléfono del propietario: {telefono_propietario}")

                await enviar_whatsapp_propietario(
                    numero=telefono_propietario,
                    nombrePropietario=propietario.get("nombre", "Propietario"),
                    nombreGlamping=glamping.get("nombreGlamping", "Tu Glamping"),
                    fechaInicio=fecha_inicio,
                    fechaFin=f"{fecha_fin} - el whatsapp de tu huésped es {telefono_cliente}",
                    imagenUrl="https://storage.googleapis.com/glamperos-imagenes/Imagenes/animal1.jpeg"
                )
                await enviar_whatsapp_cliente(
                    numero=telefono_cliente,
                    codigoReserva=reserva.get("codigoReserva", "No disponible"),
                    whatsapp=telefono_propietario,
                    nombreGlampingReservado=glamping.get("nombreGlamping", "Tu Glamping"),
                    direccionGlamping=glamping.get("direccion", "Dirección no disponible"),
                    latitud=latitud or 0,
                    longitud=longitud or 0,
                    nombreCliente=cliente.get("nombre", "Cliente")
                )
            return {"mensaje": "Webhook recibido correctamente", "estado": status}
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
