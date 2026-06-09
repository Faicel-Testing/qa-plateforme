from pages.base_api import BaseAPI


class HealthPage(BaseAPI):
    """Encapsule l'appel à l'endpoint /ping."""

    ENDPOINT = "/ping"

    def ping(self):
        return self.get(self.ENDPOINT)
