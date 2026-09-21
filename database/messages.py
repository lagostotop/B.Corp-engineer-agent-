"""Supabase message database operations."""

from typing import Optional

from .client import db


def create_message(
    user_id: str,
    chat_id: str,
    role: str,
    content: str,
    metadata: Optional[dict] = None,
    client_message_id: Optional[str] = None,
) -> dict:
    allowed_roles = {"user", "assistant", "system"}

    if role not in allowed_roles:
        raise ValueError(f"Invalid message role: {role}")

    payload = {
        "user_id": str(user_id),
        "chat_id": str(chat_id),
        "role": role,
        "content": content,
        "metadata": metadata or {},
    }

    if client_message_id:
        payload["client_message_id"] = str(client_message_id)

    result = db().table("messages").insert(payload).execute()

    if not result.data:
        raise RuntimeError("Failed to create message.")

    return result.data[0]


def get_message(
    message_id: str,
    user_id: str,
) -> Optional[dict]:
    result = (
        db()
        .table("messages")
        .select("*")
        .eq("id", str(message_id))
        .eq("user_id", str(user_id))
        .maybe_single()
        .execute()
    )

    return result.data


def list_messages(
    chat_id: str,
    user_id: str,
    limit: int = 100,
    before: Optional[str] = None,
) -> list:
    limit = max(1, min(int(limit), 200))

    query = (
        db()
        .table("messages")
        .select("*")
        .eq("chat_id", str(chat_id))
        .eq("user_id", str(user_id))
        .order("created_at", desc=False)
        .limit(limit)
    )

    if before:
        query = query.lt("created_at", before)

    result = query.execute()
    return result.data or []


def delete_message(message_id: str, user_id: str) -> bool:
    result = (
        db()
        .table("messages")
        .delete()
        .eq("id", str(message_id))
        .eq("user_id", str(user_id))
        .execute()
    )

    return bool(result.data)