from fastapi.testclient import TestClient

from app.config import get_settings
from app.main import app
from app.services.comentarios_repo import _parsear_texto

cliente = TestClient(app)
CABECERA_VALIDA = {"Authorization": f"Bearer {get_settings().api_token}"}


def test_comentarios_devuelve_datos_falsos():
    respuesta = cliente.get("/api/v1/expose/bd_ckan/comments", headers=CABECERA_VALIDA)
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
    respuesta = cliente.get("/api/v1/expose/bd_ckan/comments")
    assert respuesta.status_code == 401


def test_comentarios_filtra_por_fecha_solo_dia():
    # Datos falsos: guacari es 2026-08-19; los demas son 2026-08-20 o 2026-08-21.
    # Con desde=2026-08-20 deben quedar 3 (se excluye guacari).
    respuesta = cliente.get("/api/v1/expose/bd_ckan/comments?desde=2026-08-20", headers=CABECERA_VALIDA)
    assert respuesta.status_code == 200
    cuerpo = respuesta.json()
    assert cuerpo["total"] == 3
    assert all(c["municipio"] != "guacari" for c in cuerpo["comentarios"])


def test_comentarios_filtra_por_fecha_y_hora():
    # alcala id 1 es 10:00 y id 2 es 11:30 (ambos 2026-08-20). Con desde 11:00 se excluye
    # el de las 10:00, quedan: alcala id 2 (11:30) y cerrito (2026-08-21) = 2.
    respuesta = cliente.get(
        "/api/v1/expose/bd_ckan/comments?desde=2026-08-20T11:00:00Z", headers=CABECERA_VALIDA
    )
    assert respuesta.status_code == 200
    assert respuesta.json()["total"] == 2


def test_comentarios_desde_vacio_trae_todos():
    respuesta = cliente.get("/api/v1/expose/bd_ckan/comments?desde=", headers=CABECERA_VALIDA)
    assert respuesta.status_code == 200
    assert respuesta.json()["total"] == 4


def test_comentarios_desde_invalido_da_422():
    respuesta = cliente.get("/api/v1/expose/bd_ckan/comments?desde=ayer", headers=CABECERA_VALIDA)
    assert respuesta.status_code == 422


def test_ids_se_repiten_entre_municipios():
    # La clave real es municipio + id: el mismo id existe en municipios distintos.
    comentarios = cliente.get("/api/v1/expose/bd_ckan/comments", headers=CABECERA_VALIDA).json()["comentarios"]
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
