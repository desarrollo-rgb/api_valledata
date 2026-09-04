"""Configuracion comun de las pruebas.

Se ejecuta ANTES de importar la app. Fuerza el modo "falso" para TODAS las pruebas: asi
los tests son deterministas y no dependen del .env de desarrollo ni de infraestructura
real (DataGov, PostgreSQL). Las variables de entorno mandan sobre el archivo .env.
"""

import os

# Modo falso, pase lo que pase en el .env local.
os.environ["USAR_DATAGOV_FALSO"] = "true"
os.environ["USAR_POSTGRES_FALSO"] = "true"
# Token fijo para las pruebas (no dependemos del token real del .env).
os.environ["API_TOKEN"] = "token-de-pruebas"
