"""Enrollment eligibility policy.

The PRD marks withdrawn/incomplete handling as a *proposed* policy, so it lives behind a
version boundary. Every enrollment records the policy version that produced its eligibility.
To change the rule, add a new version here; do not edit an old one silently.
"""

POLICY_VERSION = "proposed-v1"

# status -> counts toward outcome calculations?
ELIGIBILITY_BY_STATUS: dict[str, bool] = {
    "enrolled": True,
    "completed": True,
    "withdrawn": False,
    "incomplete": False,
}


def is_eligible(status: str) -> bool:
    return ELIGIBILITY_BY_STATUS[status]
