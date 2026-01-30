from fastapi import APIRouter, HTTPException, status, Query
from pymongo import MongoClient, ASCENDING
from pydantic import BaseModel, Field
from datetime import datetime, date, timezone, timedelta
from typing import List, Optional, Literal, Dict, Any
import os

from bson import ObjectId

# ==============================================================================
# 🔗 CONFIGURACIÓN DE BASE DE DATOS
# ==============================================================================
MONGO_URI = os.environ.get("MONGO_URI", "mongodb://localhost:27017")
ConexionMongo = MongoClient(MONGO_URI)
db = ConexionMongo["glamperos"]

coleccion_aseo_tareas = db["aseo_tareas"]
coleccion_aseo_registros = db["aseo_registros"]

# ==============================================================================
# 🧰 UTIL: ObjectId
# ==============================================================================
def _to_objectid(id_str: str) -> ObjectId:
    try:
        return ObjectId(id_str)
    except Exception:
        raise HTTPException(status_code=400, detail="ID inválido (ObjectId)")

def _fecha_iso_a_dt_utc(fecha_str: str) -> datetime:
    """
    Convierte 'YYYY-MM-DD' -> datetime UTC (00:00:00)
    """
    try:
        d = datetime.strptime(fecha_str, "%Y-%m-%d").date()
    except ValueError:
        raise HTTPException(status_code=400, detail="Formato de fecha inválido. Usa YYYY-MM-DD")
    return datetime(d.year, d.month, d.day, 0, 0, 0, tzinfo=timezone.utc)

def _rango_dia_utc(fecha_str: str) -> tuple[datetime, datetime]:
    """
    Devuelve [inicio, fin) del día en UTC para una fecha 'YYYY-MM-DD'
    """
    inicio = _fecha_iso_a_dt_utc(fecha_str)
    fin = inicio + timedelta(days=1)
    return inicio, fin

def _rango_fechas_utc(desde: Optional[str], hasta: Optional[str]) -> Dict[str, Any]:
    """
    Genera un filtro Mongo para un rango de fechas (inclusive en días).
    - desde: 'YYYY-MM-DD' -> >= inicio del día
    - hasta: 'YYYY-MM-DD' -> < inicio del día siguiente (para incluir todo el día)
    """
    filtro: Dict[str, Any] = {}
    if desde:
        filtro["$gte"] = _fecha_iso_a_dt_utc(desde)
    if hasta:
        # incluir todo el día 'hasta'
        hasta_dt = _fecha_iso_a_dt_utc(hasta) + timedelta(days=1)
        filtro["$lt"] = hasta_dt
    return filtro

# ==============================================================================
# 🗂️ ÍNDICES
# ==============================================================================
try:
    # Tareas únicas por pareja + nombre_tarea (evita duplicados)
    coleccion_aseo_tareas.create_index(
        [("pareja_id", ASCENDING), ("nombre_tarea", ASCENDING)],
        unique=True
    )

    # Un registro por pareja + tarea + fecha (un día, una tarea)
    # (fecha es datetime UTC 00:00:00)
    coleccion_aseo_registros.create_index(
        [("pareja_id", ASCENDING), ("tarea_id", ASCENDING), ("fecha", ASCENDING)],
        unique=True
    )

    # Para consultas por rango de fechas
    coleccion_aseo_registros.create_index([("pareja_id", ASCENDING), ("fecha", ASCENDING)])
except Exception:
    pass

# ==============================================================================
# 🚦 ROUTER
# ==============================================================================
ruta_aseo = APIRouter(
    prefix="/aseo",
    tags=["Aseo"],
    responses={status.HTTP_404_NOT_FOUND: {"message": "No encontrado"}},
)

# ==============================================================================
# 🧩 MODELOS
# ==============================================================================
Persona = Literal["HOMBRE", "MUJER"]

class TareaAseoCrear(BaseModel):
    pareja_id: str = Field(..., min_length=1)
    nombre_tarea: str = Field(..., min_length=1, max_length=120)
    activa: bool = True
    creada_en: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class TareaAseoActualizar(BaseModel):
    nombre_tarea: Optional[str] = Field(None, min_length=1, max_length=120)
    activa: Optional[bool] = None

class TareaAseoOut(BaseModel):
    id: str
    pareja_id: str
    nombre_tarea: str
    activa: bool
    creada_en: datetime

class RegistroAseoMarcar(BaseModel):
    pareja_id: str = Field(..., min_length=1)
    tarea_id: str = Field(..., min_length=1)
    # Recibimos string para evitar datetime.date (Mongo no lo serializa)
    fecha: str = Field(..., min_length=10, max_length=10)  # "YYYY-MM-DD"
    realizado_por: Optional[Persona] = None
    completado: bool = True
    actualizado_en: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class RegistroAseoOut(BaseModel):
    id: str
    pareja_id: str
    tarea_id: str
    # devolvemos como string YYYY-MM-DD
    fecha: str
    completado: bool
    realizado_por: Optional[Persona]
    actualizado_en: datetime

def modelo_tarea(doc: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "id": str(doc["_id"]),
        "pareja_id": doc["pareja_id"],
        "nombre_tarea": doc["nombre_tarea"],
        "activa": doc.get("activa", True),
        "creada_en": doc.get("creada_en"),
    }

def _dt_a_fecha_iso(dt: Any) -> str:
    """
    Convierte dt almacenado (datetime UTC) a 'YYYY-MM-DD'
    """
    if isinstance(dt, datetime):
        return dt.date().isoformat()
    # fallback por si existe data vieja
    if isinstance(dt, date):
        return dt.isoformat()
    return str(dt)

def modelo_registro(doc: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "id": str(doc["_id"]),
        "pareja_id": doc["pareja_id"],
        "tarea_id": doc["tarea_id"],
        "fecha": _dt_a_fecha_iso(doc["fecha"]),
        "completado": doc.get("completado", False),
        "realizado_por": doc.get("realizado_por"),
        "actualizado_en": doc.get("actualizado_en"),
    }

# ==============================================================================
# ✅ ENDPOINTS: TAREAS
# ==============================================================================
@ruta_aseo.post("/tareas", response_model=dict)
async def crear_tarea(payload: TareaAseoCrear):
    """
    Crea una tarea (ej: Lavar baños, Preparar desayuno).
    Evita duplicados por pareja_id + nombre_tarea.
    """
    doc = payload.model_dump()
    try:
        resultado = coleccion_aseo_tareas.insert_one(doc)
    except Exception as e:
        existe = coleccion_aseo_tareas.find_one(
            {"pareja_id": payload.pareja_id, "nombre_tarea": payload.nombre_tarea}
        )
        if existe:
            return {"mensaje": "La tarea ya existe", "tarea": modelo_tarea(existe)}
        raise HTTPException(status_code=400, detail=f"No se pudo crear la tarea: {str(e)}")

    doc["_id"] = resultado.inserted_id
    return {"mensaje": "Tarea creada", "tarea": modelo_tarea(doc)}

@ruta_aseo.get("/tareas", response_model=List[TareaAseoOut])
async def listar_tareas(
    pareja_id: str = Query(...),
    solo_activas: bool = Query(False)
):
    filtro: Dict[str, Any] = {"pareja_id": pareja_id}
    if solo_activas:
        filtro["activa"] = True

    tareas = list(coleccion_aseo_tareas.find(filtro).sort("nombre_tarea", 1))
    return [modelo_tarea(t) for t in tareas]

@ruta_aseo.patch("/tareas/{tarea_id}", response_model=dict)
async def actualizar_tarea(tarea_id: str, payload: TareaAseoActualizar):
    cambios = {k: v for k, v in payload.model_dump().items() if v is not None}
    if not cambios:
        raise HTTPException(status_code=400, detail="No enviaste cambios")

    tarea = coleccion_aseo_tareas.find_one({"_id": _to_objectid(tarea_id)})
    if not tarea:
        raise HTTPException(status_code=404, detail="Tarea no encontrada")

    if "nombre_tarea" in cambios:
        existe = coleccion_aseo_tareas.find_one({
            "pareja_id": tarea["pareja_id"],
            "nombre_tarea": cambios["nombre_tarea"]
        })
        if existe and str(existe["_id"]) != tarea_id:
            raise HTTPException(status_code=409, detail="Ya existe otra tarea con ese nombre en la pareja")

    coleccion_aseo_tareas.update_one({"_id": _to_objectid(tarea_id)}, {"$set": cambios})
    actualizado = coleccion_aseo_tareas.find_one({"_id": _to_objectid(tarea_id)})
    return {"mensaje": "Tarea actualizada", "tarea": modelo_tarea(actualizado)}

@ruta_aseo.delete("/tareas/{tarea_id}", response_model=dict)
async def eliminar_tarea(tarea_id: str):
    """
    Elimina una tarea.
    Nota: si prefieres conservar historial, usa desactivar (PATCH) en vez de borrar.
    """
    res = coleccion_aseo_tareas.delete_one({"_id": _to_objectid(tarea_id)})
    if res.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Tarea no encontrada")

    # Limpieza opcional: borrar registros asociados a esa tarea
    coleccion_aseo_registros.delete_many({"tarea_id": tarea_id})
    return {"mensaje": "Tarea eliminada"}

# ==============================================================================
# ✅ ENDPOINTS: REGISTROS (CALENDARIO)
# ==============================================================================
@ruta_aseo.put("/registros", response_model=dict)
async def marcar_tarea_en_fecha(payload: RegistroAseoMarcar):
    """
    Marca una tarea para un día específico y quién la realizó.
    - Si completado=False => desmarca y limpia realizado_por.
    - Guarda 1 registro único por pareja_id + tarea_id + fecha (datetime UTC 00:00:00).
    """
    # Verifica que la tarea exista (y pertenezca a la misma pareja)
    tarea = coleccion_aseo_tareas.find_one({"_id": _to_objectid(payload.tarea_id)})
    if not tarea:
        raise HTTPException(status_code=404, detail="Tarea no encontrada")

    if tarea["pareja_id"] != payload.pareja_id:
        raise HTTPException(status_code=403, detail="La tarea no pertenece a esta pareja")

    fecha_dt = _fecha_iso_a_dt_utc(payload.fecha)

    doc_set = {
        "pareja_id": payload.pareja_id,
        "tarea_id": payload.tarea_id,
        "fecha": fecha_dt,
        "completado": payload.completado,
        "realizado_por": payload.realizado_por if payload.completado else None,
        "actualizado_en": datetime.now(timezone.utc),
    }

    try:
        coleccion_aseo_registros.update_one(
            {"pareja_id": payload.pareja_id, "tarea_id": payload.tarea_id, "fecha": fecha_dt},
            {"$set": doc_set},
            upsert=True
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"No se pudo guardar el registro: {str(e)}")

    guardado = coleccion_aseo_registros.find_one(
        {"pareja_id": payload.pareja_id, "tarea_id": payload.tarea_id, "fecha": fecha_dt}
    )
    return {"mensaje": "Registro guardado", "registro": modelo_registro(guardado)}

@ruta_aseo.get("/registros", response_model=List[RegistroAseoOut])
async def listar_registros(
    pareja_id: str = Query(...),
    fecha: Optional[str] = Query(None, description="YYYY-MM-DD"),
    desde: Optional[str] = Query(None, description="YYYY-MM-DD"),
    hasta: Optional[str] = Query(None, description="YYYY-MM-DD"),
):
    """
    - Si envías 'fecha' trae ese día.
    - Si envías 'desde'/'hasta' trae rango (inclusive por día).
    """
    filtro: Dict[str, Any] = {"pareja_id": pareja_id}

    if fecha:
        inicio, fin = _rango_dia_utc(fecha)
        filtro["fecha"] = {"$gte": inicio, "$lt": fin}
    else:
        if desde or hasta:
            rango = _rango_fechas_utc(desde, hasta)
            if rango:
                filtro["fecha"] = rango

    registros = list(coleccion_aseo_registros.find(filtro).sort("fecha", 1))
    return [modelo_registro(r) for r in registros]

# ==============================================================================
# ✅ ENDPOINT: ESTADÍSTICAS Y PORCENTAJE DE PARTICIPACIÓN
# ==============================================================================
@ruta_aseo.get("/estadisticas", response_model=dict)
async def estadisticas_participacion(
    pareja_id: str = Query(...),
    desde: Optional[str] = Query(None, description="YYYY-MM-DD"),
    hasta: Optional[str] = Query(None, description="YYYY-MM-DD"),
):
    """
    Calcula:
    - Total tareas completadas
    - Cuántas hizo HOMBRE y MUJER
    - Porcentajes de participación
    - Listado de actividades hechas por cada uno (con fecha y nombre de tarea)
    """
    filtro: Dict[str, Any] = {"pareja_id": pareja_id, "completado": True}

    if desde or hasta:
        rango = _rango_fechas_utc(desde, hasta)
        if rango:
            filtro["fecha"] = rango

    registros = list(coleccion_aseo_registros.find(filtro))

    total = len(registros)
    hombre = [r for r in registros if r.get("realizado_por") == "HOMBRE"]
    mujer = [r for r in registros if r.get("realizado_por") == "MUJER"]

    total_hombre = len(hombre)
    total_mujer = len(mujer)

    porc_hombre = round((total_hombre / total) * 100, 2) if total else 0.0
    porc_mujer = round((total_mujer / total) * 100, 2) if total else 0.0

    # Mapa tarea_id -> nombre_tarea para devolver "cuáles"
    tareas = list(coleccion_aseo_tareas.find({"pareja_id": pareja_id}))
    mapa_tareas = {str(t["_id"]): t["nombre_tarea"] for t in tareas}

    def _detalle(items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        salida: List[Dict[str, Any]] = []
        for r in sorted(items, key=lambda x: x.get("fecha") or datetime.min.replace(tzinfo=timezone.utc)):
            salida.append({
                "fecha": _dt_a_fecha_iso(r["fecha"]),
                "tarea_id": r["tarea_id"],
                "tarea": mapa_tareas.get(r["tarea_id"], "Tarea no encontrada"),
            })
        return salida

    return {
        "pareja_id": pareja_id,
        "rango": {"desde": desde, "hasta": hasta},
        "totales": {
            "total_actividades_completadas": total,
            "hombre": total_hombre,
            "mujer": total_mujer,
        },
        "porcentajes": {
            "hombre": porc_hombre,
            "mujer": porc_mujer,
        },
        "detalle": {
            "hombre": _detalle(hombre),
            "mujer": _detalle(mujer),
        }
    }
