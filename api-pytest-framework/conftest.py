import sys
import os
import pytest
import requests
import config

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "features"))


@pytest.fixture(scope="session")
def base_url():
    return config.BASE_URL


@pytest.fixture(scope="session")
def token(base_url):
    response = requests.post(
        f"{base_url}/auth",
        json={"username": config.USERNAME, "password": config.PASSWORD}
    )
    assert response.status_code == 200, f"Auth failed: {response.text}"
    return response.json().get("token")


@pytest.fixture
def ctx():
    """Contexte mutable partagé entre tous les steps d'un scénario BDD."""
    return {}
