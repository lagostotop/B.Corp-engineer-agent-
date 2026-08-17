from supabase import create_client
from config import SUPABASE_URL, SUPABASE_KEY

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

def search_documents(query: str, user_id: str) -> str:
    """Search user's uploaded documents in your 'documents' + 'embeddings' tables"""
    # Simple version: search documents table
    res = supabase.table("documents").select("name, content").eq("user_id", user_id).ilike("content", f"%{query}%").limit(3).execute()

    docs = res.data
    if not docs:
        return "No relevant documents found"

    return "\n".join([f"- {d['name']}: {d['content'][:200]}..." for d in docs])
