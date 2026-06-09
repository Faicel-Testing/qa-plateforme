"""US-002 -- GET /booking -- Lister les reservations."""
from pytest_bdd import scenarios
from steps.common_steps import *
from steps.booking_list_steps import *

scenarios("booking_list.feature")
