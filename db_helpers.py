# db_helpers.py - Common database operations
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Any, Optional

def create_chat(user_id: str, title: str, supabase) -> Dict:
    """Create a new chat"""
    chat_id = str(uuid.uuid4())
    result = supabase.table("chats").insert({
        "id": chat_id,
        "user_id": user_id,
        "title": title[:60] or "New Chat"
    }).execute()
    return result.data[0] if result.data else None

def get_recent_chats(user_id: str, limit: int = 50, supabase) -> List[Dict]:
    """Get user's recent chats"""
    result = supabase.table("chats") \
        .select("id,title,created_at,updated_at") \
        .eq("user_id", user_id) \
        .order("updated_at", desc=True) \
        .limit(limit) \
        .execute()
    return result.data or []

def search_messages(user_id: str, query: str, supabase) -> List[Dict]:
    """Search messages by content"""
    result = supabase.table("messages") \
        .select("id,chat_id,content,role,created_at") \
        .eq("user_id", user_id) \
        .ilike("content", f"%{query}%") \
        .limit(20) \
        .execute()
    return result.data or []

def get_chat_with_messages(chat_id: str, user_id: str, supabase) -> Dict:
    """Get chat with all messages"""
    # Get chat info
    chat = supabase.table("chats") \
        .select("*") \
        .eq("id", chat_id) \
        .eq("user_id", user_id) \
        .maybe_single() \
        .execute()
    
    if not chat.data:
        return None
    
    # Get messages
    messages = supabase.table("messages") \
        .select("*") \
        .eq("chat_id", chat_id) \
        .eq("user_id", user_id) \
        .order("created_at") \
        .execute()
    
    return {
        "chat": chat.data,
        "messages": messages.data or []
    }

def get_documents_for_chat(chat_id: str, user_id: str, supabase) -> List[Dict]:
    """Get all documents for a chat"""
    result = supabase.table("documents") \
        .select("id,content,metadata,created_at") \
        .eq("chat_id", chat_id) \
        .eq("user_id", user_id) \
        .execute()
    return result.data or []

def cleanup_old_data(user_id: str, days: int = 30, supabase) -> Dict:
    """Delete data older than N days"""
    cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
    
    # Get old chats
    old_chats = supabase.table("chats") \
        .select("id") \
        .eq("user_id", user_id) \
        .lt("updated_at", cutoff) \
        .execute()
    
    deleted = 0
    for chat in old_chats.data or []:
        # Delete chat (cascade will delete messages and documents)
        supabase.table("chats").delete().eq("id", chat["id"]).execute()
        deleted += 1
    
    return {"deleted_chats": deleted, "cutoff_date": cutoff}
