"""Endpoint que expone los comentarios de los portales CKAN (Flujo 2).

Este es el endpoint que la API DataGov consume: ValleData lee los comentarios de las 14
bases PostgreSQL y los entrega aqui, ya parseados y con el municipio identificado.

Incluye `municipios_con_error`: si alguna base no respondio, sus datos no vienen en esta
respuesta, pero los demas municipios si. El consumidor sabe asi que debe reintentar.
"""

from fastapi import APIRouter, Depends

from app.security import verificar_token
from app.services.comentarios_repo import ComentariosRepo, get_comentarios_repo

# La dependencia va en el router: protege TODOS los endpoints de una vez.
router = APIRouter(
    prefix="/api/v1/bd_ckan",
    tags=["bases de datos ckan"],
    dependencies=[Depends(verificar_token)],
)


@router.get("/comments")
async def listar_comentarios(
    repo: ComentariosRepo = Depends(get_comentarios_repo),
) -> dict:
    """Devuelve los comentarios hechos a los recursos de los conjuntos de datos de los portales ckan de los 14 municipios del proyecto, con la lista de municipios que fallaron."""
    comentarios, municipios_con_error = repo.obtener_comentarios()
    return {
        "comentarios": comentarios,
        "total": len(comentarios),
        "municipios_con_error": municipios_con_error,
    }
