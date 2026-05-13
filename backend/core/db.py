import os
import yaml
import pymysql

def load_config():
    """加载 YAML 配置文件"""
    config_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../config.yaml"))
    if not os.path.exists(config_path):
        config_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../config.yaml"))
    with open(config_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)

class PredictionDB:
    def __init__(self):
        config = load_config()
        self.db_config = config.get('database', {
            "host": "127.0.0.1",
            "port": 3306,
            "user": "root",
            "password": "password",
            "db_name": "quant_sandbox"
        })
        self._init_db()

    def _get_connection(self, include_db=True):
        conn_params = {
            "host": self.db_config["host"],
            "port": self.db_config["port"],
            "user": self.db_config["user"],
            "password": self.db_config["password"],
            "charset": "utf8mb4",
            "cursorclass": pymysql.cursors.DictCursor
        }
        if include_db:
            conn_params["database"] = self.db_config["db_name"]
        return pymysql.connect(**conn_params)

    def _init_db(self):
        # 先不指定数据库连接，创建数据库
        conn = self._get_connection(include_db=False)
        try:
            with conn.cursor() as cursor:
                cursor.execute(f"CREATE DATABASE IF NOT EXISTS `{self.db_config['db_name']}` DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;")
            conn.commit()
        finally:
            conn.close()

        # 重新连接，这次指定数据库，创建表
        conn = self._get_connection(include_db=True)
        try:
            with conn.cursor() as cursor:
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS predictions (
                        ticker VARCHAR(50),
                        date VARCHAR(20),
                        prediction TEXT,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        PRIMARY KEY (ticker, date)
                    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
                """)
                # 用户表
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS users (
                        id INT AUTO_INCREMENT PRIMARY KEY,
                        username VARCHAR(50) UNIQUE NOT NULL,
                        password_hash VARCHAR(255) NOT NULL,
                        permissions JSON,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
                    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
                """)
                # 管理员表
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS admins (
                        id INT AUTO_INCREMENT PRIMARY KEY,
                        username VARCHAR(50) UNIQUE NOT NULL,
                        password_hash VARCHAR(255) NOT NULL,
                        role VARCHAR(50) DEFAULT 'superadmin',
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
                """)
                # 用户配置表
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS user_configs (
                        user_id INT PRIMARY KEY,
                        account_config JSON,
                        strategy_config JSON,
                        llm_config JSON,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                        FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
                    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
                """)
                # 用户股票池
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS user_stocks (
                        id INT AUTO_INCREMENT PRIMARY KEY,
                        user_id INT NOT NULL,
                        ticker VARCHAR(50) NOT NULL,
                        name VARCHAR(100),
                        purchase_amount DECIMAL(15, 2) DEFAULT 0.00,
                        profit_amount DECIMAL(15, 2) DEFAULT 0.00,
                        profit_rate DECIMAL(10, 4) DEFAULT 0.0000,
                        added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        UNIQUE KEY (user_id, ticker),
                        FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
                    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
                """)
                # 用户股票操作记录表
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
            conn.commit()
        finally:
            conn.close()

    def get_prediction(self, ticker: str, date: str) -> str:
        conn = self._get_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute(
                    "SELECT prediction FROM predictions WHERE ticker = %s AND date = %s",
                    (ticker, date)
                )
                result = cursor.fetchone()
                return result['prediction'] if result else None
        finally:
            conn.close()

    def save_prediction(self, ticker: str, date: str, prediction: str):
        conn = self._get_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute(
                    "INSERT INTO predictions (ticker, date, prediction) VALUES (%s, %s, %s) ON DUPLICATE KEY UPDATE prediction = VALUES(prediction)",
                    (ticker, date, prediction)
                )
            conn.commit()
        finally:
            conn.close()

    def get_predictions_by_ticker(self, ticker: str):
        conn = self._get_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute(
                    "SELECT date, prediction, created_at FROM predictions WHERE ticker = %s ORDER BY date DESC",
                    (ticker,)
                )
                return cursor.fetchall()
        finally:
            conn.close()

    def get_latest_prediction(self, ticker: str):
        conn = self._get_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute(
                    "SELECT date, prediction, created_at FROM predictions WHERE ticker = %s ORDER BY date DESC LIMIT 1",
                    (ticker,)
                )
                return cursor.fetchone()
        finally:
            conn.close()

class UserDB:
    def __init__(self):
        config = load_config()
        self.db_config = config.get('database', {
            "host": "127.0.0.1",
            "port": 3306,
            "user": "root",
            "password": "password",
            "db_name": "quant_sandbox"
        })

    def _get_connection(self):
        return pymysql.connect(
            host=self.db_config["host"],
            port=self.db_config["port"],
            user=self.db_config["user"],
            password=self.db_config["password"],
            database=self.db_config["db_name"],
            charset="utf8mb4",
            cursorclass=pymysql.cursors.DictCursor
        )

    # === Admin Methods ===
    def get_admin(self, username: str):
        conn = self._get_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute("SELECT * FROM admins WHERE username = %s", (username,))
                return cursor.fetchone()
        finally:
            conn.close()

    def create_admin(self, username: str, password_hash: str):
        conn = self._get_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute("INSERT IGNORE INTO admins (username, password_hash) VALUES (%s, %s)", (username, password_hash))
            conn.commit()
        finally:
            conn.close()

    # === User Methods ===
    def get_user(self, username: str):
        conn = self._get_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute("SELECT * FROM users WHERE username = %s", (username,))
                return cursor.fetchone()
        finally:
            conn.close()
            
    def get_all_users(self):
        conn = self._get_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute("SELECT id, username, permissions, created_at FROM users")
                return cursor.fetchall()
        finally:
            conn.close()

    def create_user(self, username: str, password_hash: str, permissions: str = None):
        conn = self._get_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute("INSERT INTO users (username, password_hash, permissions) VALUES (%s, %s, %s)", 
                              (username, password_hash, permissions))
                user_id = cursor.lastrowid
            conn.commit()
            return user_id
        finally:
            conn.close()
            
    def update_user_permissions(self, user_id: int, permissions: str):
        conn = self._get_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute("UPDATE users SET permissions = %s WHERE id = %s", (permissions, user_id))
            conn.commit()
        finally:
            conn.close()

    def delete_user(self, user_id: int):
        conn = self._get_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute("DELETE FROM users WHERE id = %s", (user_id,))
            conn.commit()
        finally:
            conn.close()

    # === User Configs Methods ===
    def get_user_config(self, user_id: int):
        conn = self._get_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute("SELECT * FROM user_configs WHERE user_id = %s", (user_id,))
                return cursor.fetchone()
        finally:
            conn.close()

    def save_user_config(self, user_id: int, account_config: str = None, strategy_config: str = None, llm_config: str = None):
        conn = self._get_connection()
        try:
            with conn.cursor() as cursor:
                # Upsert config
                cursor.execute("""
                    INSERT INTO user_configs (user_id, account_config, strategy_config, llm_config)
                    VALUES (%s, %s, %s, %s)
                    ON DUPLICATE KEY UPDATE 
                    account_config = COALESCE(VALUES(account_config), account_config),
                    strategy_config = COALESCE(VALUES(strategy_config), strategy_config),
                    llm_config = COALESCE(VALUES(llm_config), llm_config)
                """, (user_id, account_config, strategy_config, llm_config))
            conn.commit()
        finally:
            conn.close()

    # === User Stocks Methods ===
    def get_user_stocks(self, user_id: int):
        conn = self._get_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute("SELECT ticker, name, purchase_amount, profit_amount, profit_rate, added_at FROM user_stocks WHERE user_id = %s ORDER BY added_at DESC", (user_id,))
                return cursor.fetchall()
        finally:
            conn.close()

    def add_user_stock(self, user_id: int, ticker: str, name: str):
        conn = self._get_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute(
                    "INSERT IGNORE INTO user_stocks (user_id, ticker, name) VALUES (%s, %s, %s)",
                    (user_id, ticker, name)
                )
            conn.commit()
        finally:
            conn.close()

    def remove_user_stock(self, user_id: int, ticker: str):
        conn = self._get_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute("DELETE FROM user_stocks WHERE user_id = %s AND ticker = %s", (user_id, ticker))
            conn.commit()
        finally:
            conn.close()

    def update_user_stock_stats(self, user_id: int, ticker: str, purchase_amount: float, profit_amount: float, profit_rate: float):
        conn = self._get_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute("""
                    UPDATE user_stocks 
                    SET purchase_amount = %s, profit_amount = %s, profit_rate = %s
                    WHERE user_id = %s AND ticker = %s
                """, (purchase_amount, profit_amount, profit_rate, user_id, ticker))
            conn.commit()
        finally:
            conn.close()

    # === User Stock Operations Methods ===
    def add_stock_operation(self, user_id: int, ticker: str, operation_type: str, price: float, quantity: int, amount: float, operation_date: str):
        conn = self._get_connection()
        try:
            with conn.cursor() as cursor:
                # 插入操作记录
                cursor.execute("""
                    INSERT INTO user_stock_operations (user_id, ticker, operation_type, price, quantity, amount, operation_date)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                """, (user_id, ticker, operation_type, price, quantity, amount, operation_date))
                
                # 同步更新 user_stocks 表中的 purchase_amount
                if operation_type == 'BUY':
                    cursor.execute("""
                        UPDATE user_stocks 
                        SET purchase_amount = purchase_amount + %s 
                        WHERE user_id = %s AND ticker = %s
                    """, (amount, user_id, ticker))
                elif operation_type == 'SELL':
                    cursor.execute("""
                        UPDATE user_stocks 
                        SET purchase_amount = GREATEST(0, purchase_amount - %s) 
                        WHERE user_id = %s AND ticker = %s
                    """, (amount, user_id, ticker))
            conn.commit()
        finally:
            conn.close()

    def get_stock_operations(self, user_id: int, ticker: str = None):
        conn = self._get_connection()
        try:
            with conn.cursor() as cursor:
                if ticker:
                    cursor.execute("""
                        SELECT * FROM user_stock_operations 
                        WHERE user_id = %s AND ticker = %s 
                        ORDER BY operation_date DESC, created_at DESC
                    """, (user_id, ticker))
                else:
                    cursor.execute("""
                        SELECT * FROM user_stock_operations 
                        WHERE user_id = %s 
                        ORDER BY operation_date DESC, created_at DESC
                    """, (user_id,))
                return cursor.fetchall()
        finally:
            conn.close()

# 全局单例
prediction_db = PredictionDB()
user_db = UserDB()
