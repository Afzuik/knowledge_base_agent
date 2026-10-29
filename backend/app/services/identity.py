"""Local-only identity, NOT authentication or tenant isolation.

Future authenticated identity replaces this dependency. Never accept owner_id
from request bodies. Do not expose this scaffold to a network or real users.
"""


def get_local_owner_id() -> str:
    return "local-demo"
