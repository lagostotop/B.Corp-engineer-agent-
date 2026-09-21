"""Supabase document and RAG database operations."""

from typing import Optional

from .client import db


def create_document(
    user_id: str,
    content: str,
    embedding: Optional[list] = None,
    filename: Optional[str] = None,
    chat_id: Optional[str] = None,
    metadata: Optional[dict] = None,
) -> dict:
    payload = {
        "user_id": str(user_id),
        "content": content,
        "metadata": metadata or {},
    }

    if embedding is not None:
        payload["embedding"] = embedding

    if filename:
        payload["filename"] = filename[:255]

    if chat_id:
        payload["chat_id"] = str(chat_id)

    result = db().table("documents").insert(payload).execute()

    if not result.data:
        raise RuntimeError("Failed to create document.")

    return result.data[0]


def get_document(
    document_id: str,
    user_id: str,
) -> Optional[dict]:
    result = (
        db()
        .table("documents")
        .select("*")
        .eq("id", str(document_id))
        .eq("user_id", str(user_id))
        .maybe_single()
        .execute()
    )

    return result.data


def list_documents(
    user_id: str,
    chat_id: Optional[str] = None,
    limit: int = 100,
) -> list:
    limit = max(1, min(int(limit), 200))

    query = (
        db()
        .table("documents")
        .select("*")
        .eq("user_id", str(user_id))
        .order("created_at", desc=True)
        .limit(limit)
    )

    if chat_id:
        query = query.eq("chat_id", str(chat_id))

    result = query.execute()
    return result.data or []


def delete_document(document_id: str, user_id: str) -> bool:
    result = (
        db()
        .table("documents")
        .delete()
        .eq("id", str(document_id))
        .eq("user_id", str(user_id))
        .execute()
    )

    return bool(result.data)