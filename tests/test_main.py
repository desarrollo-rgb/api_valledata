from fastapi.testclient import TestClient

from app.main import app

cliente = TestClient(app)


def test_hola_mundo():
    respuesta = cliente.get("/")
    assert respuesta.status_code == 200
    assert respuesta.json() == {"mensaje": "Hola mundo"}
