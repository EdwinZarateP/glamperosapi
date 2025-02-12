def modelo_usuario(usuario) -> dict:
    return {
        "id": str(usuario["_id"]),
        "nombre": usuario["nombre"],
        "email": usuario["email"],
        "telefono": usuario["telefono"],
        "glampings": usuario.get("glampings", []),
        "fecha_registro": usuario.get("fecha_registro"),  # Nuevo campo
        "foto": usuario.get("foto"),  # Campo opcional
        "banco": usuario.get("banco"),  # Campo opcional
        "numeroCuenta": usuario.get("numeroCuenta"),  # Campo opcional
        "tipoCuenta": usuario.get("tipoCuenta"),  # Campo opcional
        "certificadoBancario": usuario.get("certificadoBancario"),  # Campo opcional
    }

def modelo_usuarios(usuarios)->list:
    return [modelo_usuario(usuario) for usuario in usuarios]