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


@lru_cache
def get_settings() -> Settings:
    """Devuelve la configuracion una sola vez (cacheada) para toda la aplicacion."""
    return Settings()
