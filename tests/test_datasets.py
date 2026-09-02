from fastapi.testclient import TestClient

from app.main import app
from app.services.datagov_client import ClienteDataGovFalso

cliente = TestClient(app)


def test_agricultura_reexpone_datos_falsos():
    respuesta = cliente.get("/api/v1/datasets/agricultura?limite=2")
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
    respuesta = cliente.get("/api/v1/datasets/agricultura?limite=1000")
    assert respuesta.status_code == 200
    # El cliente falso tiene 5 filas de ejemplo.
    assert cuerpo_total(respuesta) == 5


def test_agricultura_rechaza_limite_invalido():
    respuesta = cliente.get("/api/v1/datasets/agricultura?limite=0")
    assert respuesta.status_code == 422


def test_cliente_falso_entrega_la_misma_forma_que_datagov():
    datos = ClienteDataGovFalso().obtener_agricultura(limite=3)
    assert set(datos) == {"identificador", "filas", "total_devuelto"}
    assert datos["total_devuelto"] == 3


def cuerpo_total(respuesta) -> int:
    return len(respuesta.json()["filas"])
