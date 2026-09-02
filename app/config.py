"""Configuracion central de la API ValleData, leida desde variables de entorno.

Regla de oro: nada de valores fijos ni secretos en el codigo. Todo lo que cambia entre
entornos (local, pruebas, produccion) entra por aqui, desde el archivo `.env` o desde las
variables de entorno del contenedor.
"""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # --- Cliente hacia la API DataGov (Flujo 1: consumir datos) ---
    # True  -> datos de ejemplo, sin llamar a DataGov (desarrollo y pruebas sin red).
    # False -> llama a la API DataGov real.
    usar_datagov_falso: bool = True
    datagov_api_base_url: str = "http://localhost:8000"
    datagov_api_token: str = "dev-local-3f9c2a7b1e5d4680-no-usar-en-produccion"
    datagov_timeout_segundos: int = 30

    # --- Lectura de comentarios de los portales CKAN (Flujo 2) ---
    # True  -> comentarios de ejemplo en memoria, sin tocar PostgreSQL (desarrollo).
    # False -> se conecta a las bases PostgreSQL reales.
    usar_postgres_falso: bool = True
    # Credenciales de un usuario de BD de SOLO LECTURA (nunca escribe en los portales).
    # En produccion vienen de Secret Manager; en local, del .env.
    postgres_host: str = "localhost"
    postgres_port: int = 5432
    postgres_user: str = "lector_readonly"
    postgres_password: str = "password-dummy-no-usar-en-produccion"
    # Las 14 bases (una por municipio). El municipio se deriva quitando el prefijo "ckan_".
    postgres_databases: list[str] = [
        "ckan_alcala",
        "ckan_argelia",
        "ckan_bolivar",
        "ckan_cerrito",
        "ckan_el_aguila",
        "ckan_guacari",
        "ckan_la_victoria",
        "ckan_pradera",
        "ckan_riofrio",
        "ckan_san_pedro",
        "ckan_trujillo",
        "ckan_ulloa",
        "ckan_vijes",
        "ckan_yotoco",
    ]


@lru_cache
def get_settings() -> Settings:
    """Devuelve la configuracion una sola vez (cacheada) para toda la aplicacion."""
    return Settings()
