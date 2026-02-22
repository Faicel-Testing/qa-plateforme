from urllib.parse import urljoin
import pytest
import allure
from api.resources.api_resources import ApiResources


def _build_url(library_url: str, endpoint: str) -> str:
    return urljoin(library_url.rstrip("/") + "/", endpoint.lstrip("/"))


@allure.title("GET Book — endpoint public (accès sans auth)")
@allure.description(
    "Contrôle de sécurité/contrat : GetBook est exposé en PUBLIC. "
    "Sans header Authorization, l'API doit répondre 200. "
    "Si un jour l'endpoint devient protégé, ce test devra être mis à jour (attendu 401/403)."
)
@allure.severity(allure.severity_level.NORMAL)
@pytest.mark.smoke
@pytest.mark.regression
def test_get_book_without_auth_returns_200(http_session, library_url):
    url = _build_url(library_url, ApiResources.GET_BOOK)

    response = http_session.get(url)

    assert response.status_code == 200
