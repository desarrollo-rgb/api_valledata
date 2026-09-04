"""Cliente hacia la API DataGov (Flujo 1: DataGov -> ValleData).

Mismo patron que usamos en DataGov: UNA interfaz, DOS implementaciones.
- ClienteDataGovFalso: datos de ejemplo en memoria (para desarrollar sin DataGov).
- ClienteDataGovHTTP: llamada HTTP real al endpoint de datos de DataGov.

ValleData consume el endpoint de DataGov y luego republica esos datos en un endpoint
propio para que CKAN los ingiera. Por ahora es un "pass-through": entrega el mismo JSON,
sin reformatear (el CSV para CKAN vendra despues).
"""

from typing import Protocol

from app.config import get_settings


class ClienteDataGov(Protocol):
    """Contrato: cualquier cliente de DataGov sabe traer los datos de agricultura."""

    def obtener_agricultura(self, limite: int) -> dict:
        ...


class ClienteDataGovFalso:
    """Datos de ejemplo, con la MISMA forma que responde DataGov de verdad."""

    _FILAS_EJEMPLO: list[dict] = [
        {"municipio": "Alcalá", "cultivo": "café", "area_hectareas": 1200, "produccion_toneladas": 980, "anio": 2026},
        {"municipio": "Cerrito", "cultivo": "caña", "area_hectareas": 3400, "produccion_toneladas": 25600, "anio": 2026},
        {"municipio": "Guacarí", "cultivo": "maíz", "area_hectareas": 850, "produccion_toneladas": 4200, "anio": 2026},
        {"municipio": "Pradera", "cultivo": "plátano", "area_hectareas": 640, "produccion_toneladas": 7300, "anio": 2026},
        {"municipio": "Yotoco", "cultivo": "aguacate", "area_hectareas": 410, "produccion_toneladas": 3100, "anio": 2026},
    ]

    def obtener_agricultura(self, limite: int) -> dict:
        filas = self._FILAS_EJEMPLO[:limite]
        return {
            "identificador": "agricultura",
            "filas": filas,
            "total_devuelto": len(filas),
        }


class ClienteDataGovHTTP:
    """Implementacion real: obtiene los datos de agricultura de DataGov por HTTP."""

    def __init__(self) -> None:
        import httpx

        s = get_settings()
        # ValleData es CLIENTE de DataGov: le presenta el token que DataGov exige.
        self._cliente = httpx.Client(
            base_url=s.datagov_api_base_url,
            headers={"Authorization": f"Bearer {s.datagov_api_token}"},
            timeout=s.datagov_timeout_segundos,
        )

    def obtener_agricultura(self, limite: int) -> dict:
        import httpx

        from app.errors import ErrorDataGovNoDisponible, ErrorDataGovRespuesta

        try:
            respuesta = self._cliente.get(
                "/api/v1/dataset_valledata/gold_cultivos_valle_geo",
                params={"limite": limite},
            )
            respuesta.raise_for_status()
        except httpx.HTTPStatusError as e:
            # DataGov contesto, pero con 4xx/5xx (p. ej. token malo, o fallo en BigQuery).
            raise ErrorDataGovRespuesta(f"codigo {e.response.status_code}") from e
        except httpx.RequestError as e:
            # Ni siquiera se pudo contactar a DataGov (caido, timeout, DNS, red).
            raise ErrorDataGovNoDisponible(str(e)) from e

        # Pass-through: devolvemos el JSON tal cual lo entrega DataGov.
        return respuesta.json()


def get_cliente_datagov() -> ClienteDataGov:
    """Decide que cliente usar segun la configuracion.

    Sirve tambien como dependencia de FastAPI: los endpoints la reciben con `Depends`
    y en las pruebas se puede sustituir por una version falsa.
    """
    if get_settings().usar_datagov_falso:
        return ClienteDataGovFalso()
    return ClienteDataGovHTTP()
