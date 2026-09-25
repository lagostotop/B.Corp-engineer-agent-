"""Central Supabase database client."""
from functools import lru_cache
from supabase import Client,ClientOptions,create_client
from core.config import settings

@lru_cache(maxsize=1)
def get_supabase()->Client:
    url=(settings.supabase_url or "").strip()
    key=(settings.supabase_secret_key or "").strip()
    if not url: raise RuntimeError("SUPABASE_URL is missing.")
    if not key: raise RuntimeError("SUPABASE_SECRET_KEY is missing.")
    if not url.startswith("https://"): raise RuntimeError("SUPABASE_URL must use HTTPS.")
    if not key.startswith("sb_secret_") and not key.startswith("eyJ"):
        raise RuntimeError(f"SUPABASE_SECRET_KEY has unexpected format: prefix={key[:12]!r}, length={len(key)}")
    return create_client(url.rstrip("/"),key,options=ClientOptions(auto_refresh_token=False,persist_session=False,postgrest_client_timeout=30,storage_client_timeout=30))

def db()->Client:
    return get_supabase()

def test_database_connection()->dict:
    try:
        url=(settings.supabase_url or "").strip()
        key=(settings.supabase_secret_key or "").strip()
        response=db().table("chats").select("id").limit(1).execute()
        return {"ok":True,"table":"chats","rows_returned":len(response.data or []),"supabase_url":url,"key_prefix":key[:12],"key_length":len(key)}
    except Exception as exc:
        url=(settings.supabase_url or "").strip()
        key=(settings.supabase_secret_key or "").strip()
        return {"ok":False,"table":"chats","supabase_url":url,"key_prefix":key[:12],"key_length":len(key),"error_type":type(exc).__name__,"error":str(exc)[:500]}