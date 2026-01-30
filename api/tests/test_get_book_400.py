from urllib.parse import urljoin
from api.resources.api_resources import ApiResources


def _build_url(library_url: str, endpoint: str) -> str:
    return urljoin(library_url.rstrip("/") + "/", endpoint.lstrip("/"))


def test_get_book_without_author_param_returns_200_and_empty_body(http_session, library_url):
    """
    Cas négatif réaliste (basé sur le comportement réel de l'API) :
    GET sans AuthorName -> 200 mais body vide (non JSON)
    """
    url = _build_url(library_url, ApiResources.GET_BOOK)

    response = http_session.get(url)

    assert response.status_code == 200
    assert response.text.strip() == "", f"Body attendu vide, reçu: {response.text!r}"

