"""Steps BDD pour health_check.feature -- GET /ping."""
import time as _time
from pytest_bdd import when, then
from pages.health_page import HealthPage


@when("j'envoie GET /ping")
def ping(ctx):
    ctx["response"] = HealthPage().ping()


@when("j'envoie GET /ping et je mesure le temps de reponse")
def ping_avec_timer(ctx):
    start = _time.monotonic()
    ctx["response"] = HealthPage().ping()
    ctx["elapsed_ms"] = (_time.monotonic() - start) * 1000


@then("le temps de reponse est inferieur a 3000 millisecondes")
def check_latence(ctx):
    elapsed = ctx.get("elapsed_ms", 0)
    assert elapsed < 3000, f"Latence trop elevee : {elapsed:.0f} ms"
