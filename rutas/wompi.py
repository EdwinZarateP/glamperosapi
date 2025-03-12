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

# 🔑 Secreto de Integridad (modo sandbox o producción)
SECRETO_INTEGRIDAD = os.environ.get("WOMPI_INTEGRITY_SECRET", "prod_integrity_XXXXXXX")  
# Cambia esto por el tuyo, e.g. "test_integrity_abcd1234..."

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
    Crea una transacción con Wompi usando la llave privada y guarda el registro en la DB.
    Retorna el response de Wompi y la info que guardamos.
    """
    try:
        # 1. Prepara el payload para Wompi
        monto_en_centavos = int(payload.valorReserva * 100)  # Wompi usa centavos
        data_wompi = {
            "amount_in_cents": monto_en_centavos,
            "currency": payload.moneda,
            "customer_email": "correo@cliente.com",  # Ajusta según tu caso
            "payment_method": {
                "installments": 1
            },
            "reference": payload.referenciaInterna,  # Referencia única de tu sistema
            "payment_method_type": "CARD",
            "redirect_url": f"https://glamperos.com/gracias?referencia={payload.referenciaInterna}"
        }

        # 2. Llamada a la API de Wompi
        headers = {
            "Authorization": f"Bearer {WOMPI_PRIVATE_KEY}",
            "Content-Type": "application/json"
        }
        response = requests.post(WOMPI_API_URL, json=data_wompi, headers=headers)
        respuesta_wompi = response.json()

        # Verifica si hubo error en la llamada
        if response.status_code not in [200, 201]:
            raise HTTPException(
                status_code=response.status_code,
                detail=f"Error Wompi: {respuesta_wompi}"
            )

        # 3. Guardar la transacción en la DB
        nueva_transaccion = {
            "referenciaInterna": payload.referenciaInterna,
            "wompi_transaction_id": respuesta_wompi["data"]["id"],  # ID de Wompi
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
@ruta_wompi.post("/webhook", response_model=dict)
async def webhook_wompi(request: Request):
    """
    Endpoint para recibir notificaciones de Wompi (estado de la transacción).
    Aquí se actualiza el estado en la DB y se responde 200 si todo está OK.
    """
    try:
        evento = await request.json()

        # Extraer info relevante
        data = evento.get("data", {})
        transaction_id = data.get("transaction", {}).get("id")
        status = data.get("transaction", {}).get("status")
        referencia_interna = data.get("transaction", {}).get("reference")

        if not transaction_id or not status or not referencia_interna:
            raise HTTPException(
                status_code=400,
                detail="Faltan datos en el webhook de Wompi"
            )

        # Actualizar la transacción en DB
        coleccion_transacciones.update_one(
            {"wompi_transaction_id": transaction_id},
            {"$set": {"status": status}}
        )

        # Lógica adicional (e.g., actualizar reserva a 'Pagada')...

        return {"mensaje": "Webhook recibido correctamente", "estado": status}

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error en webhook: {str(e)}"
        )

# ============================================================================
# 3) CONSULTAR TRANSACCIÓN (opcional)
# ============================================================================
@ruta_wompi.get("/transaccion/{referencia}", response_model=dict)
async def obtener_transaccion_por_referencia(referencia: str):
    """
    Devuelve la info de una transacción guardada en la DB por su referencia interna.
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
