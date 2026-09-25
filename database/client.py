"""Central Supabase database client."""

from functools import lru_cache

from supabase import Client, ClientOptions, create_client

from core.config import settings


@lru_cache(maxsize=1)
def get_supabase() -> Client:
    if not settings.supabase_url:
        raise RuntimeError("SUPABASE_URL is missing.")

    if not settings.supabase_secret_key:
        raise RuntimeError("SUPABASE_SECRET_KEY is missing.")

    if not settings.supabase_url.startswith("https://"):
        raise RuntimeError("SUPABASE_URL must use HTTPS.")

    return create_client(
        settings.supabase_url.rstrip("/"),
        settings.supabase_secret_key,
        options=ClientOptions(
            auto_refresh_token=False,
            persist_session=False,
            postgrest_client_timeout=30,
            storage_client_timeout=30,
        ),
    )


def db() -> Client:
    return get_supabase()


def test_database_connection() -> dict:
    """
    Perform a real PostgREST database test.

    Does not expose secrets.
    """
    try:
        response = (
            db()
            .table("chats")
            .select("id")
            .limit(1)
            .execute()
        )

        return {
            "ok": True,
            "table": "chats",
            "rows_returned": len(response.data or []),
        }

    except Exception as exc:
        return {
            "ok": False,
            "table": "chats",
            "error_type": type(exc).__name__,
            "error": str(exc)[:500],
        }