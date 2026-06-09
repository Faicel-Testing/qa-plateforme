"""US-008 -- GET /ping -- Health Check."""
from pytest_bdd import scenarios
from steps.common_steps import *
from steps.health_check_steps import *

scenarios("health_check.feature")
