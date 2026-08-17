def save_memory(user_id: str, key: str, value: str, supabase):
    supabase.table("brain30_memory").upsert({
        "user_id": user_id,
        "key": key,
        "value": value
    }).execute()

def get_memory(user_id: str, query: str, supabase):
    res = supabase.table("brain30_memory").select("value").eq("user_id", user_id).ilike("key", f"%{query}%").limit(5).execute()
    return [r["value"] for r in res.data]
