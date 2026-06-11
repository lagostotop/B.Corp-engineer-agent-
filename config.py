import os

class Config:
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
    ELEVENLABS_API_KEY = os.getenv("ELEVENLABS_API_KEY")
    SUPABASE_URL = os.getenv("SUPABASE_URL")
    SUPABASE_KEY = os.getenv("SUPABASE_KEY")
    PORT = int(os.getenv("PORT", 10000))

    @staticmethod
    def validate():
        missing = []
        for key in ["OPENAI_API_KEY", "ELEVENLABS_API_KEY", "SUPABASE_URL", "SUPABASE_KEY"]:
            if not getattr(Config, key):
                missing.append(key)
        if missing:
            raise ValueError(f"b.corp ERROR: Missing Render env vars: {', '.join(missing)}")
        print("✅ b.corp config loaded")

config = Config()
config.validate()