"""Central Supabase database client."""

from functools import lru_cache

from supabase import Client,ClientOptions,create_client

from core.config import settings


@lru_cache(maxsize=1)
def get_supabase()->Client:
    settings.validate()
    return create_client(
        settings.supabase_url,
        settings.supabase_secret_key,
        options=ClientOptions(
            auto_refresh_token=False,
            persist_session=False,
            postgrest_client_timeout=30,
            storage_client_timeout=30,
        ),
    )


def db()->Client:
    return get_supabase()