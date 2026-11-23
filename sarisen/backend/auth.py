"""
Authentication helpers.

Passwords  -> werkzeug pbkdf2 hashing (never stored in plain text)
Sessions   -> signed, time-limited tokens (itsdangerous) sent as
              "Authorization: Bearer <token>".

We use signed tokens instead of cookies because the frontend lives on
GitHub Pages while the API lives on Render - a different origin. Bearer
tokens work cleanly across origins without third-party-cookie problems.
"""
import os
from functools import wraps

from flask import g, jsonify, request
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer
from werkzeug.security import check_password_hash, generate_password_hash

SECRET_KEY = os.environ.get("SECRET_KEY", "dev-only-secret-change-me")
TOKEN_TTL_SECONDS = 60 * 60 * 24 * 7          # 7 days

_serializer = URLSafeTimedSerializer(SECRET_KEY, salt="sarisen-auth-v1")


# ---------------------------------------------------------------------
# Passwords
# ---------------------------------------------------------------------
def hash_password(raw: str) -> str:
    return generate_password_hash(raw, method="pbkdf2:sha256:260000")


def verify_password(raw: str, hashed: str) -> bool:
    try:
        return check_password_hash(hashed, raw)
    except Exception:
        return False


# ---------------------------------------------------------------------
# Tokens
# ---------------------------------------------------------------------
def make_token(user_id: str, store_id: str) -> str:
    return _serializer.dumps({"uid": str(user_id), "sid": str(store_id)})


def _read_token(token: str) -> dict:
    return _serializer.loads(token, max_age=TOKEN_TTL_SECONDS)


def require_auth(view):
    """
    Decorator: rejects the request unless a valid Bearer token is present.
    On success it exposes g.user_id and g.store_id.
    """

    @wraps(view)
    def wrapper(*args, **kwargs):
        header = request.headers.get("Authorization", "")
        if not header.startswith("Bearer "):
            return jsonify({"error": "Authentication required."}), 401

        try:
            payload = _read_token(header[7:].strip())
        except SignatureExpired:
            return jsonify({"error": "Session expired. Please log in again."}), 401
        except BadSignature:
            return jsonify({"error": "Invalid session token."}), 401

        g.user_id = payload["uid"]
        g.store_id = payload["sid"]
        return view(*args, **kwargs)

    return wrapper
