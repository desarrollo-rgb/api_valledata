"""Cliente hacia la API DataGov (DataGov -> ValleData).

Mismo patron que usamos en DataGov: UNA interfaz, DOS implementaciones.
- ClienteDataGovFalso: datos de ejemplo en memoria (para desarrollar sin DataGov).
- ClienteDataGovHTTP: llamada HTTP real a los endpoints de datos de DataGov.

ValleData consume las vistas de la analitica de comentarios que DataGov expone (detalle y
resumen) y las reexpone. Es un "pass-through": entrega el mismo JSON, sin reformatear. Como
todas se piden igual (misma URL, cambia el nombre de la vista), el cliente tiene UN solo
metodo `obtener_dataset(fuente, tabla, limite, filtros)`. `filtros` son parametros extra que
se reenvian tal cual a DataGov (p. ej. `municipio` y `fecha_hora_publicacion` en el detalle).
"""

from datetime import datetime, timezone
from typing import Protocol

from app.config import get_settings


def _a_utc_naive(dt: datetime) -> datetime:
    if dt.tzinfo is not None:
        return dt.astimezone(timezone.utc).replace(tzinfo=None)
    return dt


def _parsear_fecha(valor: str | None) -> datetime | None:
    if not valor:
        return None
    try:
        return _a_utc_naive(datetime.fromisoformat(valor))
    except (ValueError, TypeError):
        return None


def _fecha_es_mayor_o_igual(fecha_iso: str | None, desde: datetime) -> bool:
    try:
        dt = datetime.fromisoformat(fecha_iso)  # type: ignore[arg-type]
    except (ValueError, TypeError):
        return True
    return _a_utc_naive(dt) >= desde


class ClienteDataGov(Protocol):
    """Contrato: cualquier cliente de DataGov sabe traer un dataset por su nombre.

    `fuente` es el segmento de dataset en la URL de DataGov (hoy `gold_valledata`, el
    dataset donde viven las vistas de comentarios). `filtros` son parametros de query
    opcionales que se reenvian a DataGov.
    """

    def obtener_dataset(
        self, fuente: str, tabla: str, limite: int | None, filtros: dict | None = None
    ) -> dict:
        ...


class ClienteDataGovFalso:
    """Datos de ejemplo, con la forma que responde DataGov de verdad.

    Los ejemplos son representativos (pocas columnas/filas), suficientes para desarrollar
    y probar sin DataGov. En modo real, el pass-through entrega el esquema completo tal
    cual lo devuelve DataGov.
    """

    _EJEMPLOS_POR_TABLA: dict[str, list[dict]] = {
        "valledata_api_comentarios_detalle": [
            {"id_comentario": "ALCALA-144", "fecha_publicacion": "2026-10-10", "fecha_hora_publicacion": "2026-10-10T14:33:32.436942", "id_municipio_dataset": "ALCALA-0A4D4537-31B3-42F5-A9D6-6054C2710739", "municipio": "ALCALA", "dataset_id": "0A4D4537-31B3-42F5-A9D6-6054C2710739", "nombre_dataset": "CONJUNTO DE DATOS 1 OCTUBRE 07", "sentimiento": "NEGATIVO", "emocion": "FRUSTRACION", "texto_es": "EL ENLACE DE DESCARGA DEL RECURSO CSV MARCA UN ERROR 404."},
            {"id_comentario": "ALCALA-143", "fecha_publicacion": "2026-10-10", "fecha_hora_publicacion": "2026-10-10T14:33:07.879329", "id_municipio_dataset": "ALCALA-0A4D4537-31B3-42F5-A9D6-6054C2710739", "municipio": "ALCALA", "dataset_id": "0A4D4537-31B3-42F5-A9D6-6054C2710739", "nombre_dataset": "CONJUNTO DE DATOS 1 OCTUBRE 07", "sentimiento": "NEUTRO", "emocion": "NEUTRAL", "texto_es": "¿CON QUE FRECUENCIA PLANEAN ACTUALIZAR ESTE CONJUNTO DE DATOS?"},
        ],
        "valledata_api_comentarios_resumen_dataset": [
            {"id_municipio_dataset": "ALCALA-CCE62EAC-EEA9-4865-A805-6899CA472B0F", "municipio": "ALCALA", "dataset_id": "CCE62EAC-EEA9-4865-A805-6899CA472B0F", "nombre_dataset": "AGRICULTURA DRP", "total_comentarios": 6, "positivos": 1, "negativos": 3, "neutros": 2, "indice_sentimiento": -0.3333, "sentimiento_predominante": "NEGATIVO", "emocion_predominante": "FRUSTRACION"},
            {"id_municipio_dataset": "ALCALA-44AA281F-E161-447C-9820-4B5B30FEA30A", "municipio": "ALCALA", "dataset_id": "44AA281F-E161-447C-9820-4B5B30FEA30A", "nombre_dataset": "CONJUNTO AGRICULTURA OCTUBRE 2", "total_comentarios": 5, "positivos": 1, "negativos": 4, "neutros": 0, "indice_sentimiento": -0.6, "sentimiento_predominante": "NEGATIVO", "emocion_predominante": "FRUSTRACION"},
        ],
    }

    def obtener_dataset(
        self, fuente: str, tabla: str, limite: int | None, filtros: dict | None = None
    ) -> dict:
        # `fuente` no afecta a los datos de ejemplo (se indexan por tabla); importa en la
        # implementacion real, donde define la URL de DataGov.
        filas = self._EJEMPLOS_POR_TABLA.get(tabla, [])
        filtros = filtros or {}
        municipio = filtros.get("municipio")
        if municipio:
            mu = str(municipio).upper()
            filas = [f for f in filas if str(f.get("municipio", "")).upper() == mu]
        desde = _parsear_fecha(filtros.get("fecha_hora_publicacion"))
        if desde is not None:
            filas = [f for f in filas if _fecha_es_mayor_o_igual(f.get("fecha_hora_publicacion"), desde)]
        filas = filas[:limite]
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

    def obtener_dataset(
        self, fuente: str, tabla: str, limite: int | None, filtros: dict | None = None
    ) -> dict:
        import httpx

        from app.errors import ErrorDataGovNoDisponible, ErrorDataGovRespuesta

        # Reenviamos los filtros tal cual a DataGov; agregamos `limite` solo si viene.
        params: dict = dict(filtros or {})
        if limite is not None:
            params["limite"] = limite
        try:
            respuesta = self._cliente.get(
                f"/api/v1/expose/{fuente}/{tabla}",
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
