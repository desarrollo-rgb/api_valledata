"""Cliente hacia la API DataGov (Flujo 1: DataGov -> ValleData).

Mismo patron que usamos en DataGov: UNA interfaz, DOS implementaciones.
- ClienteDataGovFalso: datos de ejemplo en memoria (para desarrollar sin DataGov).
- ClienteDataGovHTTP: llamada HTTP real a los endpoints de datos de DataGov.

ValleData consume los datasets que DataGov expone (los 4 gold) y los republica en sus
propios endpoints para que CKAN los ingiera. Es un "pass-through": entrega el mismo JSON,
sin reformatear. Como todos los datasets se piden igual (misma URL, cambia el nombre de la
tabla), el cliente tiene UN solo metodo `obtener_dataset(tabla, limite)`.
"""

from typing import Protocol

from app.config import get_settings


class ClienteDataGov(Protocol):
    """Contrato: cualquier cliente de DataGov sabe traer un dataset por su nombre."""

    def obtener_dataset(self, tabla: str, limite: int | None) -> dict:
        ...


class ClienteDataGovFalso:
    """Datos de ejemplo, con la forma que responde DataGov de verdad.

    Los ejemplos son representativos (pocas columnas/filas), suficientes para desarrollar
    y probar sin DataGov. En modo real, el pass-through entrega el esquema completo tal
    cual lo devuelve DataGov.
    """

    _EJEMPLOS_POR_TABLA: dict[str, list[dict]] = {
        "gold_cultivos_valle_geo": [
            {"municipio": "alcala", "nombre_cultivo": "cafe", "anio": 2000, "hectareas_sembradas": 2183.4, "hectareas_cosechadas": 1883.51, "precio": None},
            {"municipio": "alcala", "nombre_cultivo": "platano", "anio": 2000, "hectareas_sembradas": 353.0, "hectareas_cosechadas": 245.0, "precio": None},
        ],
        "gold_modelo_rendimiento": [
            {"anio": 2000, "municipio": "bolivar", "cultivo": "papaya", "rendimiento_toneladas_ha": 16.0, "promedio_oni": -0.825},
            {"anio": 2001, "municipio": "cerrito", "cultivo": "caña", "rendimiento_toneladas_ha": 82.5, "promedio_oni": 0.4},
        ],
        "gold_pronostico_produccion": [
            {"id_municipio": 76001, "id_cultivo": 10214, "fecha_proyectada": "2020-01-01T00:00:00Z", "produccion_estimada": 12.33, "limite_inferior": 4.82, "limite_superior": 19.84},
            {"id_municipio": 76109, "id_cultivo": 10322, "fecha_proyectada": "2020-01-01T00:00:00Z", "produccion_estimada": 8.75, "limite_inferior": 2.1, "limite_superior": 15.4},
        ],
        "gold_comentarios_sentimiento": [
            {"municipio": "alcala", "id_dataset": "c98cfd48-9281-1c92-984f-e323b3292925", "total_comentarios": 1, "positivos": 0, "negativos": 1, "neutros": 0, "confianza_promedio": 0.9141, "emocion_predominante": "NEG"},
            {"municipio": "cerrito", "id_dataset": "d753b231-dc4e-4ab4-a025-3e7000000000", "total_comentarios": 5, "positivos": 3, "negativos": 1, "neutros": 1, "confianza_promedio": 0.8123, "emocion_predominante": "POS"},
        ],
    }

    def obtener_dataset(self, tabla: str, limite: int | None) -> dict:
        filas = self._EJEMPLOS_POR_TABLA.get(tabla, [])[:limite]
        return {
            "identificador": tabla,
            "filas": filas,
            "total_devuelto": len(filas),
        }


class ClienteDataGovHTTP:
    """Implementacion real: obtiene los datasets de DataGov por HTTP."""

    def __init__(self) -> None:
        import httpx

        s = get_settings()
        # ValleData es CLIENTE de DataGov: le presenta el token que DataGov exige.
        self._cliente = httpx.Client(
            base_url=s.datagov_api_base_url,
            headers={"Authorization": f"Bearer {s.datagov_api_token}"},
            timeout=s.datagov_timeout_segundos,
        )

    def obtener_dataset(self, tabla: str, limite: int | None) -> dict:
        import httpx

        from app.errors import ErrorDataGovNoDisponible, ErrorDataGovRespuesta

        # Si no hay limite, no enviamos el parametro: DataGov devuelve todas las filas.
        params = {} if limite is None else {"limite": limite}
        try:
            respuesta = self._cliente.get(
                f"/api/v1/expose/dataset_valledata/{tabla}",
                params=params,
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
