"""US-005 -- PUT /booking/{id} -- Mise a jour complete"""
from pytest_bdd import scenarios
from steps.common_steps import *
from steps.booking_update_steps import *

scenarios("booking_update.feature")
