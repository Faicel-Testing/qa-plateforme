"""Steps BDD pour booking_patch.feature -- PATCH /booking/{id}."""
from pytest_bdd import when, then
from pages.booking_page import BookingPage


# ── When : PATCH /booking/{id} ────────────────────────────────────────────────

@when('j\'envoie PATCH /booking/{id} avec {"firstname": "UpdatedName"}')
def patch_firstname(ctx):
    ctx["response"] = ctx["booking"].patch_booking(
        ctx["booking_id"], firstname="UpdatedName"
    )


@when('j\'envoie PATCH /booking/{id} avec {"totalprice": 999}')
def patch_totalprice(ctx):
    ctx["response"] = ctx["booking"].patch_booking(
        ctx["booking_id"], totalprice=999
    )


@when('j\'envoie PATCH /booking/{id} avec {"lastname": "Updated", "totalprice": 500}')
def patch_lastname_and_price(ctx):
    ctx["response"] = ctx["booking"].patch_booking(
        ctx["booking_id"], lastname="Updated", totalprice=500
    )


@when("j'envoie PATCH /booking/{id} sans header d'authentification")
def patch_no_token(ctx):
    ctx["response"] = BookingPage().patch_booking(ctx["booking_id"], firstname="X")


@when("j'envoie PATCH /booking/{id} avec un token invalide")
def patch_invalid_token(ctx):
    ctx["response"] = BookingPage(token="FAKE_TOKEN_INVALID").patch_booking(
        ctx["booking_id"], firstname="X"
    )


@when("j'envoie PATCH /booking/9999999 avec mon token")
def patch_inexistant(ctx):
    ctx["response"] = ctx["booking"].patch_booking(9999999, firstname="X")


@when("j'envoie PATCH /booking/{id} avec un body vide {}")
def patch_empty_body(ctx):
    ctx["response"] = ctx["booking"].patch_booking_empty(ctx["booking_id"])


# ── Then : assertions PATCH ───────────────────────────────────────────────────

@then("la reponse contient le nouveau firstname")
def check_new_firstname(ctx):
    body = ctx["response"].json()
    assert body.get("firstname") == "UpdatedName", (
        f"firstname non mis a jour : {body}"
    )


@then("la reponse contient totalprice = 999")
def check_new_totalprice(ctx):
    body = ctx["response"].json()
    assert body.get("totalprice") == 999, (
        f"totalprice non mis a jour : {body}"
    )


@then("la reponse contient le nouveau lastname et totalprice")
def check_lastname_and_price(ctx):
    body = ctx["response"].json()
    assert body.get("lastname")   == "Updated", f"lastname invalide : {body}"
    assert body.get("totalprice") == 500,       f"totalprice invalide : {body}"


@then("la reservation n'a pas ete modifiee")
def check_unchanged(ctx):
    # PATCH {} retourne 200 avec la réservation inchangée
    body = ctx["response"].json()
    assert "firstname" in body, f"Reponse inattendue apres PATCH vide : {body}"
