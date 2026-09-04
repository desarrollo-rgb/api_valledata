"""Lectura de comentarios desde los portales CKAN (Flujo 2: ValleData -> DataGov).

Mismo patron de siempre: UNA interfaz, DOS implementaciones.
- ComentariosRepoFalso: comentarios de ejemplo en memoria (para desarrollar sin Postgres).
- ComentariosRepoPostgres: se conecta a las 14 bases PostgreSQL (SOLO lectura).

Detalles importantes que exige la realidad de CKAN:
- La columna del texto (`comment`) NO es texto plano: es un JSON multilingue
  {"es": "...", "en": "..."} que hay que parsear (con tolerancia a filas antiguas).
- La columna del dataset se llama "package_Id" (con I mayuscula), por eso en SQL va
  entre comillas dobles.
- Tolerancia a fallos parciales: si un municipio no responde, se registra y los demas
  siguen. Nunca se escribe en las bases.
"""

import json
import logging
from typing import Protocol

from app.config import get_settings
from app.models.schemas import Comentario

logger = logging.getLogger("valledata")


class ComentariosRepo(Protocol):
    """Contrato: entrega los comentarios y la lista de municipios que fallaron."""

    def obtener_comentarios(self) -> tuple[list[Comentario], list[str]]:
        ...


def _parsear_texto(valor: str | None) -> tuple[str | None, str | None]:
    """Convierte el JSON multilingue en (texto_es, texto_en).

    Es tolerante: si una fila antigua trae texto plano (no JSON), lo trata como el
    texto original en espanol.
    """
    if valor is None:
        return None, None
    try:
        datos = json.loads(valor)
        if isinstance(datos, dict):
            return datos.get("es"), datos.get("en")
    except (json.JSONDecodeError, TypeError):
        pass
    return valor, None


class ComentariosRepoFalso:
    """Comentarios de ejemplo, imitando varias bases municipales.

    Nota como el `id` se repite entre municipios (alcala tiene 1 y 2; cerrito tiene 1):
    eso es a proposito, para reflejar que el id NO es unico entre municipios.
    """

    _COMENTARIOS: list[dict] = [
        {"id": 1, "municipio": "alcala", "dataset_id": "d-100", "usuario": "ana", "texto_es": "Buen conjunto de datos", "texto_en": "Good dataset", "fecha": "2026-08-20T10:00:00Z"},
        {"id": 2, "municipio": "alcala", "dataset_id": "d-100", "usuario": "luis", "texto_es": "Faltan los datos de 2025", "texto_en": "2025 data is missing", "fecha": "2026-08-20T11:30:00Z"},
        {"id": 1, "municipio": "cerrito", "dataset_id": "d-200", "usuario": "sara", "texto_es": "Muy util, gracias", "texto_en": "Very useful, thanks", "fecha": "2026-08-21T09:15:00Z"},
        {"id": 1, "municipio": "guacari", "dataset_id": "d-300", "usuario": "pedro", "texto_es": "El archivo no abre", "texto_en": "The file won't open", "fecha": "2026-08-19T14:00:00Z"},
    ]

    def obtener_comentarios(self) -> tuple[list[Comentario], list[str]]:
        comentarios = [Comentario(**c) for c in self._COMENTARIOS]
        return comentarios, []  # ningun municipio con error en modo falso


class ComentariosRepoPostgres:
    """Lee los comentarios reales de las 14 bases PostgreSQL (solo lectura)."""

    _CONSULTA = """
        SELECT id, "package_Id", comment, user_id, created
        FROM public.comments
        ORDER BY id
    """

    def obtener_comentarios(self) -> tuple[list[Comentario], list[str]]:
        import psycopg

        s = get_settings()
        comentarios: list[Comentario] = []
        municipios_con_error: list[str] = []

        for base in s.postgres_databases:
            municipio = base.removeprefix("ckan_")
            try:
                with psycopg.connect(
                    host=s.postgres_host,
                    port=s.postgres_port,
                    user=s.postgres_user,
                    password=s.postgres_password,
                    dbname=base,
                    connect_timeout=10,
                ) as conexion:
                    # Candado de seguridad: aunque el usuario tenga permisos de
                    # escritura, marcamos TODA la sesion como de solo lectura. Si algo
                    # intentara escribir, PostgreSQL mismo lo rechaza. Nunca tocamos
                    # los portales.
                    conexion.read_only = True
                    with conexion.cursor() as cursor:
                        cursor.execute(self._CONSULTA)
                        for id_, package_id, texto, usuario, creado in cursor.fetchall():
                            texto_es, texto_en = _parsear_texto(texto)
                            comentarios.append(
                                Comentario(
                                    id=id_,
                                    municipio=municipio,
                                    dataset_id=package_id,
                                    usuario=usuario,
                                    texto_es=texto_es,
                                    texto_en=texto_en,
                                    # created se guarda en UTC sin zona; marcamos la Z.
                                    fecha=(creado.isoformat() + "Z") if creado else "",
                                )
                            )
            except Exception as e:
                # Tolerancia a fallos parciales: si este municipio falla, lo anotamos
                # y seguimos con los demas. Al consumidor no le exponemos el detalle,
                # pero SI lo registramos en el log para poder diagnosticar (p. ej. saber
                # si fue timeout, credenciales, o que la base no existe).
                logger.warning("No se pudieron leer los comentarios de %s: %s", municipio, e)
                municipios_con_error.append(municipio)

        return comentarios, municipios_con_error


def get_comentarios_repo() -> ComentariosRepo:
    """Decide que repositorio usar segun la configuracion.

    Sirve tambien como dependencia de FastAPI: los endpoints la reciben con `Depends`
    y en las pruebas se puede sustituir por una version falsa.
    """
    if get_settings().usar_postgres_falso:
        return ComentariosRepoFalso()
    return ComentariosRepoPostgres()
