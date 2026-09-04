"""Endpoints de salud para la infraestructura (Cloud Run / GKE / balanceador).

No los consume DataGov ni un humano: los llama la plataforma para saber si la app esta
viva y si puede recibir trafico. Por eso son PUBLICOS (sin token) y no exponen datos
sensibles.

- /health (liveness): "¿el proceso responde?" -> si falla repetidamente, la plataforma
  REINICIA el contenedor.
- /ready  (readiness): "¿puede trabajar de verdad?" (sus dependencias responden) -> si
  falla, la plataforma DEJA DE ENVIARLE TRAFICO hasta que se recupere, sin reiniciarlo.

Nota de diseno: /ready revisa PostgreSQL (la fuente propia de ValleData), NO DataGov.
Un DataGov caido ya se maneja con un 502 en el Flujo 1; no debe marcar a ValleData como
"no listo", porque el Flujo 2 (comentarios) sigue funcionando.
"""

import logging

from fastapi import APIRouter, HTTPException, status

from app.config import get_settings

logger = logging.getLogger("valledata")

router = APIRouter(tags=["salud"])


@router.get("/health")
async def health() -> dict[str, str]:
    """Liveness: responde mientras el proceso este vivo. No revisa dependencias.

    Es importante que NO consulte PostgreSQL: si lo hiciera, un problema de la base
    provocaria reinicios innecesarios del contenedor.
    """
    return {"status": "alive"}


@router.get("/ready")
async def ready() -> dict[str, str]:
    """Readiness: confirma que la app puede atender (sus dependencias responden)."""
    listo, detalle = _dependencias_listas()
    if not listo:
        # 503: estoy vivo, pero todavia no puedo atender. La plataforma no me enviara
        # trafico hasta que /ready vuelva a responder 200.
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"status": "not ready", "detail": detalle},
        )
    return {"status": "ready", "detail": detalle}


def _dependencias_listas() -> tuple[bool, str]:
    """Comprueba las dependencias necesarias para trabajar.

    - En modo falso no hay dependencias externas: siempre listo.
    - En modo real hace una comprobacion barata: se conecta a UNA base (la primera) y
      ejecuta 'SELECT 1'. No revisamos las 14 en cada sondeo: seria costoso y basta una
      para confirmar que el servidor, el usuario y el tunel responden.
    """
    settings = get_settings()

    if settings.usar_postgres_falso:
        return True, "fake data mode"

    try:
        import psycopg

        with psycopg.connect(
            host=settings.postgres_host,
            port=settings.postgres_port,
            user=settings.postgres_user,
            password=settings.postgres_password,
            dbname=settings.postgres_databases[0],
            connect_timeout=5,
        ) as conexion:
            conexion.read_only = True
            with conexion.cursor() as cursor:
                cursor.execute("SELECT 1")
        return True, "postgres reachable"
    except Exception as e:
        # Al consumidor no le exponemos el detalle, pero SI lo registramos en el log.
        logger.warning("Readiness: PostgreSQL no responde: %s", e)
        return False, "postgres unavailable"
