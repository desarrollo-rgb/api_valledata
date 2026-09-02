"""Modelos de datos (contrato) que expone la API ValleData.

`Comentario` es lo que ValleData entrega en el Flujo 2, a partir de lo que hay en la tabla
`comments` de cada portal CKAN. ValleData NO clasifica: entrega el texto crudo; el analisis
de sentimiento lo hace despues el DAG de DataGov.
"""

from pydantic import BaseModel


class Comentario(BaseModel):
    # Id del comentario dentro de su municipio. OJO: NO es unico entre municipios,
    # por eso la clave real es la combinacion municipio + id.
    id: int
    # Municipio de origen (derivado del nombre de la base: "ckan_alcala" -> "alcala").
    municipio: str
    # Id del dataset comentado (columna "package_Id" en la BD).
    dataset_id: str
    # Autor del comentario (columna user_id).
    usuario: str
    # Texto del comentario separado por idioma (se parsea del JSON multilingue de la BD).
    texto_es: str | None
    texto_en: str | None
    # Fecha de creacion en UTC, formato ISO 8601.
    fecha: str
