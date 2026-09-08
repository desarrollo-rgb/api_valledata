from fastapi.testclient import TestClient

from app.config import get_settings
from app.errors import ErrorDataGovNoDisponible
from app.main import app
from app.services.datagov_client import ClienteDataGovFalso, get_cliente_datagov

cliente = TestClient(app)
CABECERA_VALIDA = {"Authorization": f"Bearer {get_settings().api_token}"}

BASE = "/api/v1/consume/dataset_valledata"

# Los 4 datasets que ValleData consume de DataGov y reexpone, con las columnas que
# entrega el cliente falso.
DATASETS = {
    "gold_cultivos_valle_geo": {"municipio", "nombre_cultivo", "anio", "hectareas_sembradas", "hectareas_cosechadas", "precio"},
    "gold_modelo_rendimiento": {"anio", "municipio", "cultivo", "rendimiento_toneladas_ha", "promedio_oni"},
    "gold_pronostico_produccion": {"id_municipio", "id_cultivo", "fecha_proyectada", "produccion_estimada", "limite_inferior", "limite_superior"},
    "gold_comentarios_sentimiento": {"municipio", "id_dataset", "total_comentarios", "positivos", "negativos", "neutros", "confianza_promedio", "emocion_predominante"},
}


def test_los_4_datasets_reexponen_datos_falsos():
    for tabla, columnas in DATASETS.items():
        respuesta = cliente.get(f"{BASE}/{tabla}?limite=1", headers=CABECERA_VALIDA)
        assert respuesta.status_code == 200, tabla

        cuerpo = respuesta.json()
        assert cuerpo["identificador"] == tabla
        assert len(cuerpo["filas"]) == 1
        # Las columnas llegan tal cual desde DataGov (pass-through).
        assert set(cuerpo["filas"][0]) == columnas, tabla


def test_respeta_el_limite():
    respuesta = cliente.get(f"{BASE}/gold_cultivos_valle_geo?limite=1", headers=CABECERA_VALIDA)
    assert respuesta.status_code == 200
    assert len(respuesta.json()["filas"]) == 1


def test_rechaza_limite_invalido():
    respuesta = cliente.get(f"{BASE}/gold_cultivos_valle_geo?limite=0", headers=CABECERA_VALIDA)
    assert respuesta.status_code == 422


def test_sin_token_da_401():
    respuesta = cliente.get(f"{BASE}/gold_cultivos_valle_geo")
    assert respuesta.status_code == 401


def test_con_token_incorrecto_da_401():
    cabecera_mala = {"Authorization": "Bearer token-inventado-que-no-sirve"}
    respuesta = cliente.get(f"{BASE}/gold_cultivos_valle_geo", headers=cabecera_mala)
    assert respuesta.status_code == 401


def test_si_datagov_falla_devuelve_502():
    # Simulamos que DataGov no responde: el cliente lanza ErrorDataGovNoDisponible.
    # El manejador de errores debe traducirlo a un 502 limpio, no a un 500 feo.
    class ClienteQueFalla:
        def obtener_dataset(self, tabla: str, limite: int) -> dict:
            raise ErrorDataGovNoDisponible("conexion rechazada")

    app.dependency_overrides[get_cliente_datagov] = lambda: ClienteQueFalla()
    try:
        respuesta = cliente.get(f"{BASE}/gold_modelo_rendimiento", headers=CABECERA_VALIDA)
        assert respuesta.status_code == 502
        assert "DataGov" in respuesta.json()["detail"]
    finally:
        app.dependency_overrides.clear()


def test_cliente_falso_entrega_la_misma_forma_que_datagov():
    datos = ClienteDataGovFalso().obtener_dataset("gold_modelo_rendimiento", limite=2)
    assert set(datos) == {"identificador", "filas", "total_devuelto"}
    assert datos["total_devuelto"] == 2
