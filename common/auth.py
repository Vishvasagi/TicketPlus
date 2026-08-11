"""
Shared session-based auth helpers for the manager and staff services.

Each service keeps its own Flask session cookie (they're separate apps on
separate domains), but both use the same pattern: a logged-in user's row id
is stored in the session under a service-specific key, checked by a
`login_required` decorator on every protected route.
"""

import secrets
import string
from functools import wraps

from flask import jsonify, session
from werkzeug.security import check_password_hash, generate_password_hash

__all__ = [
    "hash_password",
    "verify_password",
    "generate_temp_password",
    "login_required",
]


def hash_password(plain_password: str) -> str:
    return generate_password_hash(plain_password)


def verify_password(password_hash: str, plain_password: str) -> bool:
    return check_password_hash(password_hash, plain_password)


def generate_temp_password(length: int = 10) -> str:
    """A random password shown once to the manager after a reset/create."""
    alphabet = string.ascii_letters + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(length))


def login_required(session_key):
    """
    Decorator factory. session_key is the session dict key that holds the
    logged-in user's id, e.g. "manager_id" or "staff_id".
    """

    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            if not session.get(session_key):
                return jsonify({"error": "Not logged in."}), 401
            return fn(*args, **kwargs)

        return wrapper

    return decorator
