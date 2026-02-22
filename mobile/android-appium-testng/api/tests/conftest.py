import pytest
import requests

from api.utilities.config import Config
from api.utilities.headers import Headers


@pytest.fixture(scope="session")
def base_url():
    return Config.BASE_URL


@pytest.fixture(scope="session")
def library_url(base_url):
    return base_url + Config.API_LIBRARY


@pytest.fixture(scope="session")
def json_headers():
    return Headers.JSON_HEADERS


@pytest.fixture(scope="session")
def http_session(json_headers):
    """
    Session HTTP partagée : réutilise la connexion + centralise les headers
    + conserve cookies / auth si besoin.
    """
    session = requests.Session()
    session.headers.update(json_headers)
    yield session
    session.close()
