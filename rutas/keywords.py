# keywords_router.py
import os
import io
import json
from typing import List, Dict, Optional
from collections import Counter
import pandas as pd
from fastapi import APIRouter, UploadFile, File, Form, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field, conint
from pymongo import MongoClient
from openai import OpenAI

# =========================
# Configuración y clientes
# =========================
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "tu_api_key_aqui")
client = OpenAI(api_key=OPENAI_API_KEY)

MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017")
ConexionMongo = MongoClient(MONGO_URI)
db = ConexionMongo["glamperos"]

# === Router con el nombre y metadatos pedidos ===
ruta_keywords = APIRouter(
    prefix="/keywords",
    tags=["Clasificador keywords"],
    responses={404: {"description": "No encontrado"}},
)

# =========================
# Modelos Pydantic
# =========================
class CategorizeParams(BaseModel):
    max_categories: int = Field(default=20, ge=2, le=50)
    language: str = Field(default="es")
    sheet_name: Optional[str] = None
    column_name: Optional[str] = None

# =========================
# Utilidades
# =========================
POSSIBLE_COLNAMES = ["keyword", "keywords", "palabra", "palabras", "termino", "término", "consulta", "query"]

def _read_dataframe(file: UploadFile, sheet_name: Optional[str]) -> pd.DataFrame:
    filename = (file.filename or "").lower()
    if filename.endswith(".xlsx"):
        data = file.file.read()
        excel = pd.ExcelFile(io.BytesIO(data))
        sheet = sheet_name if sheet_name in excel.sheet_names else excel.sheet_names[0]
        return pd.read_excel(excel, sheet_name=sheet)
    if filename.endswith(".csv"):
        return pd.read_csv(file.file)
    raise HTTPException(status_code=400, detail="Formato no soportado. Usa .xlsx o .csv")

def _find_keyword_column(df: pd.DataFrame, explicit: Optional[str]) -> str:
    if explicit and explicit in df.columns:
        return explicit
    lcmap = {c.lower(): c for c in df.columns}
    for c in POSSIBLE_COLNAMES:
        if c in lcmap:
            return lcmap[c]
    return df.columns[0]

def _clean_list(values: List[str]) -> List[str]:
    out = []
    for v in values:
        if isinstance(v, str):
            s = v.strip()
            if s:
                out.append(s)
        elif pd.notna(v):
            s = str(v).strip()
            if s:
                out.append(s)
    return out

def _force_json(text: str) -> dict:
    text = text.strip()
    if text.startswith("```"):
        text = "\n".join([line for line in text.splitlines() if not line.strip().startswith("```")])
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        start = text.find("{"); end = text.rfind("}")
        if start != -1 and end != -1 and end > start:
            return json.loads(text[start:end+1])
    raise ValueError("No se pudo parsear JSON devuelto por el modelo.")

# =========================
# LLM helpers
# =========================
def propose_categories(all_keywords: List[str], max_categories: int, language: str = "es") -> List[str]:
    sample = all_keywords[:400]
    lang_hint = "en" if language.lower().startswith("en") else "es"

    system = (
        "Eres un taxonomista experto en marketing digital. "
        "Diseña categorías generales no redundantes para agrupar keywords. "
        "Cada categoría: 2–4 palabras, clara y mutuamente exclusiva. "
        "Responde SOLO JSON válido."
    )
    user = (
        f"Genera HASTA {max_categories} categorías (idioma etiquetas: {lang_hint}). "
        f"Keywords (muestra):\n{sample}\n\n"
        'Devuelve: {"categories": ["Cat A", "Cat B", "..."]}'
    )

    resp = client.chat.completions.create(
        model="gpt-4o-mini",
        temperature=0.2,
        messages=[{"role":"system","content":system},{"role":"user","content":user}]
    )
    data = _force_json(resp.choices[0].message.content)
    cats = [c.strip() for c in data.get("categories", []) if isinstance(c, str) and c.strip()]
    if len(cats) > max_categories:
        cats = cats[:max_categories]
    if not cats:
        cats = ["Generales", "Productos", "Guías", "Marcas", "Problemas", "Precios", "Ubicaciones", "Cómo hacer"][:max_categories]
    return cats

def classify_batch(keywords: List[str], categories: List[str], language: str = "es") -> Dict[str, str]:
    lang_hint = "en" if language.lower().startswith("en") else "es"
    system = (
        "Eres un clasificador de consultas SEO. Asigna CADA keyword a EXACTAMENTE UNA categoría de la lista. "
        "Si no encaja, elige la más cercana. Responde SOLO JSON válido."
    )
    user = (
        f"Categorías (elige SOLO UNA por keyword): {categories}\n"
        f"Idioma etiquetas: {lang_hint}\n\n"
        'Devuelve: {"mapping": [{"keyword":"...","category":"<una de las categorías>"}]}\n\n'
        f"Keywords:\n{keywords}"
    )

    resp = client.chat.completions.create(
        model="gpt-4o-mini",
        temperature=0.0,
        messages=[{"role":"system","content":system},{"role":"user","content":user}]
    )
    data = _force_json(resp.choices[0].message.content)
    mapping = {}
    for item in data.get("mapping", []):
        kw = item.get("keyword"); cat = item.get("category")
        if isinstance(kw, str) and isinstance(cat, str) and kw.strip():
            mapping[kw.strip()] = cat.strip()
    return mapping

def classify_all(all_keywords: List[str], categories: List[str], language: str = "es", batch_size: int = 200) -> Dict[str, str]:
    result = {}
    for i in range(0, len(all_keywords), batch_size):
        batch = all_keywords[i:i+batch_size]
        try:
            mapped = classify_batch(batch, categories, language)
        except Exception:
            mapped = {}
        for kw in batch:
            cat = mapped.get(kw)
            result[kw] = cat if cat in categories else None
    if "Otros" not in categories:
        categories = categories + ["Otros"]
    for k, v in result.items():
        if v is None or v not in categories:
            result[k] = "Otros"
    return result

def enforce_max_categories(mapping: Dict[str, str], max_categories: int) -> Dict[str, str]:
    counts = Counter(mapping.values())
    top = {c for c, _ in counts.most_common(max_categories - 1)}  # deja espacio a 'Otros'
    return {k: (v if v in top else "Otros") for k, v in mapping.items()}

def build_excel(original_df: pd.DataFrame, colname: str, mapping: Dict[str, str]) -> bytes:
    df = original_df.copy()
    df["categoria_general"] = df[colname].map(lambda x: mapping.get(str(x).strip(), "Otros") if pd.notna(x) else "")
    resumen = (
        df[df["categoria_general"].notna() & (df["categoria_general"] != "")]
        .groupby("categoria_general").size().reset_index(name="conteo")
        .sort_values("conteo", ascending=False)
    )
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="datos")
        resumen.to_excel(writer, index=False, sheet_name="resumen")
    output.seek(0)
    return output.read()

# =========================
# Endpoints
# =========================
@ruta_keywords.post("/categorize")
async def categorize_keywords(
    file: UploadFile = File(..., description="Archivo .xlsx o .csv con la lista de keywords."),
    max_categories: int = Form(20),
    language: str = Form("es"),
    sheet_name: Optional[str] = Form(None),
    column_name: Optional[str] = Form(None),
):
    if not OPENAI_API_KEY or OPENAI_API_KEY == "tu_api_key_aqui":
        raise HTTPException(status_code=500, detail="OPENAI_API_KEY no configurada en variables de entorno.")

    try:
        df = _read_dataframe(file, sheet_name)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error al leer el archivo: {e}")

    if df.empty:
        raise HTTPException(status_code=400, detail="El archivo está vacío.")

    col = _find_keyword_column(df, column_name)
    keywords = _clean_list(df[col].tolist())
    if not keywords:
        raise HTTPException(status_code=400, detail=f"No se encontraron keywords válidas en la columna '{col}'.")

    try:
        categories = propose_categories(keywords, max_categories=max_categories, language=language)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error generando categorías: {e}")

    if "Otros" not in [c.strip() for c in categories]:
        categories = categories + ["Otros"]

    try:
        mapping = classify_all(keywords, categories, language=language, batch_size=200)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error clasificando keywords: {e}")

    mapping = enforce_max_categories(mapping, max_categories=max_categories)

    try:
        xlsx_bytes = build_excel(df, col, mapping)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error generando Excel de salida: {e}")

    base = os.path.splitext(file.filename or "keywords.xlsx")[0]
    out_name = f"{base}_categorizado.xlsx"
    headers = {"Content-Disposition": f'attachment; filename="{out_name}"'}
    return StreamingResponse(io.BytesIO(xlsx_bytes),
                             media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                             headers=headers)
