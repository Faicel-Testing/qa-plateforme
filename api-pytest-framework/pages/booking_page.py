from pages.base_api import BaseAPI
from payloads.booking_payloads import (
    create_booking, create_booking_without_field, create_booking_minimal,
    update_booking, patch_booking,
)


class BookingPage(BaseAPI):
    """Encapsule les appels CRUD à l'endpoint /booking."""

    ENDPOINT = "/booking"

    # ── GET ───────────────────────────────────────────────────────────────────

    def get_all_bookings(self, **filters):
        return self.get(self.ENDPOINT, params=filters or None)

    def get_booking(self, booking_id):
        return self.get(f"{self.ENDPOINT}/{booking_id}")

    # ── CREATE ────────────────────────────────────────────────────────────────

    def create_booking(self, **kwargs):
        return self.post(self.ENDPOINT, create_booking(**kwargs))

    def create_booking_minimal(self):
        """Crée sans le champ optionnel additionalneeds."""
        return self.post(self.ENDPOINT, create_booking_minimal())

    def create_booking_without_field(self, field: str):
        """Crée avec un champ requis manquant — doit déclencher une erreur côté API."""
        return self.post(self.ENDPOINT, create_booking_without_field(field))

    def create_booking_empty(self):
        """POST avec body vide {}."""
        return self.post(self.ENDPOINT, {})

    def create_booking_with_dates(self, checkin: str, checkout: str):
        return self.post(self.ENDPOINT, create_booking(checkin=checkin, checkout=checkout))

    def create_booking_with_price(self, totalprice: int):
        return self.post(self.ENDPOINT, create_booking(totalprice=totalprice))

    def create_booking_xss(self):
        """Payload XSS dans firstname — l'API doit encoder ou rejeter."""
        return self.post(self.ENDPOINT, create_booking(
            firstname='<script>alert("XSS")</script>'
        ))

    # ── UPDATE (PUT) ──────────────────────────────────────────────────────────

    def update_booking(self, booking_id, **kwargs):
        return self.put(f"{self.ENDPOINT}/{booking_id}", update_booking(**kwargs))

    def update_booking_without_field(self, booking_id, field: str):
        payload = update_booking()
        payload.pop(field, None)
        return self.put(f"{self.ENDPOINT}/{booking_id}", payload)

    # ── PATCH ─────────────────────────────────────────────────────────────────

    def patch_booking(self, booking_id, **kwargs):
        return self.patch(f"{self.ENDPOINT}/{booking_id}", patch_booking(**kwargs))

    def patch_booking_empty(self, booking_id):
        """PATCH avec body vide {} — la réservation ne doit pas changer."""
        return self.patch(f"{self.ENDPOINT}/{booking_id}", {})

    # ── DELETE ────────────────────────────────────────────────────────────────

    def delete_booking(self, booking_id):
        return self.delete(f"{self.ENDPOINT}/{booking_id}")
