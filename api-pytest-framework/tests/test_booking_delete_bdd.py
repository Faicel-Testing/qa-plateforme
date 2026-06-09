"""US-007 -- DELETE /booking/{id} -- Supprimer une reservation."""
from pytest_bdd import scenarios
from steps.common_steps import *
from steps.booking_delete_steps import *

scenarios("booking_delete.feature")
