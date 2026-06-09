from pytest_bdd import scenarios
from steps.auth_steps import api_available
from steps.booking_steps import *

scenarios("booking.feature")
