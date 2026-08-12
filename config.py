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
    TAVILY_API_KEY = os.getenv("TAVILY_API_KEY")
    REPLICATE_API_TOKEN = os.getenv("REPLICATE_API_TOKEN") # Optional for now

    # =========================
    # SUPABASE
    # =========================
    SUPABASE_URL = os.getenv("SUPABASE_URL")

    # SERVER ONLY - Never send this to the browser.
    SUPABASE_KEY = os.getenv("SUPABASE_KEY")

    # Public/browser key
    SUPABASE_ANON_KEY = os.getenv("SUPABASE_ANON_KEY")

    # =========================
    # SERVER
    # =========================
    try:
        PORT = int(os.getenv("PORT", "10000"))
    except (TypeError, ValueError):
        PORT = 10000

    FLASK_ENV = os.getenv("FLASK_ENV", "production")

    @classmethod
    def validate(cls):
        required = [
            "GROQ_API_KEY",
            "TAVILY_API_KEY",
            "SUPABASE_URL",
            "SUPABASE_KEY",
            "SUPABASE_ANON_KEY",
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
            print("   Groq: ACTIVE")
            print("   Tavily: ACTIVE")
            print("   Supabase: ACTIVE")
            print(f"   Environment: {cls.FLASK_ENV}")
            print(f"   Port: {cls.PORT}")
            print("   Supabase service key: SERVER ONLY")
        else:
            print("✅ B.CORP configuration loaded [PROD]")

config = Config()
config.validate()
