from fastapi.testclient import TestClient

from app.config import get_settings
from app.main import app
from app.services.datagov_client import ClienteDataGovFalso, get_cliente_datagov
from app.errors import ErrorDataGovNoDisponible

cliente = TestClient(app)
CABECERA_VALIDA = {"Authorization": f"Bearer {get_settings().api_token}"}


def test_agricultura_reexpone_datos_falsos():
    respuesta = cliente.get("/api/v1/dataset_valledata/gold_cultivos_valle_geo?limite=2", headers=CABECERA_VALIDA)
    assert respuesta.status_code == 200

    cuerpo = respuesta.json()
    assert cuerpo["identificador"] == "agricultura"
    assert len(cuerpo["filas"]) == 2
    # Las columnas llegan tal cual desde DataGov (pass-through).
    assert set(cuerpo["filas"][0]) == {
        "municipio",
        "cultivo",
        "area_hectareas",
        "produccion_toneladas",
        "anio",
    }


def test_agricultura_respeta_el_limite():
    respuesta = cliente.get("/api/v1/dataset_valledata/gold_cultivos_valle_geo?limite=1000", headers=CABECERA_VALIDA)
    assert respuesta.status_code == 200
    # El cliente falso tiene 5 filas de ejemplo.
    assert cuerpo_total(respuesta) == 5


def test_agricultura_rechaza_limite_invalido():
    # Con token valido, pero limite fuera de rango: debe fallar la validacion (422).
    respuesta = cliente.get("/api/v1/dataset_valledata/gold_cultivos_valle_geo?limite=0", headers=CABECERA_VALIDA)
    assert respuesta.status_code == 422


def test_agricultura_sin_token_da_401():
    respuesta = cliente.get("/api/v1/dataset_valledata/gold_cultivos_valle_geo")
    assert respuesta.status_code == 401


def test_agricultura_con_token_incorrecto_da_401():
    cabecera_mala = {"Authorization": "Bearer token-inventado-que-no-sirve"}
    respuesta = cliente.get("/api/v1/dataset_valledata/gold_cultivos_valle_geo", headers=cabecera_mala)
    assert respuesta.status_code == 401


def test_agricultura_si_datagov_falla_devuelve_502():
    # Simulamos que DataGov no responde: el cliente lanza ErrorDataGovNoDisponible.
    # El manejador de errores debe traducirlo a un 502 limpio, no a un 500 feo.
    class ClienteQueFalla:
        def obtener_agricultura(self, limite: int) -> dict:
            raise ErrorDataGovNoDisponible("conexion rechazada")

    app.dependency_overrides[get_cliente_datagov] = lambda: ClienteQueFalla()
    try:
        respuesta = cliente.get("/api/v1/dataset_valledata/gold_cultivos_valle_geo", headers=CABECERA_VALIDA)
        assert respuesta.status_code == 502
        assert "DataGov" in respuesta.json()["detail"]
    finally:
        app.dependency_overrides.clear()


def test_cliente_falso_entrega_la_misma_forma_que_datagov():
    datos = ClienteDataGovFalso().obtener_agricultura(limite=3)
    assert set(datos) == {"identificador", "filas", "total_devuelto"}
    assert datos["total_devuelto"] == 3


def cuerpo_total(respuesta) -> int:
    return len(respuesta.json()["filas"])
