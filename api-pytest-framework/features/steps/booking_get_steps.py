"""Steps BDD pour booking_get.feature -- GET /booking/{id}."""
import re as _re
from pytest_bdd import when, then


# ── When : GET /booking/{id} ──────────────────────────────────────────────────

@when("j'envoie GET /booking/9999999")
def get_booking_inexistant(ctx):
    ctx["response"] = ctx["booking"].get_booking(9999999)


@when("j'envoie GET /booking/-1")
def get_booking_negatif(ctx):
    ctx["response"] = ctx["booking"].get_booking(-1)


@when("j'envoie GET /booking/abc")
def get_booking_string(ctx):
    ctx["response"] = ctx["booking"].get_booking("abc")


@when("j'envoie GET /booking/0")
def get_booking_zero(ctx):
    ctx["response"] = ctx["booking"].get_booking(0)


@when("j'envoie GET /booking/{id} et je valide le schema JSON de la reponse")
def get_booking_schema(ctx):
    ctx["response"] = ctx["booking"].get_booking(ctx["booking_id"])


@when("j'envoie GET /booking/{id} et je verifie le format des dates")
def get_booking_dates(ctx):
    ctx["response"] = ctx["booking"].get_booking(ctx["booking_id"])


# ── Then : assertions detail ──────────────────────────────────────────────────

# Note: "la reponse contient les champs firstname..." est dans common_steps.py

@then("le schema JSON de la reponse est conforme au modele Booking")
def check_booking_schema(ctx):
    body = ctx["response"].json()
    assert isinstance(body.get("firstname"),   str),  "firstname doit etre une chaine"
    assert isinstance(body.get("lastname"),    str),  "lastname doit etre une chaine"
    assert isinstance(body.get("totalprice"),  int),  "totalprice doit etre un entier"
    assert isinstance(body.get("depositpaid"), bool), "depositpaid doit etre un booleen"
    dates = body.get("bookingdates", {})
    assert "checkin"  in dates, "bookingdates.checkin absent"
    assert "checkout" in dates, "bookingdates.checkout absent"


@then("les dates checkin et checkout sont au format YYYY-MM-DD")
def check_date_format(ctx):
    dates   = ctx["response"].json().get("bookingdates", {})
    pattern = _re.compile(r"^\d{4}-\d{2}-\d{2}$")
    for key in ("checkin", "checkout"):
        value = dates.get(key, "")
        assert pattern.match(value), f"Date {key} invalide : '{value}' (attendu YYYY-MM-DD)"
