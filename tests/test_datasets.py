from fastapi.testclient import TestClient

from app.config import get_settings
from app.errors import ErrorDataGovNoDisponible
from app.main import app
from app.services.datagov_client import ClienteDataGovFalso, get_cliente_datagov

cliente = TestClient(app)
CABECERA_VALIDA = {"Authorization": f"Bearer {get_settings().api_token}"}

# Las vistas de comentarios se consumen bajo el dataset gold_valledata (su nombre va en la
# URL), con las columnas que entrega el cliente falso.
BASE = "/api/v1/consume/gold_valledata"
VISTAS = {
    "valledata_api_comentarios_detalle": {"id_comentario", "fecha_publicacion", "id_municipio_dataset", "municipio", "dataset_id", "nombre_dataset", "sentimiento", "emocion", "texto_es"},
    "valledata_api_comentarios_resumen_dataset": {"id_municipio_dataset", "municipio", "dataset_id", "nombre_dataset", "total_comentarios", "positivos", "negativos", "neutros", "indice_sentimiento", "sentimiento_predominante", "emocion_predominante"},
}


def test_las_vistas_reexponen_datos_falsos():
    for vista, columnas in VISTAS.items():
        respuesta = cliente.get(f"{BASE}/{vista}?limite=1", headers=CABECERA_VALIDA)
        assert respuesta.status_code == 200, vista

        cuerpo = respuesta.json()
        assert cuerpo["identificador"] == vista
        assert len(cuerpo["filas"]) == 1
        # Las columnas llegan tal cual desde DataGov (pass-through).
        assert set(cuerpo["filas"][0]) == columnas, vista


def test_sin_limite_trae_todos():
    # Sin el parametro `limite` se devuelven todas las filas (el falso tiene 2 por vista).
    respuesta = cliente.get(f"{BASE}/valledata_api_comentarios_detalle", headers=CABECERA_VALIDA)
    assert respuesta.status_code == 200
    assert respuesta.json()["total_devuelto"] == 2


def test_respeta_el_limite():
    respuesta = cliente.get(f"{BASE}/valledata_api_comentarios_detalle?limite=1", headers=CABECERA_VALIDA)
    assert respuesta.status_code == 200
    assert len(respuesta.json()["filas"]) == 1


def test_rechaza_limite_invalido():
    respuesta = cliente.get(f"{BASE}/valledata_api_comentarios_detalle?limite=0", headers=CABECERA_VALIDA)
    assert respuesta.status_code == 422


def test_sin_token_da_401():
    respuesta = cliente.get(f"{BASE}/valledata_api_comentarios_detalle")
    assert respuesta.status_code == 401


def test_con_token_incorrecto_da_401():
    cabecera_mala = {"Authorization": "Bearer token-inventado-que-no-sirve"}
    respuesta = cliente.get(f"{BASE}/valledata_api_comentarios_detalle", headers=cabecera_mala)
    assert respuesta.status_code == 401


def test_si_datagov_falla_devuelve_502():
    # Simulamos que DataGov no responde: el cliente lanza ErrorDataGovNoDisponible.
    # El manejador de errores debe traducirlo a un 502 limpio, no a un 500 feo.
    class ClienteQueFalla:
        def obtener_dataset(self, fuente: str, tabla: str, limite: int) -> dict:
            raise ErrorDataGovNoDisponible("conexion rechazada")

    app.dependency_overrides[get_cliente_datagov] = lambda: ClienteQueFalla()
    try:
        respuesta = cliente.get(f"{BASE}/valledata_api_comentarios_detalle", headers=CABECERA_VALIDA)
        assert respuesta.status_code == 502
        assert "DataGov" in respuesta.json()["detail"]
    finally:
        app.dependency_overrides.clear()


def test_cliente_falso_entrega_la_misma_forma_que_datagov():
    datos = ClienteDataGovFalso().obtener_dataset("gold_valledata", "valledata_api_comentarios_detalle", limite=2)
    assert set(datos) == {"identificador", "filas", "total_devuelto"}
    assert datos["total_devuelto"] == 2
