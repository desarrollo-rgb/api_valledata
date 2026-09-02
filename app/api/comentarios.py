"""Endpoint que expone los comentarios de los portales CKAN (Flujo 2).

Este es el endpoint que la API DataGov consume: ValleData lee los comentarios de las 14
bases PostgreSQL y los entrega aqui, ya parseados y con el municipio identificado.

Incluye `municipios_con_error`: si alguna base no respondio, sus datos no vienen en esta
respuesta, pero los demas municipios si. El consumidor sabe asi que debe reintentar.
"""

from fastapi import APIRouter, Depends

from app.services.comentarios_repo import ComentariosRepo, get_comentarios_repo

router = APIRouter(prefix="/api/v1", tags=["comentarios"])


@router.get("/comentarios")
async def listar_comentarios(
    repo: ComentariosRepo = Depends(get_comentarios_repo),
) -> dict:
    """Devuelve los comentarios de los portales, con la lista de municipios que fallaron."""
    comentarios, municipios_con_error = repo.obtener_comentarios()
    return {
        "comentarios": comentarios,
        "total": len(comentarios),
        "municipios_con_error": municipios_con_error,
    }
