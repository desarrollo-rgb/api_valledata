"""Manejo centralizado de errores de la API ValleData.

Idea: ni los endpoints ni los clientes arman respuestas de error a mano. Aqui definimos
excepciones propias del dominio y unos "manejadores" que las traducen a respuestas HTTP
limpias y consistentes. Asi, ante un fallo, el consumidor recibe un JSON claro con el
codigo correcto, y NUNCA una traza tecnica que revele detalles internos.

Errores que contemplamos hoy (Flujo 1, cuando ValleData llama a DataGov):
- ErrorDataGovNoDisponible: no se pudo contactar a DataGov (caida, timeout, red).
- ErrorDataGovRespuesta: DataGov respondio, pero con un codigo de error (4xx/5xx).

Y una red de seguridad final para cualquier error no previsto.
"""

import logging

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse

logger = logging.getLogger("valledata")


class ErrorDataGovNoDisponible(Exception):
    """No se pudo contactar a la API DataGov (caida, timeout, problema de red)."""


class ErrorDataGovRespuesta(Exception):
    """DataGov respondio, pero con un codigo de error (4xx/5xx)."""


def registrar_manejadores_errores(app: FastAPI) -> None:
    """Conecta los manejadores de error a la aplicacion (se llama desde main.py)."""

    @app.exception_handler(ErrorDataGovNoDisponible)
    async def _datagov_no_disponible(request: Request, exc: ErrorDataGovNoDisponible):
        # 502 Bad Gateway: nosotros estamos bien, pero el servicio del que dependemos no
        # respondio. Registramos el detalle tecnico en el log, no en la respuesta.
        logger.warning("DataGov no disponible: %s", exc)
        return JSONResponse(
            status_code=status.HTTP_502_BAD_GATEWAY,
            content={"detail": "No se pudo contactar a la API DataGov. Intenta mas tarde."},
        )

    @app.exception_handler(ErrorDataGovRespuesta)
    async def _datagov_respuesta(request: Request, exc: ErrorDataGovRespuesta):
        logger.warning("DataGov respondio con error: %s", exc)
        return JSONResponse(
            status_code=status.HTTP_502_BAD_GATEWAY,
            content={"detail": "La API DataGov respondio con un error."},
        )

    @app.exception_handler(Exception)
    async def _error_no_esperado(request: Request, exc: Exception):
        # Red de seguridad: cualquier error no previsto se registra COMPLETO en el log
        # (para poder depurarlo), pero al cliente solo le llega un mensaje generico, sin
        # filtrar detalles internos.
        logger.exception("Error no esperado procesando %s", request.url.path)
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"detail": "Error interno del servidor."},
        )
