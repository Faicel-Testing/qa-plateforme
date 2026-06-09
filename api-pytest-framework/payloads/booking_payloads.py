def create_booking(firstname="Jim", lastname="Brown", totalprice=111,
                   depositpaid=True, checkin="2025-01-01", checkout="2025-01-10",
                   additionalneeds="Breakfast") -> dict:
    return {
        "firstname":       firstname,
        "lastname":        lastname,
        "totalprice":      totalprice,
        "depositpaid":     depositpaid,
        "bookingdates":    {"checkin": checkin, "checkout": checkout},
        "additionalneeds": additionalneeds,
    }


def create_booking_without_field(field: str) -> dict:
    """Retourne un payload complet dont le champ `field` est omis."""
    full = create_booking()
    full.pop(field, None)
    return full


def create_booking_minimal() -> dict:
    """Payload sans le champ optionnel additionalneeds."""
    return {
        "firstname":    "Jim",
        "lastname":     "Brown",
        "totalprice":   111,
        "depositpaid":  True,
        "bookingdates": {"checkin": "2025-01-01", "checkout": "2025-01-10"},
    }


def update_booking(**kwargs) -> dict:
    payload = create_booking()
    payload.update(kwargs)
    return payload


def patch_booking(firstname: str = None, lastname: str = None,
                  totalprice: int = None) -> dict:
    payload = {}
    if firstname  is not None: payload["firstname"]  = firstname
    if lastname   is not None: payload["lastname"]   = lastname
    if totalprice is not None: payload["totalprice"] = totalprice
    return payload


def auth_payload(username: str = "admin", password: str = "password123") -> dict:
    return {"username": username, "password": password}
