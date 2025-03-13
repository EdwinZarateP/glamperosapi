from fastapi import APIRouter, HTTPException, status, Body, Request
from pymongo import MongoClient
from datetime import datetime
from pydantic import BaseModel
import os
import requests
import hashlib
import time
from bson import ObjectId


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
            print("🔄 Esperando a que la reserva aparezca en la BD...")
            time.sleep(2)  # Esperar antes de intentar de nuevo

        if reserva:
            print(f"✅ Reserva {referencia_interna} encontrada, actualizando EstadoPago a '{status}'.")

            # Actualizar estado de pago de la reserva
            base_datos.reservas.update_one(
                {"codigoReserva": referencia_interna},
                {"$set": {"EstadoPago": "Pagado"}}
            )

            print("🔄 Estado de la reserva actualizado a 'Pagado'")

            # Obtener datos del propietario y del cliente
            id_propietario = reserva.get("idPropietario")
            id_cliente = reserva.get("idCliente")

            print(f"📌 ID Propietario recibido: {id_propietario}, ID Cliente recibido: {id_cliente}")

            # Validar si los IDs son ObjectId válidos antes de hacer la conversión
            propietario = None
            cliente = None

            try:
                if id_propietario and ObjectId.is_valid(id_propietario):
                    propietario = base_datos.usuarios.find_one({"_id": ObjectId(id_propietario)})
                else:
                    print("⚠️ id_propietario no es un ObjectId válido.")

                if id_cliente and ObjectId.is_valid(id_cliente):
                    cliente = base_datos.usuarios.find_one({"_id": ObjectId(id_cliente)})
                else:
                    print("⚠️ id_cliente no es un ObjectId válido.")
            except Exception as e:
                print(f"❌ Error al convertir IDs a ObjectId: {e}")

            # Verificar si se encontraron los datos
            if propietario:
                print(f"👤 Propietario encontrado: {propietario.get('nombre', 'Desconocido')}")
            else:
                print("⚠️ No se encontró el propietario en la base de datos.")

            if cliente:
                print(f"👤 Cliente encontrado: {cliente.get('nombre', 'Desconocido')}")
            else:
                print("⚠️ No se encontró el cliente en la base de datos.")


            if propietario and cliente:
                correo_propietario = {
                    "from_email": "reservas@glamperos.com",
                    "name": propietario.get("nombre", "Propietario"),
                    "email": propietario.get("email", ""),
                    "subject": "🚀 ¡Nueva Reserva Confirmada en tu Glamping!",
                    "html_content": f"""
                        <h2>Hola {propietario.get('nombre', 'Propietario')},</h2>
                        <p>¡Has recibido una nueva reserva en tu glamping!</p>
                        <h3>Detalles de la reserva:</h3>
                        <ul>
                            <li><b>Cliente:</b> {cliente.get('nombre', 'Cliente')}</li>
                            <li><b>Correo del cliente:</b> {cliente.get('email', 'No disponible')}</li>
                            <li><b>Teléfono del cliente:</b> {cliente.get('telefono', 'No disponible')}</li>
                            <li><b>Código de reserva:</b> {reserva.get('codigoReserva')}</li>
                            <li><b>Glamping:</b> {reserva.get('idGlamping')}</li>
                            <li><b>Ciudad:</b> {reserva.get('ciudad_departamento')}</li>
                            <li><b>Fecha de ingreso:</b> {reserva.get('FechaIngreso')}</li>
                            <li><b>Fecha de salida:</b> {reserva.get('FechaSalida')}</li>
                            <li><b>Noches:</b> {reserva.get('Noches')}</li>
                            <li><b>Huéspedes:</b> {reserva.get('adultos')} adultos, {reserva.get('ninos')} niños</li>
                            <li><b>Valor total:</b> COP {reserva.get('ValorReserva', 0):,.0f}</li>
                        </ul>
                        <p>Revisa más detalles en tu perfil de Glamperos.</p>
                        <p>¡Gracias por ser parte de nuestra comunidad!</p>
                    """
                }

                correo_cliente = {
                    "from_email": "reservas@glamperos.com",
                    "name": cliente.get("nombre", "Cliente"),
                    "email": cliente.get("email", ""),
                    "subject": "🏕️ ¡Tu Reserva en Glamperos está Confirmada!",
                    "html_content": f"""
                        <h2>Hola {cliente.get('nombre', 'Cliente')},</h2>
                        <p>¡Tu reserva en Glamperos ha sido confirmada!</p>
                        <h3>Detalles de la reserva:</h3>
                        <ul>
                            <li><b>Código de reserva:</b> {reserva.get('codigoReserva')}</li>
                            <li><b>Glamping:</b> {reserva.get('idGlamping')}</li>
                            <li><b>Ciudad:</b> {reserva.get('ciudad_departamento')}</li>
                            <li><b>Fecha de ingreso:</b> {reserva.get('FechaIngreso')}</li>
                            <li><b>Fecha de salida:</b> {reserva.get('FechaSalida')}</li>
                            <li><b>Noches:</b> {reserva.get('Noches')}</li>
                            <li><b>Huéspedes:</b> {reserva.get('adultos')} adultos, {reserva.get('ninos')} niños</li>
                            <li><b>Valor total:</b> COP {reserva.get('ValorReserva', 0):,.0f}</li>
                        </ul>
                        <p>¡Esperamos que disfrutes tu estadía! Puedes ver más detalles en tu perfil de Glamperos.</p>
                        <p>Gracias por reservar con nosotros. 🌿</p>
                    """
                }

                # Enviar correos usando la API de correos y mostrar respuestas para depuración
                try:
                    response_propietario = requests.post(CORREO_API_URL, json=correo_propietario)
                    response_cliente = requests.post(CORREO_API_URL, json=correo_cliente)
                    print("📧 Respuesta API Correo Propietario:", response_propietario.status_code, response_propietario.text)
                    print("📧 Respuesta API Correo Cliente:", response_cliente.status_code, response_cliente.text)
                except Exception as emailError:
                    print("❌ Error al enviar correos:", emailError)

                print("✅ Correos enviados correctamente.")

            else:
                print("⚠️ No se encontraron datos completos de usuario (propietario o cliente).")

        else:
            print(f"⚠️ No se encontró la reserva en la BD después de {intentos} intentos. NO se actualizará.")

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
