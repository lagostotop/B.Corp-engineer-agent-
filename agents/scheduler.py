def create_schedule(cron: str, prompt: str, user_id: str, supabase):
    """Save to scheduled_tasks table"""
    supabase.table("scheduled_tasks").insert({
        "user_id": user_id,
        "cron": cron,
        "prompt": prompt
    }).execute()
    return "Scheduled"
