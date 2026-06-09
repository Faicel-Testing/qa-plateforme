"""Steps BDD pour booking_update.feature -- PUT /booking/{id}."""
from pytest_bdd import when, then
from pages.booking_page import BookingPage


# ── When : PUT /booking/{id} ──────────────────────────────────────────────────

@when("j'envoie PUT /booking/{id} avec tous les champs et mon token (Cookie)")
def put_booking_valid(ctx):
    ctx["update_payload"] = {"firstname": "UpdatedJim", "lastname": "UpdatedBrown",
                              "totalprice": 999, "depositpaid": True,
                              "checkin": "2026-01-01", "checkout": "2026-01-10"}
    ctx["response"] = ctx["booking"].update_booking(
        ctx["booking_id"],
        firstname="UpdatedJim", lastname="UpdatedBrown",
        totalprice=999,
    )


@when("j'envoie GET /booking/{id} pour verifier la persistence apres PUT")
def get_booking_after_put(ctx):
    ctx["response"] = ctx["booking"].get_booking(ctx["booking_id"])


@when("j'envoie PUT /booking/{id} sans header d'authentification")
def put_booking_no_token(ctx):
    ctx["response"] = BookingPage().update_booking(ctx["booking_id"])


@when("j'envoie PUT /booking/{id} avec un token invalide")
def put_booking_invalid_token(ctx):
    ctx["response"] = BookingPage(token="FAKE_TOKEN_INVALID").update_booking(
        ctx["booking_id"]
    )


@when("j'envoie PUT /booking/9999999 avec mon token")
def put_booking_inexistant(ctx):
    ctx["response"] = ctx["booking"].update_booking(9999999)


@when("j'envoie PUT /booking/{id} sans le champ requis firstname")
def put_booking_missing_field(ctx):
    ctx["response"] = ctx["booking"].update_booking_without_field(
        ctx["booking_id"], "firstname"
    )


# ── Then : assertions PUT ─────────────────────────────────────────────────────
# Note: "la reponse contient les donnees mises a jour" est dans common_steps.py

@then("un GET /booking/{id} confirme que les modifications sont persistees")
def check_persistence(ctx):
    body = ctx["response"].json()
    assert body.get("firstname") == "UpdatedJim", (
        f"Persistance echouee -- firstname : {body}"
    )
