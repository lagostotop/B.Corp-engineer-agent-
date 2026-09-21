"""Supabase chat database operations."""

import uuid
from typing import Optional

from .client import db


def create_chat(user_id: str, title: str = "New Chat") -> dict:
    chat_id = str(uuid.uuid4())

    result = (
        db()
        .table("chats")
        .insert({
            "id": chat_id,
            "user_id": str(user_id),
            "title": title[:200],
        })
        .execute()
    )

    if not result.data:
        raise RuntimeError("Failed to create chat.")

    return result.data[0]


def get_chat(chat_id: str, user_id: str) -> Optional[dict]:
    result = (
        db()
        .table("chats")
        .select("*")
        .eq("id", str(chat_id))
        .eq("user_id", str(user_id))
        .maybe_single()
        .execute()
    )

    return result.data


def list_chats(user_id: str, limit: int = 50) -> list:
    limit = max(1, min(int(limit), 100))

    result = (
        db()
        .table("chats")
        .select("*")
        .eq("user_id", str(user_id))
        .order("updated_at", desc=True)
        .limit(limit)
        .execute()
    )

    return result.data or []


def update_chat(
    chat_id: str,
    user_id: str,
    title: Optional[str] = None,
) -> Optional[dict]:
    if title is None:
        return get_chat(chat_id, user_id)

    result = (
        db()
        .table("chats")
        .update({"title": str(title)[:200]})
        .eq("id", str(chat_id))
        .eq("user_id", str(user_id))
        .execute()
    )

    return result.data[0] if result.data else None


def delete_chat(chat_id: str, user_id: str) -> bool:
    result = (
        db()
        .table("chats")
        .delete()
        .eq("id", str(chat_id))
        .eq("user_id", str(user_id))
        .execute()
    )

    return bool(result.data)