from pydantic import BaseModel, EmailStr
from typing import Optional
from datetime import datetime

class Usuario(BaseModel):
    id: Optional[str] = None
    nombre: str = "Edwin Zarate"
    email: EmailStr = "edwin@example.com"
    telefono: Optional[str] = None
    clave: str = "clavesegura"

