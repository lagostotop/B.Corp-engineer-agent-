import os
from dotenv import load_dotenv

load_dotenv() # Load .env file for local testing

class Config:
    GROQ_API_KEY = os.getenv("GROQ_API_KEY")
    TAVILY_API_KEY = os.getenv("TAVILY_API_KEY") # LIVE WEB SEARCH
    SUPABASE_URL = os.getenv("SUPABASE_URL")
    SUPABASE_KEY = os.getenv("SUPABASE_KEY") # service_role for backend
    SUPABASE_ANON_KEY = os.getenv("SUPABASE_ANON_KEY") # public key for frontend
    REPLICATE_API_TOKEN = os.getenv("REPLICATE_API_TOKEN")
    PORT = int(os.getenv("PORT", 10000))

    @staticmethod
    def validate():
        missing = []
        for key in ["GROQ_API_KEY", "TAVILY_API_KEY", "SUPABASE_URL", "SUPABASE_KEY", "SUPABASE_ANON_KEY"]:
            if not getattr(Config, key):
                missing.append(key)
        if missing:
            raise ValueError(f"b.corp ERROR: Missing Render env vars: {', '.join(missing)}")
        print("✅ b.corp config loaded - Groq $0 stack + Tavily Search active")

config = Config()
config.validate()
