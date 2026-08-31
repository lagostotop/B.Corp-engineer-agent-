# setup_db.py
import os
import requests
from dotenv import load_dotenv

load_dotenv()

def setup_database():
    """Run initial database setup via Supabase SQL API"""
    
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
    
    if not url or not key:
        print("❌ Missing SUPABASE_URL or SUPABASE_SERVICE_ROLE_KEY")
        return
    
    # Read SQL from the file
    with open("supabase/migrations/20250101000000_initial_schema.sql", "r") as f:
        sql = f.read()
    
    # Execute via Supabase API
    try:
        # Using Supabase's SQL endpoint
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
            print("✅ Database setup successful!")
            
            # Verify tables
            verify_response = requests.get(
                f"{url}/rest/v1/chats?limit=1",
                headers={
                    "apikey": key,
                    "Authorization": f"Bearer {key}"
                }
            )
            
            if verify_response.status_code == 200:
                print("✅ Tables verified - ready to use!")
            else:
                print("⚠️ Tables created but verification failed")
                
        else:
            print(f"❌ Setup failed: {response.text}")
            
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    setup_database()
