"""Steps BDD pour booking_delete.feature -- DELETE /booking/{id}."""
from pytest_bdd import when, then
from pages.booking_page import BookingPage


# ── When : DELETE /booking/{id} ───────────────────────────────────────────────

@when("j'envoie DELETE /booking/{id} avec mon token (Cookie)")
def delete_booking_valid(ctx):
    ctx["response"] = ctx["booking"].delete_booking(ctx["booking_id"])


@when("j'envoie GET /booking/{id} apres la suppression")
def get_booking_after_delete(ctx):
    ctx["response"] = ctx["booking"].get_booking(ctx["booking_id"])


@when("j'envoie DELETE /booking/{id} sans header d'authentification")
def delete_no_token(ctx):
    resp_create = ctx["booking"].create_booking()
    ctx["booking_id"] = resp_create.json()["bookingid"]
    ctx["response"] = BookingPage().delete_booking(ctx["booking_id"])


@when("j'envoie DELETE /booking/{id} avec un token invalide")
def delete_invalid_token(ctx):
    resp_create = ctx["booking"].create_booking()
    ctx["booking_id"] = resp_create.json()["bookingid"]
    ctx["response"] = BookingPage(token="FAKE_TOKEN_INVALID").delete_booking(
        ctx["booking_id"]
    )


@when("j'envoie DELETE /booking/9999999 avec mon token")
def delete_inexistant(ctx):
    ctx["response"] = ctx["booking"].delete_booking(9999999)


@when("j'envoie DELETE /booking/{id} une seconde fois")
def delete_booking_twice(ctx):
    # Crée une réservation, la supprime une première fois, puis une seconde
    resp = ctx["booking"].create_booking()
    bid  = resp.json()["bookingid"]
    ctx["booking"].delete_booking(bid)          # 1er DELETE → 201
    ctx["response"] = ctx["booking"].delete_booking(bid)  # 2e DELETE → 404/405


# ── Then : assertions DELETE ──────────────────────────────────────────────────
# Note: 'le body de la reponse contient "Created"' est dans common_steps.py
