"""Steps partagés par toutes les features BDD (Background + Then communs)."""
from pytest_bdd import given, when, then, parsers
from pages.auth_page import AuthPage
from pages.booking_page import BookingPage


# ── Background commun ─────────────────────────────────────────────────────────

@given("l'API est disponible")
def api_disponible(ctx):
    ctx["auth"]    = AuthPage()
    ctx["booking"] = BookingPage()


@given("j'ai un token d'authentification valide")
def token_valide(ctx):
    ctx["token"]   = ctx["auth"].get_token()
    ctx["booking"] = BookingPage(token=ctx["token"])


@given("une reservation existe avec un ID valide")
def booking_valide_id(ctx):
    resp = ctx["booking"].create_booking()
    ctx["booking_id"] = resp.json()["bookingid"]


@given("une reservation existe avec son ID")
def booking_avec_id(ctx):
    resp = ctx["booking"].create_booking()
    ctx["booking_id"] = resp.json()["bookingid"]


@given("j'ai cree une reservation et recupere son ID")
def booking_cree_id(ctx):
    resp = ctx["booking"].create_booking()
    ctx["booking_id"] = resp.json()["bookingid"]


@given("j'ai supprime la reservation avec succes")
def booking_supprime(ctx):
    if "booking_id" not in ctx:
        resp = ctx["booking"].create_booking()
        ctx["booking_id"] = resp.json()["bookingid"]
    ctx["booking"].delete_booking(ctx["booking_id"])


# ── Then : status code ────────────────────────────────────────────────────────

@then(parsers.re(r"le status code est (?P<code>\d+)$"))
def check_status(ctx, code):
    resp = ctx["response"]
    assert resp.status_code == int(code), (
        f"Attendu HTTP {code}, recu {resp.status_code} -- {resp.text[:300]}"
    )


@then(parsers.re(r"le status code est (?P<c1>\d+) ou (?P<c2>\d+)"))
def check_status_or(ctx, c1, c2):
    resp = ctx["response"]
    assert resp.status_code in (int(c1), int(c2)), (
        f"Attendu HTTP {c1} ou {c2}, recu {resp.status_code} -- {resp.text[:300]}"
    )


# ── Then : securite ───────────────────────────────────────────────────────────

@then("le payload est encode ou refuse -- aucune execution")
def payload_non_execute(ctx):
    body = ctx["response"].text.lower()
    assert "<script>" not in body, f"XSS non filtre dans la reponse : {body[:300]}"


# ── When : GET /booking/{id} (partagé booking_get / update / delete) ──────────

@when("j'envoie GET /booking/{id}")
def get_booking_by_id_common(ctx):
    ctx["response"] = ctx["booking"].get_booking(ctx["booking_id"])


# ── Then : champs et données (partagé create / get / update) ──────────────────

@then("la reponse contient les champs firstname, lastname, totalprice, depositpaid, bookingdates")
def check_booking_fields_common(ctx):
    body = ctx["response"].json()
    # POST /booking imbrique sous "booking", GET /booking/{id} est direct
    data = body.get("booking", body)
    for field in ("firstname", "lastname", "totalprice", "depositpaid", "bookingdates"):
        assert field in data, f"Champ '{field}' absent dans : {data}"


@then("la reponse contient les donnees mises a jour")
def check_updated_data_common(ctx):
    body = ctx["response"].json()
    assert body.get("firstname") == "UpdatedJim", (
        f"firstname non mis a jour : {body}"
    )
    assert body.get("totalprice") == 999, f"totalprice non mis a jour : {body}"


# ── Then : corps de la reponse ────────────────────────────────────────────────

@then('le body de la reponse contient "Created"')
def check_body_created(ctx):
    assert "Created" in ctx["response"].text, (
        f"'Created' absent de la reponse : {ctx['response'].text[:200]}"
    )


# ── Then : 404 ────────────────────────────────────────────────────────────────

@then("la reponse est 404 Not Found")
def check_404_body(ctx):
    assert ctx["response"].status_code == 404, (
        f"Attendu 404, recu {ctx['response'].status_code}"
    )
