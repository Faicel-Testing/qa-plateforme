import pytest
import allure
from api.resources.api_resources import ApiResources


@pytest.mark.regression
@allure.title("GET Book sans autorisation — 403 non applicable (endpoint public)")
@allure.description(
    "Test de sécurité : un 403 serait attendu si l'endpoint était protégé par des rôles. "
    "Or GetBook est public et retourne 200. "
    "Le test est marqué XFAIL (non applicable)."
)
@pytest.mark.xfail(reason="Endpoint public : pas de contrôle d'autorisation → 403 non applicable", strict=True)
def test_get_books_forbidden_returns_403(http_session, library_url):
    url = library_url + ApiResources.GET_BOOK
    params = {"AuthorName": "Rahul Shetty2"}

    response = http_session.get(url, params=params)

    # assertion théorique sécurité
    assert response.status_code == 403
