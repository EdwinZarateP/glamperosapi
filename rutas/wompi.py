from fastapi import APIRouter, HTTPException, status, Body, Request
from pymongo import MongoClient
from datetime import datetime
from pydantic import BaseModel
import os
import requests
import hashlib

# ============================================================================
# CONFIGURACIÓN DE LA BASE DE DATOS
# ============================================================================
MONGO_URI = os.environ.get("MONGO_URI", "mongodb://localhost:27017")
ConexionMongo = MongoClient(MONGO_URI)
base_datos = ConexionMongo["glamperos"]

# ============================================================================
# CONFIGURACIÓN DE FASTAPI
# ============================================================================
ruta_wompi = APIRouter(
    prefix="/wompi",
    tags=["Wompi"],
    responses={status.HTTP_404_NOT_FOUND: {"message": "No encontrado"}},
)

# ============================================================================
# MODELOS DE DATOS
# ============================================================================
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

# ============================================================================
# CONFIGURACIÓN WOMPI
# ============================================================================
WOMPI_PRIVATE_KEY = os.environ.get("WOMPI_PRIVATE_KEY", "tu_llave_privada_sandbox")
WOMPI_PUBLIC_KEY = os.environ.get("WOMPI_PUBLIC_KEY", "tu_llave_publica_sandbox")
WOMPI_API_URL = "https://sandbox.wompi.co/v1/transactions"

# Secreto de Integridad (modo sandbox o producción)
SECRETO_INTEGRIDAD = os.environ.get("WOMPI_INTEGRITY_SECRET", "test_integrity_Yrpy71FNU9fwbR8BrLPWBUHKHiu9hVua")

# ============================================================================
# COLECCIÓN DE TRANSACCIONES
# ============================================================================
coleccion_transacciones = base_datos["transacciones_wompi"]

# ============================================================================
# ENDPOINT PARA GENERAR FIRMA DE INTEGRIDAD
# ============================================================================
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

# ============================================================================
# 1) CREAR TRANSACCIÓN
# ============================================================================
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
            "customer_email": "correo@cliente.com",  # Puedes ajustar para recibirlo desde el front
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

# ============================================================================
# 2) WEBHOOK DE WOMPI
# ============================================================================
from fastapi import APIRouter, HTTPException, Request
from pymongo import MongoClient
import os
import resend

# ============================================================================  
# CONFIGURACIÓN DE LA BASE DE DATOS  
# ============================================================================  
MONGO_URI = os.environ.get("MONGO_URI", "mongodb://localhost:27017")  
ConexionMongo = MongoClient(MONGO_URI)  
base_datos = ConexionMongo["glamperos"]

# ============================================================================  
# CONFIGURACIÓN RESEND (ENVÍO DE CORREOS)  
# ============================================================================  
resend.api_key = os.getenv("RESEND_API_KEY")  

ruta_wompi = APIRouter(
    prefix="/wompi",
    tags=["Wompi"],
)

# ============================================================================  
# FUNCIÓN PARA ENVIAR CORREO AL PROPIETARIO  
# ============================================================================  
def enviar_correo_propietario(destinatario, nombre_propietario, reserva):
    """Envía un correo de confirmación de pago al dueño del glamping."""
    try:
        asunto = "Nueva Reserva Pagada en Glamperos 🚀"
        html_content = f"""
        <h2>Hola {nombre_propietario},</h2>
        <p>¡Una nueva reserva ha sido confirmada en tu glamping!</p>
        <ul>
            <li><b>Código de reserva:</b> {reserva['codigoReserva']}</li>
            <li><b>Fecha de ingreso:</b> {reserva['FechaIngreso']}</li>
            <li><b>Fecha de salida:</b> {reserva['FechaSalida']}</li>
            <li><b>Noches:</b> {reserva['Noches']}</li>
            <li><b>Huéspedes:</b> {reserva['adultos']} adultos, {reserva['ninos']} niños</li>
            <li><b>Valor total:</b> COP {reserva['ValorReserva']:,.0f}</li>
        </ul>
        <p>Revisa los detalles en tu perfil de Glamperos.</p>
        <p>¡Gracias por ser parte de nuestra comunidad!</p>
        """

        response = resend.Emails.send({
            "from": "reservas@glamperos.com",
            "to": [destinatario],
            "subject": asunto,
            "html": html_content,
        })
        print("✅ Correo enviado al propietario:", response)
    except Exception as e:
        print("❌ Error al enviar correo:", str(e))

# ============================================================================  
# WEBHOOK DE WOMPI (ACTUALIZADO CON ENVÍO DE CORREO)  
# ============================================================================  
@ruta_wompi.post("/webhook", response_model=dict)
async def webhook_wompi(request: Request):
    """Recibe notificaciones de Wompi y envía un correo al propietario si el pago es aprobado."""
    try:
        evento = await request.json()
        transaction = evento.get("data", {}).get("transaction", {})
        transaction_id = transaction.get("id")
        status = transaction.get("status")
        referencia_interna = transaction.get("reference")

        if not transaction_id or not status or not referencia_interna:
            raise HTTPException(status_code=400, detail="Faltan datos en el webhook de Wompi")

        # Actualizar el estado del pago en la BD
        base_datos.transacciones_wompi.update_one(
            {"wompi_transaction_id": transaction_id},
            {"$set": {"status": status}}
        )

        if status == "APPROVED":
            print(f"✅ Pago aprobado para la referencia {referencia_interna}")

            # Buscar la reserva correspondiente
            reserva = base_datos.reservas.find_one({"codigoReserva": referencia_interna})
            if not reserva:
                print("⚠️ No se encontró la reserva en la base de datos.")
                return {"mensaje": "Reserva no encontrada"}

            # Actualizar estado de la reserva a "Pagado"
            base_datos.reservas.update_one(
                {"codigoReserva": referencia_interna},
                {"$set": {"EstadoPago": "Pagado"}}
            )

            # Obtener datos del propietario
            propietario = base_datos.usuarios.find_one({"_id": reserva["idPropietario"]})
            if propietario and "email" in propietario:
                enviar_correo_propietario(
                    destinatario=propietario["email"],
                    nombre_propietario=propietario["nombre"],
                    reserva=reserva
                )

        return {"mensaje": "Webhook recibido correctamente", "estado": status}

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error en webhook: {str(e)}")


# ============================================================================
# 3) CONSULTAR TRANSACCIÓN (opcional)
# ============================================================================
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
