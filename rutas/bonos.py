from fastapi import APIRouter, HTTPException, status, UploadFile, File, Query
from pydantic import BaseModel, Field
from pymongo import MongoClient, ASCENDING, errors
from bson import ObjectId
from datetime import datetime, timezone, timedelta
from typing import Optional, List
from google.cloud import storage
import os, random, string, json, base64, uuid
from rutas.Funciones.pdfBonos import generar_pdf_bono_bytes
from rutas.whatsapp_utils import enviar_whatsapp_compra_bonos
from google.oauth2 import service_account  # <-- nuevo import

# ===================== PDF =====================
try:
    from reportlab.lib.pagesizes import letter
    from reportlab.pdfgen import canvas
    REPORTLAB_OK = True
except Exception:
    REPORTLAB_OK = False

# ===================== Email (Resend) =====================
import resend
RESEND_API_KEY = os.getenv("RESEND_API_KEY")
if RESEND_API_KEY:
    resend.api_key = RESEND_API_KEY

MAIL_FROM = "contabilidad@glamperos.com"

# ===================== Google Cloud Storage =====================
BUCKET_NAME = "glamperos-imagenes"
CARPETA_BONOS = "pagosBonos"

def _crear_storage_client():
    """
    Crea el cliente de GCS tomando la variable GOOGLE_CLOUD_CREDENTIALS (base64 del JSON)
    sin escribir archivos a disco.
    Si no existe la variable, intenta Application Default Credentials.
    """
    credenciales_base64 = os.environ.get("GOOGLE_CLOUD_CREDENTIALS")
    if credenciales_base64:
        try:
            info = json.loads(base64.b64decode(credenciales_base64).decode("utf-8"))
            creds = service_account.Credentials.from_service_account_info(info)
            return storage.Client(credentials=creds, project=info.get("project_id"))
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Credenciales GCS inválidas: {e}")
    # Fallback a ADC (gcloud, Workload Identity, etc.)
    try:
        return storage.Client()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"No se pudo inicializar GCS: {e}")

try:
    storage_client = _crear_storage_client()
except Exception:
    storage_client = None  # Permitimos levantar la app; fallará al subir si no hay credenciales


def _get_bucket():
    if storage_client is None:
        raise HTTPException(status_code=500, detail="Google Cloud Storage no inicializado (credenciales faltantes)")
    bucket = storage_client.bucket(BUCKET_NAME)
    return bucket


def subir_a_google_storage(archivo: UploadFile, carpeta: str, nombre: Optional[str] = None) -> str:
    """Sube un UploadFile a GCS y retorna URL pública."""
    try:
        bucket = _get_bucket()
        ext = archivo.filename.split(".")[-1].lower() if archivo.filename and "." in archivo.filename else "dat"
        nombre_archivo = nombre or f"{carpeta}/{uuid.uuid4().hex}.{ext}"
        blob = bucket.blob(nombre_archivo)
        blob.upload_from_file(archivo.file, content_type=archivo.content_type)
        return f"https://storage.googleapis.com/{BUCKET_NAME}/{nombre_archivo}"
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al subir a Google Storage: {str(e)}")


def subir_bytes_a_google_storage(data: bytes, carpeta: str, filename: str, content_type: str = "application/pdf") -> str:
    """Sube bytes en memoria a GCS y retorna URL pública."""
    try:
        bucket = _get_bucket()
        nombre_archivo = f"{carpeta}/{filename}"
        blob = bucket.blob(nombre_archivo)
        blob.upload_from_string(data, content_type=content_type)
        return f"https://storage.googleapis.com/{BUCKET_NAME}/{nombre_archivo}"
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al subir bytes a Google Storage: {str(e)}")

# ===================== Tipos de archivos (PDF o imágenes) =====================
ALLOWED_MIME = {
    "application/pdf",
    "image/jpeg",
    "image/jpg",
    "image/png",
    "image/webp",
    "application/octet-stream",  # algunos navegadores lo envían
}
ALLOWED_EXT = {"pdf", "jpg", "jpeg", "png", "webp"}

MIME_EXT_MAP = {
    "application/pdf": "pdf",
    "image/jpeg": "jpg",
    "image/jpg": "jpg",
    "image/png": "png",
    "image/webp": "webp",
}

def _ext_from_upload(upload: UploadFile) -> str:
    # 1) por filename
    if upload.filename and "." in upload.filename:
        ext = upload.filename.rsplit(".", 1)[-1].lower()
        if ext in ALLOWED_EXT:
            return ext
    # 2) por content-type
    if upload.content_type in MIME_EXT_MAP:
        return MIME_EXT_MAP[upload.content_type]
    return "dat"  # fallback

def _is_allowed_upload(upload: UploadFile) -> bool:
    if upload.content_type in ALLOWED_MIME:
        return True
    # si el content-type viene vacío u 'octet-stream', validamos por extensión
    if upload.filename and "." in upload.filename:
        ext = upload.filename.rsplit(".", 1)[-1].lower()
        return ext in ALLOWED_EXT
    return False

# ===================== Mongo =====================
MONGO_URI = os.environ.get("MONGO_URI", "mongodb://localhost:27017")
conexion = MongoClient(MONGO_URI)
db = conexion["glamperos"]

def ensure_indexes():
    # Único parcial para codigo_unico
    try:
        db.bonos.create_index(
            [("codigo_unico", ASCENDING)],
            name="codigo_unico_1",
            unique=True,
            partialFilterExpression={"codigo_unico": {"$type": "string"}},
        )
    except errors.OperationFailure:
        pass

    # Índices de apoyo (no únicos)
    try:
        db.bonos.create_index([("compra_lote_id", ASCENDING)], name="compra_lote_id_1")
        db.bonos.create_index([("_usuario", ASCENDING)], name="_usuario_1")
        db.bonos.create_index([("estado", ASCENDING)], name="estado_1")
        db.bonos.create_index([("fechaVencimiento", ASCENDING)], name="fechaVencimiento_1")
    except errors.OperationFailure:
        pass

ensure_indexes()

# ===================== FastAPI =====================
ruta_bonos = APIRouter(
    prefix="/bonos",
    tags=["Bonos"],
    responses={status.HTTP_404_NOT_FOUND: {"message": "No encontrado"}},
)

# ===================== Constantes =====================
IVA_PORCENTAJE = 0.19
MONTO_MINIMO_BONO = 150_000  # Cambia a 100_000 si lo necesitas
CODIGO_PREFIJO = "GLAM_"
CODIGO_LONGITUD = 10
VIGENCIA_DIAS = 365  # 1 año

# ===================== Modelos =====================
class BonoCrear(BaseModel):
    valor: int = Field(..., ge=MONTO_MINIMO_BONO, description="Valor base SIN IVA (valor redimible)")

class RedimirBonoRequest(BaseModel):
    codigo_unico: str
    id_usuario: str
    email_usuario_redime: Optional[str] = None  # se fija aquí (no en creación)

# ===================== Utilidades =====================
def generar_codigo_bono() -> str:
    caracteres = string.ascii_uppercase + string.digits
    while True:
        sufijo = ''.join(random.choice(caracteres) for _ in range(CODIGO_LONGITUD))
        codigo = f"{CODIGO_PREFIJO}{sufijo}"
        if db.bonos.count_documents({"codigo_unico": codigo}, limit=1) == 0:
            return codigo

def calcular_iva_y_total(valor_base: int) -> tuple[int, int]:
    iva = int(round(valor_base * IVA_PORCENTAJE))
    total = valor_base + iva
    return iva, total

def enviar_correo(destinatario: str, asunto: str, html: str,
                  adjuntos: Optional[List[dict]] = None):
    if not RESEND_API_KEY:
        raise HTTPException(status_code=500, detail="RESEND_API_KEY no configurada")
    payload = {"from": MAIL_FROM, "to": [destinatario], "subject": asunto, "html": html}
    if adjuntos:
        payload["attachments"] = adjuntos
    try:
        return resend.Emails.send(payload)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Error enviando correo: {str(e)}")

def serialize_bono(doc: dict) -> dict:
    return {
        "id": str(doc["_id"]),
        "codigo_unico": doc["codigo_unico"],
        "valor": doc["valor"],  # base SIN IVA (valor redimible)
        "iva": doc["iva"],
        "total_valor_bono": doc["total_valor_bono"],  # base + IVA (solo referencia de cobro)
        "estado": doc["estado"],  # pendiente_aprobacion | activo | redimido | rechazado
        "fechaCompra": doc.get("fechaCompra"),
        "fechaVencimiento": doc.get("fechaVencimiento"),
        "fechaRedencion": doc.get("fechaRedencion"),
        "_usuario": doc["_usuario"],
        "email_comprador": doc["email_comprador"],
        "cedula_o_nit": doc["cedula_o_nit"],
        "requiere_factura_electronica": doc.get("requiere_factura_electronica", False),
        "datos_facturacion": doc.get("datos_facturacion"),
        "email_usuario_redime": doc.get("email_usuario_redime"),
        # URLs en GCS
        "soporte_pago_url": doc.get("soporte_pago_url"),
        "pdf_bono_url": doc.get("pdf_bono_url"),
        "factura_url": doc.get("factura_url"),
        "activado_por": doc.get("activado_por"),
        "fecha_activacion": doc.get("fecha_activacion"),
        "compra_lote_id": str(doc["compra_lote_id"]) if doc.get("compra_lote_id") else None,
    }

def parse_fecha(fecha_str: Optional[str]) -> datetime:
    if not fecha_str:
        return datetime.now(timezone.utc)
    try:
        dt = datetime.fromisoformat(fecha_str)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except Exception:
        raise HTTPException(status_code=400, detail="fechaCompra inválida. Use ISO8601.")

# ===================== Endpoints =====================
# 1) Comprar (Query params + soporte PDF o imagen en File) | SIN email_usuario_redime
@ruta_bonos.post("/comprar", response_model=dict)
async def comprar_bonos(
    id_usuario: str = Query(..., description="ID del usuario/comprador (string)"),
    email_comprador: str = Query(...),
    cedula_o_nit: str = Query(...),
    fechaCompra: Optional[str] = Query(None, description="ISO8601 (opcional)"),
    datos_bonos_json: str = Query(..., description='JSON lista bonos: [{"valor":200000}, ...]'),

    # Facturación
    requiere_factura_electronica: bool = Query(False, description="¿Requiere factura electrónica?"),

    # Si requiere_factura_electronica=True, debes enviar estos:
    razon_social: Optional[str] = Query(None, description="Razón social (si requiere factura)"),
    nit_facturacion: Optional[str] = Query(None, description="NIT de facturación (si requiere factura)"),
    email_facturacion: Optional[str] = Query(None, description="Email para factura (si requiere factura)"),
    direccion_facturacion: Optional[str] = Query(None, description="Dirección de facturación"),
    telefono_facturacion: Optional[str] = Query(None, description="Teléfono de facturación"),

    # Archivo
    soporte_pago: UploadFile = File(..., description="Comprobante de pago (PDF o imagen JPG/PNG/WEBP)"),
):
    # ---- Validaciones básicas
    if not _is_allowed_upload(soporte_pago):
        raise HTTPException(status_code=400, detail="El soporte debe ser PDF o imagen (JPG/PNG/WEBP)")

    # Parse bonos
    try:
        raw_list = json.loads(datos_bonos_json)
        bonos_obj = [BonoCrear(**b) for b in raw_list]
        if not bonos_obj:
            raise ValueError("La lista de bonos está vacía")
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"datos_bonos_json inválido: {str(e)}")

    # Validar facturación si corresponde
    datos_facturacion = None
    if requiere_factura_electronica:
        faltan = []
        if not razon_social:          faltan.append("razon_social")
        if not nit_facturacion:       faltan.append("nit_facturacion")
        if not email_facturacion:     faltan.append("email_facturacion")
        if not direccion_facturacion: faltan.append("direccion_facturacion")
        if faltan:
            raise HTTPException(status_code=400, detail=f"Faltan datos de facturación: {', '.join(faltan)}")
        datos_facturacion = {
            "razon_social": razon_social,
            "nit": nit_facturacion,
            "email": email_facturacion,
            "direccion": direccion_facturacion,
            "telefono": telefono_facturacion,
        }

    # ---- Subir soporte a GCS (y conservar bytes para adjunto)
    soporte_bytes = await soporte_pago.read()
    if not soporte_bytes:
        raise HTTPException(status_code=400, detail="El archivo de soporte está vacío")

    ext = _ext_from_upload(soporte_pago)
    nombre_soporte = f"soporte_{uuid.uuid4().hex}.{ext}"
    soporte_url = subir_bytes_a_google_storage(
        soporte_bytes,
        carpeta=f"{CARPETA_BONOS}/soportes",
        filename=nombre_soporte,
        content_type=soporte_pago.content_type or "application/octet-stream",
    )

    # ---- Crear documentos de bonos
    fecha_dt = parse_fecha(fechaCompra)
    compra_lote_id = ObjectId()
    creados: List[dict] = []

    total_redimible = 0
    total_con_iva = 0

    for item in bonos_obj:
        valor = int(item.valor)
        if valor < MONTO_MINIMO_BONO:
            raise HTTPException(status_code=400, detail=f"Cada bono debe ser mínimo de ${MONTO_MINIMO_BONO:,}")

        iva, total = calcular_iva_y_total(valor)
        codigo = generar_codigo_bono()
        fecha_vencimiento = fecha_dt + timedelta(days=VIGENCIA_DIAS)

        bono_doc = {
            "codigo_unico": codigo,
            "_usuario": id_usuario,
            "email_comprador": email_comprador,
            "cedula_o_nit": cedula_o_nit,

            "valor": valor,                # SIN IVA (redimible)
            "iva": iva,
            "total_valor_bono": total,     # CON IVA (para cobro)

            "fechaCompra": fecha_dt,
            "fechaVencimiento": fecha_vencimiento,
            "fechaRedencion": None,
            "estado": "pendiente_aprobacion",
            "email_usuario_redime": None,  # se define al redimir

            # Archivos/URLs
            "soporte_pago_url": soporte_url,
            "pdf_bono_url": None,
            "factura_url": None,

            # Auditoría
            "activado_por": None,
            "fecha_activacion": None,
            "compra_lote_id": compra_lote_id,

            # Facturación
            "requiere_factura_electronica": requiere_factura_electronica,
            "datos_facturacion": datos_facturacion,
        }

        inserted = db.bonos.insert_one(bono_doc)
        bono_doc["_id"] = inserted.inserted_id
        creados.append(serialize_bono(bono_doc))

        total_redimible += valor
        total_con_iva += total

    # ---- Correo al CLIENTE: pago recibido y en validación (SIN adjuntos)
    try:
        asunto_cliente = "¡Recibimos tu pago de bonos! (en validación)"
        html_cliente = f"""
            <h2>¡Gracias por tu compra en Glamperos!</h2>
            <p>Recibimos tu pago y ahora está siendo validado por nuestro equipo.</p>
            <ul>
                <li><b>Compra/Lote:</b> {str(compra_lote_id)}</li>
                <li><b>Bonos creados:</b> {len(creados)}</li>
                <li><b>Total redimible (sin IVA):</b> ${total_redimible:,}</li>
                <li><b>Total pagado (con IVA):</b> ${total_con_iva:,}</li>
            </ul>
            <p><i>Una vez confirmemos el pago, te llegará un único correo con tus bonos adjuntos/enlaces.</i></p>
        """
        enviar_correo(destinatario=email_comprador, asunto=asunto_cliente, html=html_cliente)
    except:
        pass

    # ---- Correo a CONTABILIDAD: notificación con comprobante adjunto
    try:
        asunto_conta = f"Nuevo pago de bonos en validación – {email_comprador}"
        html_conta = f"""
            <h3>Nuevo pago recibido (pendiente de validación)</h3>
            <ul>
                <li><b>Cliente:</b> {email_comprador}</li>
                <li><b>Cédula/NIT:</b> {cedula_o_nit}</li>
                <li><b>Compra/Lote:</b> {str(compra_lote_id)}</li>
                <li><b>Bonos:</b> {len(creados)}</li>
                <li><b>Total redimible (sin IVA):</b> ${total_redimible:,}</li>
                <li><b>Total pagado (con IVA):</b> ${total_con_iva:,}</li>
                <li><b>Soporte en GCS:</b> <a href="{soporte_url}">{soporte_url}</a></li>
            </ul>
            <p>Se adjunta el comprobante del cliente.</p>
        """
        adjunto_soporte = [{
            "filename": nombre_soporte,
            "content": base64.b64encode(soporte_bytes).decode("utf-8"),
            "contentType": soporte_pago.content_type or "application/octet-stream",
        }]
        enviar_correo(
            destinatario="contabilidad@glamperos.com",
            asunto=asunto_conta,
            html=html_conta,
            adjuntos=adjunto_soporte
        )
    except:
        pass

    # ---- WhatsApp (manteniendo enviar_whatsapp_compra_bonos)
    try:
        await enviar_whatsapp_compra_bonos(
            numero="573125443396",  # TODO: reemplazar por el teléfono real del cliente si lo tienes
            pdf=soporte_url,
            correo_cliente=compra_lote_id,
            valor_bono=f"Total redimible ${total_redimible:,} | Total pagado con IVA: ${total_con_iva:,}",
            imagenUrl="https://storage.googleapis.com/glamperos-imagenes/Imagenes/bono.png"
        )

        await enviar_whatsapp_compra_bonos(
            numero="573197812921",  # TODO: reemplazar por el teléfono real del cliente si lo tienes
            pdf=soporte_url,
            correo_cliente=compra_lote_id,
            valor_bono=f"Total redimible ${total_redimible:,} | Total pagado con IVA: ${total_con_iva:,}",
            imagenUrl="https://storage.googleapis.com/glamperos-imagenes/Imagenes/bono.png"
        )
    except:
        pass

    # ---- Respuesta API
    return {
        "mensaje": "Tu pago fue recibido y está en validación. "
                   "Una vez aprobado, te enviaremos un único correo con tus bonos adjuntos/enlaces.",
        "estado_compra": "pendiente_aprobacion",
        "compra_lote_id": str(compra_lote_id),
        "bonos_creados": len(creados),
        "totales": {
            "valor_redimible_total_sin_iva": total_redimible,
            "total_pagado_con_iva": total_con_iva
        },
        "bonos": creados
    }

# ------------------------------------------------------------------------------
# 2) Aprobar (admin) individual → ACTIVA y genera PDF del bono (NO envía correo)
@ruta_bonos.post("/{codigo_unico}/aprobar", response_model=dict)
async def aprobar_bono(
    codigo_unico: str,
    id_usuario_admin: str = Query(...),
    observacion: Optional[str] = Query(None),
    factura_pdf: Optional[UploadFile] = File(None, description="Factura/soporte final (PDF o imagen JPG/PNG/WEBP) para el cliente (opcional)")
):
    bono = db.bonos.find_one({"codigo_unico": codigo_unico})
    if not bono:
        raise HTTPException(status_code=404, detail="Bono no encontrado")
    if bono["estado"] != "pendiente_aprobacion":
        raise HTTPException(status_code=400, detail="El bono no está en pendiente_aprobacion")

    # Generar PDF del bono (MUESTRA SOLO VALOR BASE y vigencia) y subir a GCS
    pdf_bytes = generar_pdf_bono_bytes(
        codigo=bono["codigo_unico"],
        valor_base=bono["valor"],
        fecha_compra=bono["fechaCompra"],
        fecha_vencimiento=bono["fechaVencimiento"]
    )
    pdf_url = subir_bytes_a_google_storage(
        pdf_bytes, carpeta=f"{CARPETA_BONOS}/bonos", filename=f"{bono['codigo_unico']}.pdf"
    )

    set_fields = {
        "estado": "activo",
        "activado_por": id_usuario_admin,
        "fecha_activacion": datetime.now(timezone.utc),
        "pdf_bono_url": pdf_url,
        "observacion_aprobacion": observacion
    }

    # Guardar factura del admin (si la adjunta) en GCS pagosBonos/facturas
    if factura_pdf:
        if not _is_allowed_upload(factura_pdf):
            raise HTTPException(status_code=400, detail="La factura debe ser PDF o imagen (JPG/PNG/WEBP)")
        ext_fac = _ext_from_upload(factura_pdf)
        factura_url = subir_a_google_storage(
            factura_pdf, carpeta=f"{CARPETA_BONOS}/facturas", nombre=f"factura_{bono['codigo_unico']}.{ext_fac}"
        )
        set_fields["factura_url"] = factura_url

    db.bonos.update_one({"_id": bono["_id"]}, {"$set": set_fields})
    bono = db.bonos.find_one({"_id": bono["_id"]})

    return {
        "mensaje": "Bono aprobado/activado. No se envió correo porque el envío se hace al aprobar el lote.",
        "bono": serialize_bono(bono)
    }

# ------------------------------------------------------------------------------
# 2b) Aprobar LOTE (admin) → activa todos, adjunta FACTURA del admin en el ÚNICO correo, e incluye links a cada bono
@ruta_bonos.post("/compras/{compra_lote_id}/aprobar", response_model=dict)
async def aprobar_lote(
    compra_lote_id: str,
    id_usuario_admin: str = Query(...),
    observacion: Optional[str] = Query(None),
    factura_pdf: Optional[UploadFile] = File(None, description="Factura/soporte final (PDF o imagen JPG/PNG/WEBP) para el cliente (se adjunta en el correo)")
):
    try:
        lote_oid = ObjectId(compra_lote_id)
    except Exception:
        raise HTTPException(status_code=400, detail="compra_lote_id inválido")

    bonos = list(db.bonos.find({"compra_lote_id": lote_oid, "estado": "pendiente_aprobacion"}))
    if not bonos:
        return {"mensaje": "No hay bonos en pendiente_aprobacion para este lote.", "aprobados": 0}

    # Asumimos mismo comprador para el lote
    email_comprador = bonos[0]["email_comprador"] if bonos else None

    # Subir factura una sola vez (si la envían)
    factura_url_general = None
    factura_adjunto = None
    if factura_pdf:
        if not _is_allowed_upload(factura_pdf):
            raise HTTPException(status_code=400, detail="La factura debe ser PDF o imagen (JPG/PNG/WEBP)")
        ext_fac = _ext_from_upload(factura_pdf)
        # Subir a GCS
        factura_url_general = subir_a_google_storage(
            factura_pdf, carpeta=f"{CARPETA_BONOS}/facturas", nombre=f"factura_lote_{compra_lote_id}.{ext_fac}"
        )
        # También adjuntarla en el correo
        factura_pdf.file.seek(0)
        factura_bytes = factura_pdf.file.read()
        factura_adjunto = {
            "filename": f"factura_lote_{compra_lote_id}.{ext_fac}",
            "content": base64.b64encode(factura_bytes).decode("utf-8"),
            "contentType": factura_pdf.content_type or "application/octet-stream",
        }

    aprobados = 0
    enlaces_bonos = []

    for b in bonos:
        # generar PDF del bono (solo valor base y vigencia) y subir a GCS
        pdf_bytes = generar_pdf_bono_bytes(
            codigo=b["codigo_unico"],
            valor_base=b["valor"],
            fecha_compra=b["fechaCompra"],
            fecha_vencimiento=b["fechaVencimiento"]
        )
        pdf_url = subir_bytes_a_google_storage(
            pdf_bytes, carpeta=f"{CARPETA_BONOS}/bonos", filename=f"{b['codigo_unico']}.pdf"
        )

        set_fields = {
            "estado": "activo",
            "activado_por": id_usuario_admin,
            "fecha_activacion": datetime.now(timezone.utc),
            "pdf_bono_url": pdf_url,
            "observacion_aprobacion": observacion
        }
        if factura_url_general:
            set_fields["factura_url"] = factura_url_general

        db.bonos.update_one({"_id": b["_id"]}, {"$set": set_fields})
        aprobados += 1

        enlaces_bonos.append({
            "codigo_unico": b["codigo_unico"],
            "valor_redimible": b["valor"],
            "vence": b["fechaVencimiento"].date().isoformat(),
            "pdf_bono_url": pdf_url
        })

    # Enviar UN SOLO correo al comprador con:
    # - Factura adjunta (si la subió el admin)
    # - Lista de links a todos los bonos del lote
    if email_comprador:
        lista_html = "".join(
            f"<li><b>{e['codigo_unico']}</b> — Valor redimible: ${e['valor_redimible']:,} — "
            f"Vence: {e['vence']} — <a href='{e['pdf_bono_url']}'>Descargar</a></li>"
            for e in enlaces_bonos
        )
        asunto = f"Tus bonos Glamperos están ACTIVOS (lote {compra_lote_id})"
        html = f"""
        <h2>¡Tu compra fue aprobada!</h2>
        <p>Estos son tus bonos (válidos por 1 año):</p>
        <ul>{lista_html}</ul>
        {"<p>Adjuntamos tu factura en PDF o imagen.</p>" if factura_adjunto else ""}
        <p>Gracias por comprar en <a href="https://glamperos.com">Glamperos.com</a>.</p>
        """

        adjuntos = [factura_adjunto] if factura_adjunto else None
        enviar_correo(destinatario=email_comprador, asunto=asunto, html=html, adjuntos=adjuntos)

    return {"mensaje": f"{aprobados} bono(s) aprobados y activados. Se envió un único correo al comprador.",
            "aprobados": aprobados,
            "bonos": enlaces_bonos,
            "factura_url": factura_url_general}

# ------------------------------------------------------------------------------
# 3) Rechazar (admin) individual → envía correo al comprador
@ruta_bonos.post("/{codigo_unico}/rechazar", response_model=dict)
async def rechazar_bono(
    codigo_unico: str,
    id_usuario_admin: str = Query(...),
    motivo: str = Query(..., description="Motivo del rechazo")
):
    bono = db.bonos.find_one({"codigo_unico": codigo_unico})
    if not bono:
        raise HTTPException(status_code=404, detail="Bono no encontrado")
    if bono["estado"] != "pendiente_aprobacion":
        raise HTTPException(status_code=400, detail="El bono no está en pendiente_aprobacion")

    db.bonos.update_one(
        {"_id": bono["_id"]},
        {"$set": {"estado": "rechazado", "activado_por": id_usuario_admin, "observacion_rechazo": motivo}}
    )

    # correo al comprador
    asunto = f"Tu bono Glamperos fue RECHAZADO: {bono['codigo_unico']}"
    html = f"""
    <h2>Tu bono fue rechazado</h2>
    <p>Código: <b>{bono['codigo_unico']}</b></p>
    <p>Motivo: {motivo}</p>
    <p>Si crees que es un error, responde a este correo con el comprobante correcto.</p>
    """
    enviar_correo(destinatario=bono["email_comprador"], asunto=asunto, html=html)

    return {"mensaje": "Bono rechazado y correo enviado.", "codigo_unico": codigo_unico}

# ------------------------------------------------------------------------------
# 3b) Rechazar LOTE (admin) → por compra_lote_id, envía un único correo
@ruta_bonos.post("/compras/{compra_lote_id}/rechazar", response_model=dict)
async def rechazar_lote(
    compra_lote_id: str,
    id_usuario_admin: str = Query(...),
    motivo: str = Query(..., description="Motivo del rechazo (aplicará a todos)")
):
    try:
        lote_oid = ObjectId(compra_lote_id)
    except Exception:
        raise HTTPException(status_code=400, detail="compra_lote_id inválido")

    bonos = list(db.bonos.find({"compra_lote_id": lote_oid, "estado": "pendiente_aprobacion"}))
    if not bonos:
        return {"mensaje": "No hay bonos en pendiente_aprobacion para este lote.", "rechazados": 0}

    rechazados = 0
    for b in bonos:
        db.bonos.update_one({"_id": b["_id"]}, {"$set": {
            "estado": "rechazado",
            "activado_por": id_usuario_admin,
            "observacion_rechazo": motivo
        }})
        rechazados += 1

    # Enviar un solo correo
    email_comprador = bonos[0]["email_comprador"]
    asunto = f"Tu compra de bonos Glamperos fue RECHAZADA (lote {compra_lote_id})"
    codigos = ", ".join([b["codigo_unico"] for b in bonos])
    html = f"""
    <h2>Tu compra fue rechazada</h2>
    <p>Bonos: {codigos}</p>
    <p>Motivo: {motivo}</p>
    <p>Si crees que es un error, responde a este correo con el comprobante correcto.</p>
    """
    enviar_correo(destinatario=email_comprador, asunto=asunto, html=html)

    return {"mensaje": f"{rechazados} bono(s) rechazados y se envió un único correo al comprador.",
            "rechazados": rechazados}

# 4) Validar
@ruta_bonos.get("/validar/{codigo_unico}", response_model=dict)
async def validar_bono(codigo_unico: str):
    bono = db.bonos.find_one({"codigo_unico": codigo_unico})
    if not bono or bono["estado"] != "activo":
        return {"valido": False}
    # Chequear vigencia
    ahora = datetime.now(timezone.utc)
    if bono.get("fechaVencimiento") and ahora > bono["fechaVencimiento"]:
        return {"valido": False, "motivo": "vencido", "fechaVencimiento": bono["fechaVencimiento"]}
    return {
        "valido": True,
        "valor_redimible": bono["valor"],         # solo base
        "estado": bono["estado"],
        "fechaVencimiento": bono.get("fechaVencimiento"),
    }

# ------------------------------------------------------------------------------
# 5) Redimir (valida que no esté vencido)
@ruta_bonos.post("/redimir", response_model=dict)
async def redimir_bono(payload: RedimirBonoRequest):
    bono = db.bonos.find_one({"codigo_unico": payload.codigo_unico})
    if not bono:
        raise HTTPException(status_code=404, detail="Bono no encontrado")
    if bono["estado"] != "activo":
        raise HTTPException(status_code=400, detail="El bono no está activo o ya fue usado")

    ahora = datetime.now(timezone.utc)
    if bono.get("fechaVencimiento") and ahora > bono["fechaVencimiento"]:
        raise HTTPException(status_code=400, detail="El bono está vencido y no puede ser redimido")

    update = {
        "estado": "redimido",
        "fechaRedencion": ahora,
        "_usuario_redime": payload.id_usuario,
    }
    if payload.email_usuario_redime:
        update["email_usuario_redime"] = payload.email_usuario_redime

    db.bonos.update_one({"_id": bono["_id"]}, {"$set": update})
    bono = db.bonos.find_one({"_id": bono["_id"]})
    return {"mensaje": "Bono redimido exitosamente", "bono": serialize_bono(bono)}

# ------------------------------------------------------------------------------
# 6) Listar por comprador
@ruta_bonos.get("/comprados/{id_usuario}", response_model=List[dict])
async def listar_bonos_comprados(id_usuario: str):
    bonos = db.bonos.find({"_usuario": id_usuario}).sort("fechaCompra", ASCENDING)
    return [serialize_bono(b) for b in bonos]

# 6b) Listar por lote
@ruta_bonos.get("/compras/{compra_lote_id}", response_model=List[dict])
async def listar_bonos_por_lote(compra_lote_id: str):
    try:
        lote_oid = ObjectId(compra_lote_id)
    except Exception:
        raise HTTPException(status_code=400, detail="compra_lote_id inválido")
    bonos = db.bonos.find({"compra_lote_id": lote_oid}).sort("fechaCompra", ASCENDING)
    return [serialize_bono(b) for b in bonos]

# ------------------------------------------------------------------------------
# 7) Obtener por código
@ruta_bonos.get("/{codigo_unico}", response_model=dict)
async def obtener_bono(codigo_unico: str):
    bono = db.bonos.find_one({"codigo_unico": codigo_unico})
    if not bono:
        raise HTTPException(status_code=404, detail="Bono no encontrado")
    return serialize_bono(bono)

# ------------------------------------------------------------------------------
# 8) URLs de archivos (opcional)
@ruta_bonos.get("/{codigo_unico}/soporte", response_model=dict)
async def obtener_soporte_url(codigo_unico: str):
    bono = db.bonos.find_one({"codigo_unico": codigo_unico})
    if not bono or not bono.get("soporte_pago_url"):
        raise HTTPException(status_code=404, detail="Soporte no encontrado")
    return {"url": bono["soporte_pago_url"]}

@ruta_bonos.get("/{codigo_unico}/pdf", response_model=dict)
async def obtener_pdf_bono_url(codigo_unico: str):
    bono = db.bonos.find_one({"codigo_unico": codigo_unico})
    if not bono or not bono.get("pdf_bono_url"):
        raise HTTPException(status_code=404, detail="PDF del bono no disponible")
    return {"url": bono["pdf_bono_url"]}

# ------------------------------------------------------------------------------
# 9) Factura
@ruta_bonos.get("/{codigo_unico}/factura", response_model=dict)
async def obtener_factura_url(codigo_unico: str):
    bono = db.bonos.find_one({"codigo_unico": codigo_unico})
    if not bono or not bono.get("factura_url"):
        raise HTTPException(status_code=404, detail="Factura no disponible")
    return {"url": bono["factura_url"]}

# ------------------------------------------------------------------------------
# 10) Reenviar lote de bonos (opcional)
@ruta_bonos.post("/compras/{compra_lote_id}/reenviar", response_model=dict)
async def reenviar_bonos_lote(
    compra_lote_id: str,
    destinatario: Optional[str] = Query(None, description="Email al que se reenviará (default: comprador original)"),
    adjuntar_pdfs: bool = Query(False, description="Adjuntar PDFs en el correo (recomendado solo si son pocos)"),
    recrear_si_falta_pdf: bool = Query(True, description="Si falta el PDF de un bono, regenerarlo y subirlo"),
    incluir_factura: bool = Query(True, description="Adjuntar la factura del lote si existe")
):
    errores: List[str] = []

    # 1) Validar lote y obtener bonos
    try:
        lote_oid = ObjectId(compra_lote_id)
    except Exception:
        raise HTTPException(status_code=400, detail="compra_lote_id inválido")

    bonos = list(db.bonos.find({"compra_lote_id": lote_oid}))
    if not bonos:
        raise HTTPException(status_code=404, detail="No hay bonos para ese lote")

    email_destino = destinatario or bonos[0].get("email_comprador")
    if not email_destino:
        raise HTTPException(status_code=400, detail="No hay email del comprador y no se recibió 'destinatario'")

    # Helper para extraer el blob name desde URL pública
    def _blob_name_from_url(url: str) -> Optional[str]:
        prefix = f"https://storage.googleapis.com/{BUCKET_NAME}/"
        if not url or not url.startswith(prefix):
            return None
        return url[len(prefix):]

    enlaces_bonos: List[dict] = []
    adjuntos_email: List[dict] = []
    regenerados = 0

    # 2) Ubicar factura del lote (si existe)
    factura_url_general = None
    for b in bonos:
        if b.get("factura_url"):
            factura_url_general = b["factura_url"]
            break

    # 3) Adjuntar factura si procede (con extensión real)
    if incluir_factura and factura_url_general:
        try:
            blob_name = _blob_name_from_url(factura_url_general)
            if blob_name:
                bucket = _get_bucket()
                blob = bucket.blob(blob_name)
                factura_bytes = blob.download_as_bytes()
                ext_fac = "dat"
                if "." in blob_name:
                    ext_fac = blob_name.rsplit(".", 1)[-1].lower()
                adjuntos_email.append({
                    "filename": f"factura_lote_{compra_lote_id}.{ext_fac}",
                    "content": base64.b64encode(factura_bytes).decode("utf-8")
                })
        except Exception as e:
            errores.append(f"No se pudo adjuntar la factura: {e}")

    # 4) Preparar los bonos: regenerar PDF si falta (opcional) y armar lista/adjuntos
    for b in bonos:
        if b.get("estado") != "activo":
            enlaces_bonos.append({
                "codigo_unico": b["codigo_unico"],
                "estado": b["estado"],
                "nota": "Bono no activo (no se adjunta PDF)"
            })
            continue

        pdf_url = b.get("pdf_bono_url")

        # Regenerar PDF si falta
        if not pdf_url and recrear_si_falta_pdf:
            try:
                pdf_bytes = generar_pdf_bono_bytes(
                    codigo=b["codigo_unico"],
                    valor_base=b["valor"],
                    fecha_compra=b["fechaCompra"],
                    fecha_vencimiento=b["fechaVencimiento"]
                )
                pdf_url = subir_bytes_a_google_storage(
                    pdf_bytes,
                    carpeta=f"{CARPETA_BONOS}/bonos",
                    filename=f"{b['codigo_unico']}.pdf"
                )
                db.bonos.update_one({"_id": b["_id"]}, {"$set": {"pdf_bono_url": pdf_url}})
                regenerados += 1
            except Exception as e:
                errores.append(f"No fue posible regenerar PDF de {b['codigo_unico']}: {e}")
                enlaces_bonos.append({
                    "codigo_unico": b["codigo_unico"],
                    "estado": b["estado"],
                    "error": "No se pudo generar el PDF"
                })
                continue

        info = {
            "codigo_unico": b["codigo_unico"],
            "valor_redimible": b["valor"],
            "vence": b["fechaVencimiento"].date().isoformat() if b.get("fechaVencimiento") else None,
            "pdf_bono_url": pdf_url
        }
        enlaces_bonos.append(info)

        # Adjuntar cada PDF (si se pide)
        if adjuntar_pdfs and pdf_url:
            try:
                blob_name = _blob_name_from_url(pdf_url)
                if blob_name:
                    bucket = _get_bucket()
                    blob = bucket.blob(blob_name)
                    bono_bytes = blob.download_as_bytes()
                    adjuntos_email.append({
                        "filename": f"{b['codigo_unico']}.pdf",
                        "content": base64.b64encode(bono_bytes).decode("utf-8")
                    })
            except Exception as e:
                errores.append(f"No se pudo adjuntar PDF de {b['codigo_unico']}: {e}")

    # 5) Construir correo
    def _li_bono(e: dict) -> str:
        partes = [f"<li><b>{e.get('codigo_unico','')}</b>"]
        if e.get('valor_redimible') is not None:
            partes.append(" — Valor redimible: $" + format(e['valor_redimible'], ','))
        if e.get('vence'):
            partes.append(" — Vence: " + e['vence'])
        if e.get('pdf_bono_url'):
            partes.append(f' — <a href="{e["pdf_bono_url"]}">Descargar</a>')
        if e.get('estado') and e['estado'] != 'activo':
            partes.append(" — (NO ACTIVO)")
        if e.get('error'):
            partes.append(" — " + e['error'])
        partes.append("</li>")
        return "".join(partes)

    lista_html = "".join(_li_bono(e) for e in enlaces_bonos)

    html = f"""
    <h2>Reenvío de bonos Glamperos (lote {compra_lote_id})</h2>
    <p>Te compartimos nuevamente tus bonos:</p>
    <ul>{lista_html}</ul>
    {"<p>Adjuntamos tu factura.</p>" if incluir_factura and factura_url_general else ""}
    {f'<p>También puedes ver tu factura aquí: <a href="{factura_url_general}">{factura_url_general}</a></p>' if factura_url_general else ""}
    <p>Gracias por comprar en <a href="https://glamperos.com">Glamperos.com</a>.</p>
    """

    asunto = f"Reenvío de tus bonos Glamperos (lote {compra_lote_id})"

    # 6) Enviar el correo (protegido)
    try:
        enviar_correo(
            destinatario=email_destino,
            asunto=asunto,
            html=html,
            adjuntos=(adjuntos_email if adjuntos_email else None)
        )
    except Exception as e:
        # ¡IMPORTANTE! Aunque falle el envío, devolvemos un dict para no gatillar ResponseValidationError
        errores.append(f"No se pudo enviar el correo: {e}")

    # 7) Respuesta SIEMPRE en dict
    return {
        "mensaje": "Proceso de reenvío completado.",
        "destinatario": email_destino,
        "bonos_total": len(bonos),
        "bonos_con_link": len([e for e in enlaces_bonos if e.get('pdf_bono_url')]),
        "regenerados": regenerados,
        "adjuntos_incluidos": len(adjuntos_email),
        "factura_url": factura_url_general,
        "errores": errores
     }
 