"""Supabase long-term memory operations."""

from typing import Optional

from .client import db


def save_memory(
    user_id: str,
    key: str,
    value: str,
) -> dict:
    key = str(key).strip()
    value = str(value).strip()

    if not key:
        raise ValueError("Memory key cannot be empty.")

    if not value:
        raise ValueError("Memory value cannot be empty.")

    result = (
        db()
        .table("brain30_memory")
        .upsert(
            {
                "user_id": str(user_id),
                "key": key,
                "value": value,
            },
            on_conflict="user_id,key",
        )
        .execute()
    )

    if not result.data:
        raise RuntimeError("Failed to save memory.")

    return result.data[0]


def get_memory(
    user_id: str,
    key: Optional[str] = None,
    limit: int = 50,
) -> list:
    limit = max(1, min(int(limit), 200))

    query = (
        db()
        .table("brain30_memory")
        .select("*")
        .eq("user_id", str(user_id))
        .order("updated_at", desc=True)
        .limit(limit)
    )

    if key:
        query = query.eq("key", str(key))

    result = query.execute()
    return result.data or []


def get_memory_value(
    user_id: str,
    key: str,
) -> Optional[str]:
    result = (
        db()
        .table("brain30_memory")
        .select("value")
        .eq("user_id", str(user_id))
        .eq("key", str(key))
        .maybe_single()
        .execute()
    )

    if not result.data:
        return None

    return result.data.get("value")


def delete_memory(
    memory_id: str,
    user_id: str,
) -> bool:
    result = (
        db()
        .table("brain30_memory")
        .delete()
        .eq("id", str(memory_id))
        .eq("user_id", str(user_id))
        .execute()
    )

    return bool(result.data)


def delete_memory_by_key(
    user_id: str,
    key: str,
) -> bool:
    result = (
        db()
        .table("brain30_memory")
        .delete()
        .eq("user_id", str(user_id))
        .eq("key", str(key))
        .execute()
    )

    return bool(result.data)