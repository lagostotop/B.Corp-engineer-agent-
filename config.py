import os

class Config:
    GROQ_API_KEY = os.getenv("GROQ_API_KEY")
    TAVILY_API_KEY = os.getenv("TAVILY_API_KEY") # NEW: FOR LIVE WEB SEARCH
    SUPABASE_URL = os.getenv("SUPABASE_URL")
    SUPABASE_KEY = os.getenv("SUPABASE_KEY")
    PORT = int(os.getenv("PORT", 10000))

    @staticmethod
    def validate():
        missing = []
        for key in ["GROQ_API_KEY", "TAVILY_API_KEY", "SUPABASE_URL", "SUPABASE_KEY"]: # ADDED TAVILY
            if not getattr(Config, key):
                missing.append(key)
        if missing:
            raise ValueError(f"b.corp ERROR: Missing Render env vars: {', '.join(missing)}")
        print("✅ b.corp config loaded - Groq $0 stack + Tavily Search active")

config = Config()
config.validate()
