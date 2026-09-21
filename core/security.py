"""Authentication and authorization helpers for Brain 3.0."""

from functools import wraps

from flask import g, jsonify, request
from supabase import Client


class AuthError(Exception):
    def __init__(self, message="Authentication required.", status=401):
        super().__init__(message)
        self.message = message
        self.status = status


def get_bearer_token():
    header = request.headers.get("Authorization", "")
    scheme, _, token = header.partition(" ")

    if scheme.lower() != "bearer" or not token.strip():
        return None

    return token.strip()


def authenticate_request(supabase: Client):
    token = get_bearer_token()

    if not token:
        raise AuthError()

    try:
        result = supabase.auth.get_user(token)
        user = getattr(result, "user", None)

        if user is None:
            raise AuthError("Invalid or expired authentication token.")
    except AuthError:
        raise
    except Exception as exc:
        raise AuthError("Invalid or expired authentication token.") from exc

    g.user = user
    g.user_id = str(user.id)

    return user


def require_auth(supabase: Client):
    def decorator(view):
        @wraps(view)
        def wrapped(*args, **kwargs):
            try:
                authenticate_request(supabase)
            except AuthError as exc:
                return jsonify({
                    "error": {
                        "code": "AUTH_REQUIRED",
                        "message": exc.message
                    }
                }), exc.status

            return view(*args, **kwargs)

        return wrapped

    return decorator


def current_user_id(required=True):
    user_id = getattr(g, "user_id", None)

    if required and not user_id:
        raise AuthError()

    return user_id


def require_owner(resource_user_id):
    user_id = current_user_id()

    if str(resource_user_id) != str(user_id):
        raise AuthError(
            "You are not authorized to access this resource.",
            403
        )