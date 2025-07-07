from fastapi import APIRouter, HTTPException, status, Body
from pymongo import MongoClient
from bson import ObjectId
from pydantic import BaseModel
from datetime import datetime, timezone
import os
import random
import string

# ====================================================
# CONFIGURACIÓN DE MONGO
# ====================================================
MONGO_URI = os.environ.get("MONGO_URI", "mongodb://localhost:27017")
conexion = MongoClient(MONGO_URI)
db = conexion["glamperos"]

# ====================================================
# CONFIGURACIÓN DE FASTAPI
# ====================================================
ruta_bonos = APIRouter(
    prefix="/bonos",
    tags=["Bonos"],
    responses={status.HTTP_404_NOT_FOUND: {"message": "No encontrado"}},
)

# ====================================================
# MODELOS
# ====================================================
class CompraBonosRequest(BaseModel):
    idComprador: str
    listaValores: list[int]  # Ej: [100000, 200000]

class RedimirBonoRequest(BaseModel):
    codigo: str
    idUsuario: str

# ====================================================
# UTILIDADES
# ====================================================
def generar_codigo_bono(longitud=8):
    prefijo = "GIFT-"
    caracteres = string.ascii_uppercase + string.digits
    codigo = ''.join(random.choice(caracteres) for _ in range(longitud))
    return prefijo + codigo

def modelo_bono(bono) -> dict:
    return {
        "id": str(bono["_id"]),
        "codigo": bono["codigo"],
        "valor": bono["valor"],
        "compradoPor": bono.get("compradoPor"),
        "fechaCompra": bono["fechaCompra"],
        "redimidoPor": bono.get("redimidoPor"),
        "fechaRedencion": bono.get("fechaRedencion"),
        "estado": bono["estado"],
    }

# ====================================================
# ENDPOINTS
# ====================================================

# ✅ 1. Comprar bonos (compra masiva)
@ruta_bonos.post("/comprar", response_model=dict)
async def comprar_bonos(payload: CompraBonosRequest):
    bonos_creados = []
    fecha_actual = datetime.now(timezone.utc)
    for valor in payload.listaValores:
        codigo_unico = generar_codigo_bono()
        while db.bonos.find_one({"codigo": codigo_unico}):
            codigo_unico = generar_codigo_bono()  # Genera otro si colisiona

        nuevo_bono = {
            "codigo": codigo_unico,
            "valor": valor,
            "compradoPor": payload.idComprador,
            "fechaCompra": fecha_actual,
            "redimidoPor": None,
            "fechaRedencion": None,
            "estado": "activo",
        }
        result = db.bonos.insert_one(nuevo_bono)
        nuevo_bono["_id"] = result.inserted_id
        bonos_creados.append(modelo_bono(nuevo_bono))
    
    return {
        "mensaje": f"{len(bonos_creados)} bonos comprados exitosamente",
        "bonos": bonos_creados,
    }

# ✅ 2. Validar bono
@ruta_bonos.get("/validar/{codigo}", response_model=dict)
async def validar_bono(codigo: str):
    bono = db.bonos.find_one({"codigo": codigo})
    if not bono:
        return {"valido": False}
    if bono["estado"] != "activo":
        return {"valido": False}
    return {
        "valido": True,
        "valor": bono["valor"],
        "estado": bono["estado"],
    }

# ✅ 3. Redimir bono
@ruta_bonos.post("/redimir", response_model=dict)
async def redimir_bono(payload: RedimirBonoRequest):
    bono = db.bonos.find_one({"codigo": payload.codigo})
    if not bono:
        raise HTTPException(status_code=404, detail="Bono no encontrado")
    if bono["estado"] != "activo":
        raise HTTPException(status_code=400, detail="Bono no está activo o ya fue usado")

    fecha_redencion = datetime.now(timezone.utc)

    db.bonos.update_one(
        {"_id": bono["_id"]},
        {
            "$set": {
                "estado": "redimido",
                "redimidoPor": payload.idUsuario,
                "fechaRedencion": fecha_redencion
            }
        }
    )
    bono_actualizado = db.bonos.find_one({"_id": bono["_id"]})
    return {
        "mensaje": "Bono redimido exitosamente",
        "bono": modelo_bono(bono_actualizado)
    }

# ✅ 4. Listar bonos comprados por usuario/empresa
@ruta_bonos.get("/comprados/{idComprador}", response_model=list)
async def listar_bonos_comprados(idComprador: str):
    bonos = db.bonos.find({"compradoPor": idComprador})
    return [modelo_bono(b) for b in bonos]

# ✅ 5. Obtener bono por código
@ruta_bonos.get("/{codigo}", response_model=dict)
async def obtener_bono(codigo: str):
    bono = db.bonos.find_one({"codigo": codigo})
    if not bono:
        raise HTTPException(status_code=404, detail="Bono no encontrado")
    return modelo_bono(bono)

# ✅ 6. Eliminar bono (administrativo)
@ruta_bonos.delete("/{codigo}", response_model=dict)
async def eliminar_bono(codigo: str):
    result = db.bonos.delete_one({"codigo": codigo})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Bono no encontrado")
    return {"mensaje": "Bono eliminado correctamente"}
