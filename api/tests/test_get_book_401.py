from urllib.parse import urljoin
import pytest
import allure
from api.resources.api_resources import ApiResources


@pytest.mark.regression
def _build_url(library_url: str, endpoint: str) -> str:
    return urljoin(library_url.rstrip("/") + "/", endpoint.lstrip("/"))


@allure.title("GET Book sans auth — endpoint public (401 non applicable)")
@allure.description(
    "GetBook est un endpoint PUBLIC : sans Authorization il retourne 200. "
    "Le 401 n'est pas applicable ici, donc le test est marqué XFAIL."
)
@pytest.mark.xfail(reason="Endpoint public : pas d'auth requise => 401 non applicable", strict=True)
def test_get_book_without_auth_returns_401(http_session, library_url):
    url = _build_url(library_url, ApiResources.GET_BOOK)
    response = http_session.get(url)
    assert response.status_code == 200
