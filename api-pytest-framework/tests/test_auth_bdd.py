"""US-001 -- POST /auth -- Authentification."""
from pytest_bdd import scenarios
from steps.common_steps import *
from steps.auth_steps import *

scenarios("auth.feature")
