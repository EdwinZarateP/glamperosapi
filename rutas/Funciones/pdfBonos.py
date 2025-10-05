from datetime import datetime, timezone
from io import BytesIO
from reportlab.lib.pagesizes import letter
from reportlab.lib.units import inch
from reportlab.lib import colors
from reportlab.pdfgen import canvas
from reportlab.lib.utils import ImageReader

def generar_pdf_bono_bytes(
    codigo: str,
    valor_base: int,
    fecha_compra: datetime,
    fecha_vencimiento: datetime,
) -> bytes:
    """
    Genera un PDF estético del bono de regalo de Glamperos.
    - Incluye logo, valor redimible, código y fechas.
    - Estilo de tarjeta de regalo con marco, fondo suave y condiciones.
    - Añade instrucciones de uso para redimir el bono.
    """

    buffer = BytesIO()
    c = canvas.Canvas(buffer, pagesize=letter)
    width, height = letter

    # === Fondo suave ===
    c.setFillColorRGB(0.96, 0.93, 0.88)  # beige claro
    c.rect(0, 0, width, height, fill=1, stroke=0)

    # === Marco decorativo ===
    c.setStrokeColor(colors.HexColor("#8B5E3C"))  # marrón elegante
    c.setLineWidth(6)
    margin = 20
    c.rect(margin, margin, width - 2*margin, height - 2*margin, fill=0)

    # === Logo Glamperos ===
    try:
        logo_url = "https://storage.googleapis.com/glamperos-imagenes/Imagenes/oso.webp"
        logo = ImageReader(logo_url)
        c.drawImage(logo, width/2 - 60, height - 140, width=100, height=100, mask="auto")
    except:
        pass

    # === Título ===
    c.setFont("Helvetica-Bold", 28)
    c.setFillColor(colors.HexColor("#4B2E2E"))
    c.drawCentredString(width/2, height - 170, "🎁 Bono de Regalo 🎁")

    # === Subtítulo Glamperos ===
    c.setFont("Helvetica-Oblique", 14)
    c.setFillColor(colors.HexColor("#6B4226"))
    c.drawCentredString(width/2, height - 190, "Vive experiencias únicas con Glamperos")

    # === Información principal del bono ===
    c.setFont("Helvetica-Bold", 20)
    c.setFillColor(colors.black)
    c.drawCentredString(width/2, height - 250, f"Valor redimible: ${valor_base:,}")

    c.setFont("Helvetica", 14)
    c.drawCentredString(width/2, height - 280, f"Código único: {codigo}")
    c.drawCentredString(width/2, height - 300, f"Fecha de compra: {fecha_compra.strftime('%Y-%m-%d')}")
    c.drawCentredString(width/2, height - 320, f"Válido hasta: {fecha_vencimiento.strftime('%Y-%m-%d')}")

    # === Línea divisoria ===
    c.setStrokeColor(colors.HexColor("#A9745B"))
    c.setLineWidth(1)
    c.line(80, height - 340, width - 80, height - 340)

    # === Condiciones ===
    condiciones = [
        "• Válido para redimir reservas en Glamperos.com",
        "• Vigencia de 1 año a partir de la fecha de compra",
        "• Uso único, no acumulable",
        "• No canjeable por dinero en efectivo",
    ]
    c.setFont("Helvetica", 10)
    y = height - 370
    for cond in condiciones:
        c.drawCentredString(width/2, y, cond)
        y -= 15

    # === Instrucciones de uso ===
    instrucciones = [
        "👉 Ingresa a glamperos.com",
        "👉 Selecciona el glamping de tu preferencia",
        "👉 Confirma la disponibilidad escribiendo al WhatsApp 321 8695196",
        "👉 Allí podrás redimir tu bono y vivir la experiencia ✨"
    ]
    c.setFont("Helvetica-Bold", 11)
    y -= 10
    c.setFillColor(colors.HexColor("#4B2E2E"))
    c.drawCentredString(width/2, y, "Instrucciones de Uso")
    c.setFont("Helvetica", 10)
    c.setFillColor(colors.black)
    y -= 20
    for instr in instrucciones:
        c.drawCentredString(width/2, y, instr)
        y -= 15

    # === Mensaje final ===
    c.setFont("Helvetica-BoldOblique", 12)
    c.setFillColor(colors.HexColor("#6B4226"))
    c.drawCentredString(width/2, 60, "¡Gracias por elegir Glamperos! 🌿✨")

    # Finalizar PDF
    c.showPage()
    c.save()
    buffer.seek(0)
    return buffer.read()
