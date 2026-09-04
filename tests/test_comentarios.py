from fastapi.testclient import TestClient

from app.config import get_settings
from app.main import app
from app.services.comentarios_repo import _parsear_texto

cliente = TestClient(app)
CABECERA_VALIDA = {"Authorization": f"Bearer {get_settings().api_token}"}


def test_comentarios_devuelve_datos_falsos():
    respuesta = cliente.get("/api/v1/bd_ckan/comments", headers=CABECERA_VALIDA)
    assert respuesta.status_code == 200

    cuerpo = respuesta.json()
    assert cuerpo["total"] == 4
    assert cuerpo["municipios_con_error"] == []
    assert set(cuerpo["comentarios"][0]) == {
        "id",
        "municipio",
        "dataset_id",
        "usuario",
        "texto_es",
        "texto_en",
        "fecha",
    }


def test_comentarios_sin_token_da_401():
    respuesta = cliente.get("/api/v1/bd_ckan/comments")
    assert respuesta.status_code == 401


def test_ids_se_repiten_entre_municipios():
    # La clave real es municipio + id: el mismo id existe en municipios distintos.
    comentarios = cliente.get("/api/v1/bd_ckan/comments", headers=CABECERA_VALIDA).json()["comentarios"]
    ids_alcala = {c["id"] for c in comentarios if c["municipio"] == "alcala"}
    ids_cerrito = {c["id"] for c in comentarios if c["municipio"] == "cerrito"}
    assert 1 in ids_alcala and 1 in ids_cerrito


def test_parsear_texto_json_multilingue():
    es, en = _parsear_texto('{"es": "Hola", "en": "Hello"}')
    assert es == "Hola"
    assert en == "Hello"


def test_parsear_texto_tolera_texto_plano():
    # Filas antiguas que no son JSON: se tratan como texto original en espanol.
    es, en = _parsear_texto("comentario viejo sin json")
    assert es == "comentario viejo sin json"
    assert en is None
