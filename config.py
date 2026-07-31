import os
from dotenv import load_dotenv

# Load .env only for local dev. Render will ignore this
load_dotenv()

class Config:
    GROQ_API_KEY = os.getenv("GROQ_API_KEY")
    TAVILY_API_KEY = os.getenv("TAVILY_API_KEY") # LIVE WEB SEARCH
    SUPABASE_URL = os.getenv("SUPABASE_URL")
    SUPABASE_KEY = os.getenv("SUPABASE_KEY") # service_role for backend
    SUPABASE_ANON_KEY = os.getenv("SUPABASE_ANON_KEY") # public key for frontend
    REPLICATE_API_TOKEN = os.getenv("REPLICATE_API_TOKEN")
    PORT = int(os.getenv("PORT", 10000))
    FLASK_ENV = os.getenv("FLASK_ENV", "production")

    @staticmethod
    def validate():
        required = ["GROQ_API_KEY", "TAVILY_API_KEY", "SUPABASE_URL", "SUPABASE_KEY"]
        missing = [key for key in required if not getattr(Config, key)]
        
        if missing:
            raise ValueError(f"B.CORP FATAL: Missing env vars: {', '.join(missing)}")
        
        # Security check: never allow service_role key in browser
        if Config.SUPABASE_KEY == Config.SUPABASE_ANON_KEY:
            raise ValueError("B.CORP FATAL: SUPABASE_KEY and SUPABASE_ANON_KEY cannot be the same")
            
        print("✅ B.CORP config loaded - Groq + Tavily + Supabase active")
        print(f"   Environment: {Config.FLASK_ENV}")
        print(f"   Port: {Config.PORT}")

config = Config()
config.validate()
