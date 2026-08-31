# migrate_db.py - Run this once to set up your database
import os
from supabase import create_client
from dotenv import load_dotenv

load_dotenv()

def run_migration():
    """Run database migrations"""
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
    
    if not url or not key:
        print("❌ Missing Supabase credentials")
        return
    
    supabase = create_client(url, key)
    
    # Read migration file
    with open("supabase/migrations/20250101000000_initial_schema.sql", "r") as f:
        sql = f.read()
    
    # Execute SQL
    try:
        # Supabase doesn't support raw SQL execution via the client directly
        # Use the SQL API endpoint instead
        import requests
        response = requests.post(
            f"{url}/rest/v1/rpc/exec_sql",
            headers={
                "apikey": key,
                "Authorization": f"Bearer {key}",
                "Content-Type": "application/json"
            },
            json={"query": sql}
        )
        
        if response.status_code == 200:
            print("✅ Database migration completed successfully!")
        else:
            print(f"❌ Migration failed: {response.text}")
    except Exception as e:
        print(f"❌ Migration error: {e}")

if __name__ == "__main__":
    run_migration()
