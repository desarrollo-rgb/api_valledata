"""Endpoint que expone los comentarios de los portales CKAN (Flujo 2).

Este es el endpoint que la API DataGov consume: ValleData lee los comentarios de las 14
bases PostgreSQL y los entrega aqui, ya parseados y con el municipio identificado.

Incluye `municipios_con_error`: si alguna base no respondio, sus datos no vienen en esta
respuesta, pero los demas municipios si. El consumidor sabe asi que debe reintentar.
"""

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.security import verificar_token
from app.services.comentarios_repo import ComentariosRepo, get_comentarios_repo

# La dependencia va en el router: protege TODOS los endpoints de una vez.
router = APIRouter(
    prefix="/api/v1/expose/bd_ckan",
    tags=["bases de datos ckan"],
    dependencies=[Depends(verificar_token)],
)


@router.get("/comments")
async def listar_comentarios(
    desde: str | None = Query(
        default=None,
        description=(
            "Fecha desde la cual traer comentarios (created >= desde). Acepta ISO 8601: "
            "fecha (2026-07-29) o fecha y hora (2026-07-29T23:58:33Z). "
            "Si se deja vacio, trae todos."
        ),
    ),
    repo: ComentariosRepo = Depends(get_comentarios_repo),
) -> dict:
    """Devuelve los comentarios hechos a los recursos de los conjuntos de datos de los portales ckan de los 14 municipios del proyecto, con la lista de municipios que fallaron. Se puede filtrar por fecha con el parametro `desde`."""
    fecha_desde = _parsear_desde(desde)
    comentarios, municipios_con_error = repo.obtener_comentarios(desde=fecha_desde)
    return {
        "comentarios": comentarios,
        "total": len(comentarios),
        "municipios_con_error": municipios_con_error,
    }


def _parsear_desde(valor: str | None) -> datetime | None:
    """Convierte el parametro `desde` (string) en un datetime UTC sin zona.

    - Vacio o ausente -> None (no se filtra: se traen todos).
    - Acepta fecha (2026-07-29) o fecha y hora ISO 8601 (2026-07-29T23:58:33Z).
    - Si el formato es invalido, responde 422 (error de quien consume, no del servidor).
    """
    if valor is None or valor.strip() == "":
        return None
    try:
        dt = datetime.fromisoformat(valor)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Parametro 'desde' invalido. Usa ISO 8601, por ejemplo 2026-07-29 o 2026-07-29T23:58:33Z.",
        )
    # Normalizamos a UTC sin zona para comparar de forma consistente con `created`.
    if dt.tzinfo is not None:
        dt = dt.astimezone(timezone.utc).replace(tzinfo=None)
    return dt
