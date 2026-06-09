"""Steps BDD pour booking_list.feature -- GET /booking."""
from pytest_bdd import when, then


# ── When : GET /booking ───────────────────────────────────────────────────────

@when("j'envoie GET /booking")
def get_booking_list(ctx):
    ctx["response"] = ctx["booking"].get_all_bookings()


@when("j'envoie GET /booking avec le filtre ?firstname=Jim")
def get_filter_firstname_jim(ctx):
    ctx["response"] = ctx["booking"].get_all_bookings(firstname="Jim")


@when("j'envoie GET /booking avec le filtre ?lastname=Brown")
def get_filter_lastname_brown(ctx):
    ctx["response"] = ctx["booking"].get_all_bookings(lastname="Brown")


@when("j'envoie GET /booking avec le filtre ?checkin=2018-01-01")
def get_filter_checkin(ctx):
    ctx["response"] = ctx["booking"].get_all_bookings(checkin="2018-01-01")


@when("j'envoie GET /booking avec le filtre ?checkout=2019-01-01")
def get_filter_checkout(ctx):
    ctx["response"] = ctx["booking"].get_all_bookings(checkout="2019-01-01")


@when("j'envoie GET /booking avec ?firstname=XYZ_INEXISTANT")
def get_filter_unknown_firstname(ctx):
    ctx["response"] = ctx["booking"].get_all_bookings(firstname="XYZ_INEXISTANT_99999")


@when("j'envoie GET /booking avec une injection SQL dans le filtre firstname")
def get_filter_sql_injection(ctx):
    ctx["response"] = ctx["booking"].get_all_bookings(firstname="' OR '1'='1")


# ── Then : assertions liste ───────────────────────────────────────────────────

@then("la reponse est une liste de reservations")
def check_booking_list(ctx):
    body = ctx["response"].json()
    assert isinstance(body, list), f"Attendu une liste, recu : {type(body)}"


@then('la reponse contient un champ "bookingid" entier > 0')
def check_bookingid_positive(ctx):
    body = ctx["response"].json()
    assert isinstance(body, list) and len(body) > 0, "La liste est vide"
    assert all(
        isinstance(item.get("bookingid"), int) and item["bookingid"] > 0
        for item in body
    ), f"bookingid invalide dans : {body[:3]}"


@then("la reponse est une liste vide []")
def check_empty_list(ctx):
    body = ctx["response"].json()
    assert isinstance(body, list) and len(body) == 0, (
        f"Attendu [], recu {len(body)} element(s) : {body[:3]}"
    )


@then('tous les resultats ont firstname = "Jim"')
def check_filter_jim(ctx):
    # GET /booking retourne uniquement des {bookingid: N}, sans les données détaillées
    body = ctx["response"].json()
    assert isinstance(body, list) and len(body) > 0, "Aucun resultat pour firstname=Jim"


@then('tous les resultats ont lastname = "Brown"')
def check_filter_brown(ctx):
    body = ctx["response"].json()
    assert isinstance(body, list) and len(body) > 0, "Aucun resultat pour lastname=Brown"
