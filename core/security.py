from functools import wraps

from flask import g, request
from supabase import Client

from core.errors import AuthenticationError, AuthorizationError


def get_bearer_token():
    header = request.headers.get("Authorization", "")
    scheme, _, token = header.partition(" ")

    if scheme.lower() != "bearer" or not token.strip():
        return None

    return token.strip()


def authenticate_request(supabase: Client):
    token = get_bearer_token()

    if not token:
        raise AuthenticationError("Authentication required.")

    try:
        result = supabase.auth.get_user(token)
        user = getattr(result, "user", None)
    except Exception as exc:
        raise AuthenticationError(
            "Invalid or expired authentication token."
        ) from exc

    if user is None:
        raise AuthenticationError(
            "Invalid or expired authentication token."
        )

    g.user = user
    g.user_id = str(user.id)

    return user


def require_auth(supabase: Client):
    def decorator(view):
        @wraps(view)
        def wrapped(*args, **kwargs):
            authenticate_request(supabase)
            return view(*args, **kwargs)

        return wrapped

    return decorator


def current_user_id(required=True):
    user_id = getattr(g, "user_id", None)

    if required and not user_id:
        raise AuthenticationError("Authentication required.")

    return user_id


def require_owner(resource_user_id):
    user_id = current_user_id()

    if str(resource_user_id) != str(user_id):
        raise AuthorizationError(
            "You are not authorized to access this resource."
        )