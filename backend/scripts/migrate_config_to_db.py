import os
import sys
import json

# Add root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from backend.core.db import prediction_db, user_db, load_config
from backend.main import get_stock_names_from_config

def migrate():
    print("Initializing database tables...")
    prediction_db._init_db()
    
    config = load_config()
    
    print("Creating default admin and user...")
    # Create default admin
    user_db.create_admin("admin", "admin123")  # Simple password for demonstration, should be hashed in prod
    
    # Create default user
    user = user_db.get_user("default_user")
    if not user:
        user_id = user_db.create_user("default_user", "password123", json.dumps({"can_trade": True}))
    else:
        user_id = user["id"]
        
    print(f"Default user ID: {user_id}")
    
    # Migrate configs
    account_config = json.dumps(config.get("account", {}))
    strategy_config = json.dumps(config.get("strategy", {}))
    llm_config = json.dumps(config.get("llm", {}))
    
    print("Migrating user configs...")
    user_db.save_user_config(user_id, account_config, strategy_config, llm_config)
    
    # Migrate stock pool
    pool = config.get("stock_pool", [])
    names_map = get_stock_names_from_config()
    
    print("Migrating stock pool...")
    for ticker in pool:
        name = names_map.get(ticker, "")
        user_db.add_user_stock(user_id, ticker, name)
        
    print("Migration completed successfully.")

if __name__ == "__main__":
    migrate()
