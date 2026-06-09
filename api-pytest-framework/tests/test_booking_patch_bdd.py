"""US-006 -- PATCH /booking/{id} -- Mise a jour partielle."""
from pytest_bdd import scenarios
from steps.common_steps import *
from steps.booking_patch_steps import *

scenarios("booking_patch.feature")
