"""Autenticacion de los consumidores de la API (hoy, la API DataGov).

Esquema 'Bearer token': quien llama debe enviar la cabecera
    Authorization: Bearer <token>
y ese token debe coincidir con el configurado en API_TOKEN.

Toda la logica vive detras de una unica dependencia de FastAPI (`verificar_token`).
Eso tiene una ventaja: si el dia de manana cambiamos el mecanismo (por ejemplo a
tokens de identidad de GCP entre servicios), solo tocamos este archivo; los endpoints
no se enteran.
"""

import secrets

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.config import get_settings

# Esquema Bearer. auto_error=False: si falta la cabecera no dejamos que FastAPI lance
# su error por defecto; lo manejamos nosotros para responder siempre 401 y con un
# mensaje generico.
_esquema_bearer = HTTPBearer(auto_error=False)


def verificar_token(
    credenciales: HTTPAuthorizationCredentials | None = Depends(_esquema_bearer),
) -> None:
    """Deja pasar solo si el token presentado coincide con el configurado."""
    token_esperado = get_settings().api_token

    # Falta la cabecera, o no es del tipo "Bearer".
    if credenciales is None or credenciales.scheme.lower() != "bearer":
        raise _no_autorizado()

    # Comparacion en tiempo constante: 'compare_digest' siempre tarda lo mismo, coincida
    # o no. Con un '==' normal, un atacante podria deducir el token caracter por caracter
    # midiendo diferencias de tiempo (timing attack).
    if not secrets.compare_digest(credenciales.credentials, token_esperado):
        raise _no_autorizado()


def _no_autorizado() -> HTTPException:
    # Mensaje generico a proposito: no revelamos si el token falto o si era incorrecto.
    # Dar detalles solo ayudaria a quien intenta adivinar.
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="No autorizado",
        headers={"WWW-Authenticate": "Bearer"},
    )
