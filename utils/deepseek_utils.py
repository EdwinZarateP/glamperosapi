import os
import json
import requests

# Asegúrate de exportar: export DEEPSEEK_API_KEY="tu_key"
DEEPSEEK_API_KEY = os.environ.get("DEEPSEEK_API_KEY")
if not DEEPSEEK_API_KEY:
    raise RuntimeError("🚫 No se encontró la variable DEEPSEEK_API_KEY")

BASE_URL = "https://api.deepseek.com/v1/chat/completions"


def extraer_intencion(pregunta: str) -> dict:
    """
    Recibe una pregunta libre y devuelve:
    {
      "ubicacion": "...",
      "amenidades": ["..."]
    }
    """
    system = (
        "Eres un parser estricto. Responde SOLO un JSON válido "
        "con las claves exactas: 'ubicacion' (string) y 'amenidades' (lista de strings). "
        "No incluyas texto antes o después. "
        "Ejemplo válido: {\"ubicacion\": \"Bogotá\", \"amenidades\": [\"Jacuzzi\"]}."
    )

    payload = {
        "model": "deepseek-chat",
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": pregunta}
        ]
    }

    headers = {
        "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
        "Content-Type": "application/json"
    }

    response = requests.post(BASE_URL, headers=headers, json=payload)
    response.raise_for_status()
    content = response.json()["choices"][0]["message"]["content"]

    # Intenta forzar que el contenido sea JSON puro
    try:
        # Recorta si devuelve texto extra antes/después
        start = content.find("{")
        end = content.rfind("}") + 1
        cleaned = content[start:end]
        return json.loads(cleaned)
    except Exception:
        print("\n⚠️ Respuesta cruda DeepSeek:", content)
        raise RuntimeError("DeepSeek no devolvió un JSON limpio.")


def generar_respuesta(pregunta: str, lista_glampings: str) -> str:
    """
    Genera un texto natural con los glampings reales.
    """
    system = (
        f"Eres un asistente turístico. El usuario preguntó: '{pregunta}'.\n"
        f"Estos son los glampings reales:\n{lista_glampings}\n"
        "Redacta una respuesta clara y amigable SIN inventar datos adicionales."
    )

    payload = {
        "model": "deepseek-chat",
        "messages": [
            {"role": "system", "content": system}
        ]
    }

    headers = {
        "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
        "Content-Type": "application/json"
    }

    response = requests.post(BASE_URL, headers=headers, json=payload)
    response.raise_for_status()
    return response.json()["choices"][0]["message"]["content"]
