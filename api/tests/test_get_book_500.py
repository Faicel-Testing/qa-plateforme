from urllib.parse import urljoin
import pytest
import allure
from api.resources.api_resources import ApiResources


@pytest.mark.regression
def test_get_book_with_invalid_params_returns_500(http_session, library_url):
    """
    Cas négatif :
    Appel GET Book avec des paramètres volontairement invalides
    → attendu : 500 Internal Server Error
    """

    url = library_url + "/GetBook.php"

    # Paramètre volontairement invalide (type inattendu)
    params = {
        "AuthorName": {"invalid": "object"}  # provoque une erreur serveur possible
    }

    response = http_session.get(url, params=params)

    if response.status_code != 500:
        print("URL    =", url)
        print("STATUS =", response.status_code)
        print("BODY   =", response.text)

    assert response.status_code == 500
