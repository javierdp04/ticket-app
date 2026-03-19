"""Lightweight CSRF protection using Flask sessions."""
import secrets
from functools import wraps

from flask import session, request, abort


def generate_csrf_token():
    """Generate and store a CSRF token in the session."""
    if "_csrf_token" not in session:
        session["_csrf_token"] = secrets.token_hex(32)
    return session["_csrf_token"]


def csrf_protect(f):
    """Decorator to validate CSRF token on POST requests.

    Skips validation for endpoints that receive external webhooks
    (identified by having no session cookie / no CSRF token in session).
    """
    @wraps(f)
    def decorated(*args, **kwargs):
        if request.method == "POST":
            token = session.get("_csrf_token")
            form_token = request.form.get("_csrf_token", "")
            if not token or not form_token or token != form_token:
                abort(403)
        return f(*args, **kwargs)
    return decorated
