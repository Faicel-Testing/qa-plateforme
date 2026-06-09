"""Steps BDD pour booking_create.feature -- POST /booking."""
from pytest_bdd import when, then


# ── When : POST /booking ──────────────────────────────────────────────────────

@when("j'envoie POST /booking")
def post_booking_all_fields(ctx):
    ctx["response"] = ctx["booking"].create_booking()


@when("j'envoie POST /booking avec tous les champs requis et additionalneeds")
def post_booking_full(ctx):
    ctx["response"] = ctx["booking"].create_booking()


@when("j'envoie POST /booking sans le champ optionnel additionalneeds")
def post_booking_minimal(ctx):
    ctx["response"] = ctx["booking"].create_booking_minimal()


@when("j'envoie POST /booking avec checkin = checkout = 2026-07-01")
def post_booking_same_dates(ctx):
    ctx["response"] = ctx["booking"].create_booking_with_dates(
        checkin="2026-07-01", checkout="2026-07-01"
    )


@when("j'envoie POST /booking sans le champ requis firstname")
def post_booking_no_firstname(ctx):
    ctx["response"] = ctx["booking"].create_booking_without_field("firstname")


@when("j'envoie POST /booking sans le champ requis lastname")
def post_booking_no_lastname(ctx):
    ctx["response"] = ctx["booking"].create_booking_without_field("lastname")


@when("j'envoie POST /booking sans le champ requis totalprice")
def post_booking_no_totalprice(ctx):
    ctx["response"] = ctx["booking"].create_booking_without_field("totalprice")


@when("j'envoie POST /booking sans le champ requis depositpaid")
def post_booking_no_depositpaid(ctx):
    ctx["response"] = ctx["booking"].create_booking_without_field("depositpaid")


@when("j'envoie POST /booking sans le champ requis bookingdates")
def post_booking_no_bookingdates(ctx):
    ctx["response"] = ctx["booking"].create_booking_without_field("bookingdates")


@when("j'envoie POST /booking avec totalprice = -100")
def post_booking_negative_price(ctx):
    ctx["response"] = ctx["booking"].create_booking_with_price(-100)


@when("j'envoie POST /booking avec checkin posterieur a checkout")
def post_booking_inverted_dates(ctx):
    ctx["response"] = ctx["booking"].create_booking_with_dates(
        checkin="2026-12-31", checkout="2026-01-01"
    )


@when("j'envoie POST /booking avec un body vide {}")
def post_booking_empty(ctx):
    ctx["response"] = ctx["booking"].create_booking_empty()


@when("j'envoie POST /booking avec un payload XSS dans firstname")
def post_booking_xss(ctx):
    ctx["response"] = ctx["booking"].create_booking_xss()


# ── Then : assertions creation ────────────────────────────────────────────────

@then('la reponse contient un champ "bookingid" entier > 0')
def check_bookingid_created(ctx):
    body = ctx["response"].json()
    assert "bookingid" in body, f"Champ 'bookingid' absent : {body}"
    assert isinstance(body["bookingid"], int) and body["bookingid"] > 0, (
        f"bookingid invalide : {body['bookingid']}"
    )


@then("la reservation est creee (cas limite accepte par l'API)")
def check_limite_accepte(ctx):
    body = ctx["response"].json()
    assert "bookingid" in body and body["bookingid"] > 0, (
        f"Reservation non creee (cas limite) : {body}"
    )
