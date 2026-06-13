"""US-004 -- POST /booking -- Creer reservation"""
from pytest_bdd import scenarios
from steps.common_steps import *
from steps.booking_create_steps import *

scenarios("booking_create.feature")
