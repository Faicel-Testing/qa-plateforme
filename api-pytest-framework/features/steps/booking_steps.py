from pytest_bdd import given, when, then, parsers
from pages.auth_page import AuthPage
from pages.booking_page import BookingPage


@given("I have a valid auth token", target_fixture="booking_page")
def get_booking_page(auth_page):
    token = auth_page.get_token()
    return BookingPage(token=token)


@given("a booking exists", target_fixture="booking_id")
def existing_booking(booking_page):
    response = booking_page.create_booking()
    return response.json()["bookingid"]


# ── GET all bookings ──────────────────────────────────────────────────────────

@when("I get the list of all bookings", target_fixture="response")
def get_all_bookings(booking_page):
    return booking_page.get_all_bookings()


@then("the response contains a list of booking ids")
def check_booking_list(response):
    body = response.json()
    assert isinstance(body, list)
    assert all("bookingid" in item for item in body)


# ── GET booking by id ─────────────────────────────────────────────────────────

@when("I get the booking by its id", target_fixture="response")
def get_booking(booking_page, booking_id):
    return booking_page.get_booking(booking_id)


@then("the response contains the booking details")
def check_booking_details(response):
    body = response.json()
    assert "firstname" in body
    assert "lastname" in body
    assert "bookingdates" in body


# ── CREATE booking ────────────────────────────────────────────────────────────

@when("I create a booking with valid data", target_fixture="response")
def create_new_booking(booking_page):
    return booking_page.create_booking()


@then("the response contains the new booking id")
def check_new_booking_id(response):
    assert "bookingid" in response.json()


# ── UPDATE booking (PUT) ──────────────────────────────────────────────────────

@when("I update the booking with valid data", target_fixture="response")
def update_booking_valid(booking_page, booking_id):
    return booking_page.update_booking(booking_id, firstname="Updated")


@when("I update the booking without token", target_fixture="response")
def update_booking_no_token(auth_page, booking_id):
    return BookingPage().update_booking(booking_id)


@then("the booking is updated")
def check_updated(response):
    assert response.json()["firstname"] == "Updated"


# ── PATCH booking ─────────────────────────────────────────────────────────────

@when("I patch the booking firstname", target_fixture="response")
def patch_booking_valid(booking_page, booking_id):
    return booking_page.patch_booking(booking_id, firstname="Patched")


@when("I patch the booking without token", target_fixture="response")
def patch_booking_no_token(auth_page, booking_id):
    return BookingPage().patch_booking(booking_id, firstname="Patched")


@then("the firstname is updated")
def check_patched(response):
    assert response.json()["firstname"] == "Patched"


# ── DELETE booking ────────────────────────────────────────────────────────────

@when("I delete the booking with valid token", target_fixture="response")
def delete_booking_valid(booking_page, booking_id):
    return booking_page.delete_booking(booking_id)


@when("I delete the booking without token", target_fixture="response")
def delete_booking_no_token(auth_page, booking_id):
    return BookingPage().delete_booking(booking_id)


# ── Shared then ───────────────────────────────────────────────────────────────

@then(parsers.parse("the response status is {status_code:d}"))
def check_status(response, status_code):
    assert response.status_code == status_code
