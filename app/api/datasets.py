"""Endpoints que reexponen las vistas de la analitica de comentarios de DataGov.

ValleData obtiene cada vista desde DataGov y la reexpone aqui (pass-through: el mismo JSON).
Las vistas viven en el dataset `gold_valledata` de DataGov, por eso su URL usa ese nombre.
El parametro `limite` se reenvia tal cual a DataGov.
"""

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.security import verificar_token
from app.services.datagov_client import ClienteDataGov, get_cliente_datagov

# La dependencia va en el router: protege TODOS los endpoints de una vez.
router = APIRouter(
    prefix="/api/v1/consume/gold_valledata",
    tags=["dataset Valledata"],
    dependencies=[Depends(verificar_token)],
)

# Parametro `limite`: opcional. Vacio = todas las filas; con valor = tope de filas.
_LIMITE = Query(
    default=None,
    ge=1,
    description="Maximo de filas a pedir a DataGov. Vacio = todas.",
)


def _validar_fecha(valor: str | None) -> None:
    """Valida que la fecha sea ISO 8601 (fecha o fecha-hora). 422 si no. Se reenvia a DataGov."""
    if valor is None or valor.strip() == "":
        return
    try:
        datetime.fromisoformat(valor)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Parametro 'fecha_hora_publicacion' invalido. Usa ISO 8601, por ejemplo 2026-10-10 o 2026-10-10T14:33:32.",
        )


@router.get(
    "/valledata_api_comentarios_detalle",
    summary="Obtener el detalle de comentarios analizados",
)
async def obtener_comentarios_detalle(
    limite: int | None = _LIMITE,
    fecha_hora_publicacion: str | None = Query(
        default=None,
        description=(
            "Trae los comentarios publicados DESDE esta fecha/hora en adelante. Acepta ISO "
            "8601: fecha (2026-10-10) o fecha y hora (2026-10-10T14:33:32). Vacio = todos. "
            "Se reenvia a DataGov."
        ),
    ),
    municipio: str | None = Query(
        default=None,
        description="Filtra por municipio. No distingue mayusculas/minusculas. Se reenvia a DataGov.",
    ),
    cliente: ClienteDataGov = Depends(get_cliente_datagov),
) -> dict:
    """Devuelve el detalle de comentarios analizados (un comentario por fila) que ValleData obtuvo de DataGov. Se puede filtrar por `fecha_hora_publicacion` (desde) y por `municipio`."""
    _validar_fecha(fecha_hora_publicacion)
    filtros: dict = {}
    if fecha_hora_publicacion and fecha_hora_publicacion.strip():
        filtros["fecha_hora_publicacion"] = fecha_hora_publicacion
    if municipio and municipio.strip():
        filtros["municipio"] = municipio.strip().upper()
    return cliente.obtener_dataset(
        "gold_valledata", "valledata_api_comentarios_detalle", limite=limite, filtros=filtros
    )


@router.get(
    "/valledata_api_comentarios_resumen_dataset",
    summary="Obtener el resumen de comentarios por dataset",
)
async def obtener_comentarios_resumen_dataset(
    limite: int | None = _LIMITE,
    cliente: ClienteDataGov = Depends(get_cliente_datagov),
) -> dict:
    """Devuelve el resumen de comentarios por dataset (totales y porcentajes) que ValleData obtuvo de DataGov."""
    return cliente.obtener_dataset("gold_valledata", "valledata_api_comentarios_resumen_dataset", limite=limite)
