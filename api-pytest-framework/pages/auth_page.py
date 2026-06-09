from pages.base_api import BaseAPI
from payloads.booking_payloads import auth_payload


class AuthPage(BaseAPI):
    """Encapsule les appels à l'endpoint /auth."""

    ENDPOINT = "/auth"

    def create_token(self, username: str = None, password: str = None):
        payload = auth_payload(username, password) if username else auth_payload()
        return self.post(self.ENDPOINT, payload)

    def get_token(self) -> str:
        response = self.create_token()
        return response.json().get("token", "")
