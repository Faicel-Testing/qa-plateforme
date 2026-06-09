import requests
import config


class BaseAPI:
    """Classe de base — gère la session HTTP, l'URL et les headers communs."""

    def __init__(self, token: str = None):
        self.base_url = config.BASE_URL
        self.session = requests.Session()
        self.session.verify = False
        self.session.headers.update({"Content-Type": "application/json"})
        if token:
            self.session.headers.update({"Cookie": f"token={token}"})

    def get(self, endpoint: str, **kwargs) -> requests.Response:
        return self.session.get(f"{self.base_url}{endpoint}", **kwargs)

    def post(self, endpoint: str, payload: dict = None, **kwargs) -> requests.Response:
        return self.session.post(f"{self.base_url}{endpoint}", json=payload, **kwargs)

    def put(self, endpoint: str, payload: dict = None, **kwargs) -> requests.Response:
        return self.session.put(f"{self.base_url}{endpoint}", json=payload, **kwargs)

    def patch(self, endpoint: str, payload: dict = None, **kwargs) -> requests.Response:
        return self.session.patch(f"{self.base_url}{endpoint}", json=payload, **kwargs)

    def delete(self, endpoint: str, **kwargs) -> requests.Response:
        return self.session.delete(f"{self.base_url}{endpoint}", **kwargs)
