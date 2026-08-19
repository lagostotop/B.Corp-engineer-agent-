import os
from dotenv import load_dotenv

# Local development only.
# Render environment variables take precedence.
load_dotenv()

class Config:
    # =========================
    # AI / SEARCH
    # =========================
    GROQ_API_KEY = os.getenv("GROQ_API_KEY")
    
    # FIX 1: ADD THESE 2 LINES - THE MISSING ONES
    GROQ_GENERAL_MODEL = os.getenv("GROQ_GENERAL_MODEL", "openai/gpt-oss-120b")
    GROQ_VISION_MODEL = os.getenv("GROQ_VISION_MODEL", "openai/gpt-oss-120b")
    
    TAVILY_API_KEY = os.getenv("TAVILY_API_KEY")
    REPLICATE_API_TOKEN = os.getenv("REPLICATE_API_TOKEN") # Optional for now

    # =========================
    # SUPABASE
    # =========================
    SUPABASE_URL = os.getenv("SUPABASE_URL")

    # SERVER ONLY - Never send this to the browser.
    SUPABASE_SECRET_KEY = os.getenv("SUPABASE_SECRET_KEY")

    # Public/browser key
    SUPABASE_PUBLISHABLE_KEY = os.getenv("SUPABASE_PUBLISHABLE_KEY")

    # =========================
    # SERVER
    # =========================
    try:
        PORT = int(os.getenv("PORT", "10000"))
    except (TypeError, ValueError):
        PORT = 10000

    FLASK_ENV = os.getenv("FLASK_ENV", "production")

    # FIX 2: ADD ALLOWED_ORIGINS
    ALLOWED_ORIGINS = os.getenv("ALLOWED_ORIGINS", "*").split(",")

    @classmethod
    def validate(cls):
        required = [
            "GROQ_API_KEY",
            "TAVILY_API_KEY",
            "SUPABASE_URL",
            "SUPABASE_KEY",
            "SUPABASE_ANON_KEY",
            "GROQ_GENERAL_MODEL" # FIX 3: ADD THIS TO VALIDATE
        ]
        # REPLICATE_API_TOKEN is optional until we add image gen

        missing = [key for key in required if not getattr(cls, key, None)]

        if missing:
            raise ValueError(
                "B.CORP FATAL: Missing environment variables: "
                + ", ".join(missing)
            )

        # =========================
        # SECURITY CHECKS
        # =========================

        if cls.SUPABASE_KEY == cls.SUPABASE_ANON_KEY:
            raise ValueError(
                "B.CORP FATAL: SUPABASE_KEY and "
                "SUPABASE_ANON_KEY cannot be the same"
            )

        # FORCE HTTPS IN PRODUCTION
        if cls.FLASK_ENV == "production" and not cls.SUPABASE_URL.startswith("https://"):
            raise ValueError(
                "B.CORP FATAL: SUPABASE_URL must use HTTPS in production"
            )
        # Allow http://localhost for local dev
        if not cls.SUPABASE_URL.startswith(("https://", "http://")):
            raise ValueError(
                "B.CORP FATAL: SUPABASE_URL must be a valid URL"
            )

        # =========================
        # STARTUP LOGGING - NO SECRETS
        # =========================
        if cls.FLASK_ENV != "production":
            print("✅ B.CORP configuration loaded")
            print(f"   Model: {cls.GROQ_GENERAL_MODEL}")
            print("   Groq: ACTIVE")
            print("   Tavily: ACTIVE")
            print("   Supabase: ACTIVE")
            print(f"   Environment: {cls.FLASK_ENV}")
            print(f"   Port: {cls.PORT}")
            print("   Supabase service key: SERVER ONLY")
        else:
            print(f"✅ B.CORP configuration loaded [PROD] Model: {cls.GROQ_GENERAL_MODEL}")

config = Config()
config.validate()
