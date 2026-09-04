from fastapi.testclient import TestClient

from app.main import app

cliente = TestClient(app)


def test_health_responde_alive():
    respuesta = cliente.get("/health")
    assert respuesta.status_code == 200
    assert respuesta.json() == {"status": "alive"}


def test_ready_en_modo_falso_esta_listo():
    # En pruebas (conftest fuerza modo falso) no hay dependencias externas: siempre listo.
    respuesta = cliente.get("/ready")
    assert respuesta.status_code == 200
    assert respuesta.json()["status"] == "ready"


def test_salud_es_publica_sin_token():
    # Los endpoints de salud NO llevan token: la plataforma debe poder sondearlos.
    assert cliente.get("/health").status_code == 200
    assert cliente.get("/ready").status_code == 200
