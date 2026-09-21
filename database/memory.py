"""Supabase long-term memory operations."""

from typing import Optional

from .client import db


def save_memory(
    user_id: str,
    content: str,
    memory_type: str = "general",
    metadata: Optional[dict] = None,
) -> dict:
    payload = {
        "user_id": str(user_id),
        "content": content,
        "memory_type": memory_type,
        "metadata": metadata or {},
    }

    result = db().table("brain30_memory").insert(payload).execute()

    if not result.data:
        raise RuntimeError("Failed to save memory.")

    return result.data[0]


def get_memory(
    user_id: str,
    limit: int = 50,
    memory_type: Optional[str] = None,
) -> list:
    limit = max(1, min(int(limit), 200))

    query = (
        db()
        .table("brain30_memory")
        .select("*")
        .eq("user_id", str(user_id))
        .order("created_at", desc=True)
        .limit(limit)
    )

    if memory_type:
        query = query.eq("memory_type", memory_type)

    result = query.execute()
    return result.data or []


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