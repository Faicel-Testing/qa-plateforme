"""US-003 -- GET /booking/{id} -- Recuperer une reservation."""
from pytest_bdd import scenarios
from steps.common_steps import *
from steps.booking_get_steps import *

scenarios("booking_get.feature")
