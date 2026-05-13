import os
import sys
import pymysql

# Add root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from backend.core.db import load_config

def migrate_db():
    config = load_config()
    db_config = config.get('database', {
        "host": "127.0.0.1",
        "port": 3306,
        "user": "root",
        "password": "password",
        "db_name": "quant_sandbox"
    })
    
    conn = pymysql.connect(
        host=db_config["host"],
        port=db_config["port"],
        user=db_config["user"],
        password=db_config["password"],
        database=db_config["db_name"],
        charset="utf8mb4",
        cursorclass=pymysql.cursors.DictCursor
    )
    
    try:
        with conn.cursor() as cursor:
            # 1. 尝试修改 user_stocks 表增加字段
            try:
                cursor.execute("""
                    ALTER TABLE user_stocks
                    ADD COLUMN purchase_amount DECIMAL(15, 2) DEFAULT 0.00 AFTER name,
                    ADD COLUMN profit_amount DECIMAL(15, 2) DEFAULT 0.00 AFTER purchase_amount,
                    ADD COLUMN profit_rate DECIMAL(10, 4) DEFAULT 0.0000 AFTER profit_amount;
                """)
                print("Successfully added columns to user_stocks.")
            except pymysql.err.OperationalError as e:
                # 1060: Duplicate column name
                if e.args[0] == 1060:
                    print("Columns already exist in user_stocks.")
                else:
                    print(f"Error altering user_stocks: {e}")
                    raise e
                    
            # 2. 检查 user_stock_operations 表是否创建
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS user_stock_operations (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    user_id INT NOT NULL,
                    ticker VARCHAR(50) NOT NULL,
                    operation_type ENUM('BUY', 'SELL') NOT NULL,
                    price DECIMAL(10, 3) NOT NULL,
                    quantity INT NOT NULL,
                    amount DECIMAL(15, 2) NOT NULL,
                    operation_date DATE NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
            """)
            print("Ensured user_stock_operations table exists.")
            
        conn.commit()
        print("Migration completed successfully.")
    finally:
        conn.close()

if __name__ == "__main__":
    migrate_db()
