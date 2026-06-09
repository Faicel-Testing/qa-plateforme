"""Steps BDD pour auth.feature -- POST /auth."""
from pytest_bdd import when, then
from pages.auth_page import AuthPage


# ── When : POST /auth ─────────────────────────────────────────────────────────

@when('j\'envoie POST /auth avec username "admin" et password "password123"')
def post_auth_valid(ctx):
    ctx["response"] = ctx["auth"].create_token("admin", "password123")


@when('j\'envoie POST /auth avec username "wrong" et password "wrong"')
def post_auth_invalid(ctx):
    ctx["response"] = ctx["auth"].create_token("wrong", "wrong")


@when("j'envoie POST /auth avec un body vide {}")
def post_auth_empty(ctx):
    ctx["response"] = ctx["auth"].post("/auth", {})


@when("j'envoie POST /auth avec une injection SQL dans username")
def post_auth_sql_injection(ctx):
    ctx["response"] = ctx["auth"].create_token("' OR '1'='1", "test")


@when("j'envoie POST /auth avec un payload XSS dans password")
def post_auth_xss(ctx):
    ctx["response"] = ctx["auth"].create_token("admin", '<script>alert("XSS")</script>')


# ── Then : assertions auth ────────────────────────────────────────────────────

@then('la reponse contient un champ "token" non vide')
def check_token_present(ctx):
    body = ctx["response"].json()
    assert "token" in body, f"Champ 'token' absent : {body}"
    assert body["token"], "Le token est vide"


@then("la longueur du token est superieure a 10 caracteres")
def check_token_length(ctx):
    token = ctx["response"].json().get("token", "")
    assert len(token) > 10, f"Token trop court ({len(token)} chars) : {token}"


@then('la reponse contient {"reason": "Bad credentials"}')
def check_bad_credentials(ctx):
    body = ctx["response"].json()
    assert body.get("reason") == "Bad credentials", (
        f"Message d'erreur inattendu : {body}"
    )
