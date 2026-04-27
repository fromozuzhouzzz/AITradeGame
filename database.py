"""
Database management module with connection pooling and WAL mode
"""
import sqlite3
import json
import time
import threading
from datetime import datetime
from typing import List, Dict, Optional
from contextlib import contextmanager

class Database:
    def __init__(self, db_path: str = 'trading_bot.db'):
        self.db_path = db_path
        self._local = threading.local()
        self._lock = threading.Lock()
        self._enable_wal_mode()

    def _enable_wal_mode(self):
        """Enable WAL mode for better concurrency"""
        try:
            conn = sqlite3.connect(self.db_path)
            conn.execute('PRAGMA journal_mode=WAL')
            conn.execute('PRAGMA synchronous=NORMAL')
            conn.execute('PRAGMA busy_timeout=10000')  # 10 seconds
            conn.execute('PRAGMA cache_size=-64000')  # 64MB cache
            conn.close()
            print(f"[DB] WAL mode enabled for {self.db_path}")
        except Exception as e:
            print(f"[DB] Warning: Could not enable WAL mode: {e}")

    def get_connection(self):
        """Get database connection with optimized settings"""
        conn = sqlite3.connect(self.db_path, timeout=10.0)
        conn.row_factory = sqlite3.Row
        # Set pragmas for this connection
        conn.execute('PRAGMA busy_timeout=10000')
        return conn

    @contextmanager
    def get_connection_context(self):
        """Context manager for database connections with automatic cleanup"""
        conn = self.get_connection()
        try:
            yield conn
        finally:
            conn.close()

    def execute_with_retry(self, operation, max_retries=3, retry_delay=0.1):
        """Execute database operation with retry on lock errors"""
        for attempt in range(max_retries):
            try:
                return operation()
            except sqlite3.OperationalError as e:
                if "database is locked" in str(e) and attempt < max_retries - 1:
                    time.sleep(retry_delay * (attempt + 1))
                    continue
                raise
        raise sqlite3.OperationalError("Max retries exceeded")
    
    def init_db(self):
        """Initialize database tables"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        # Models table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS models (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                api_key TEXT NOT NULL,
                api_url TEXT NOT NULL,
                model_name TEXT NOT NULL,
                initial_capital REAL DEFAULT 10000,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Portfolios table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS portfolios (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                model_id INTEGER NOT NULL,
                coin TEXT NOT NULL,
                quantity REAL NOT NULL,
                avg_price REAL NOT NULL,
                leverage INTEGER DEFAULT 1,
                side TEXT DEFAULT 'long',
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (model_id) REFERENCES models(id),
                UNIQUE(model_id, coin, side)
            )
        ''')
        
        # Trades table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS trades (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                model_id INTEGER NOT NULL,
                coin TEXT NOT NULL,
                signal TEXT NOT NULL,
                quantity REAL NOT NULL,
                price REAL NOT NULL,
                leverage INTEGER DEFAULT 1,
                side TEXT DEFAULT 'long',
                pnl REAL DEFAULT 0,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (model_id) REFERENCES models(id)
            )
        ''')
        
        # Conversations table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS conversations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                model_id INTEGER NOT NULL,
                user_prompt TEXT NOT NULL,
                ai_response TEXT NOT NULL,
                cot_trace TEXT,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (model_id) REFERENCES models(id)
            )
        ''')
        
        # Account values history table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS account_values (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                model_id INTEGER NOT NULL,
                total_value REAL NOT NULL,
                cash REAL NOT NULL,
                positions_value REAL NOT NULL,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (model_id) REFERENCES models(id)
            )
        ''')
        
        conn.commit()
        conn.close()
    
    # ============ Model Management ============
    
    def add_model(self, name: str, api_key: str, api_url: str,
                   model_name: str, initial_capital: float = 10000) -> int:
        """Add new trading model with retry"""
        def operation():
            with self.get_connection_context() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    INSERT INTO models (name, api_key, api_url, model_name, initial_capital)
                    VALUES (?, ?, ?, ?, ?)
                ''', (name, api_key, api_url, model_name, initial_capital))
                model_id = cursor.lastrowid
                conn.commit()
                return model_id
        return self.execute_with_retry(operation)

    def get_model(self, model_id: int) -> Optional[Dict]:
        """Get model information with retry"""
        def operation():
            with self.get_connection_context() as conn:
                cursor = conn.cursor()
                cursor.execute('SELECT * FROM models WHERE id = ?', (model_id,))
                row = cursor.fetchone()
                return dict(row) if row else None
        return self.execute_with_retry(operation)

    def get_all_models(self) -> List[Dict]:
        """Get all trading models with retry"""
        def operation():
            with self.get_connection_context() as conn:
                cursor = conn.cursor()
                cursor.execute('SELECT * FROM models ORDER BY created_at DESC')
                rows = cursor.fetchall()
                return [dict(row) for row in rows]
        return self.execute_with_retry(operation)
    
    def update_model(self, model_id: int, name: str = None, api_key: str = None,
                     api_url: str = None, model_name: str = None) -> bool:
        """Update model configuration with retry"""
        def operation():
            with self.get_connection_context() as conn:
                cursor = conn.cursor()

                # Build update query dynamically based on provided parameters
                updates = []
                params = []

                if name is not None:
                    updates.append('name = ?')
                    params.append(name)
                if api_key is not None:
                    updates.append('api_key = ?')
                    params.append(api_key)
                if api_url is not None:
                    updates.append('api_url = ?')
                    params.append(api_url)
                if model_name is not None:
                    updates.append('model_name = ?')
                    params.append(model_name)

                if not updates:
                    return False

                params.append(model_id)
                query = f"UPDATE models SET {', '.join(updates)} WHERE id = ?"
                cursor.execute(query, params)
                conn.commit()
                return True

        return self.execute_with_retry(operation)

    def delete_model(self, model_id: int):
        """Delete model and related data with retry"""
        def operation():
            with self.get_connection_context() as conn:
                cursor = conn.cursor()
                cursor.execute('DELETE FROM models WHERE id = ?', (model_id,))
                cursor.execute('DELETE FROM portfolios WHERE model_id = ?', (model_id,))
                cursor.execute('DELETE FROM trades WHERE model_id = ?', (model_id,))
                cursor.execute('DELETE FROM conversations WHERE model_id = ?', (model_id,))
                cursor.execute('DELETE FROM account_values WHERE model_id = ?', (model_id,))
                conn.commit()
        self.execute_with_retry(operation)
    
    # ============ Portfolio Management ============
    
    def update_position(self, model_id: int, coin: str, quantity: float,
                       avg_price: float, leverage: int = 1, side: str = 'long'):
        """
        Update position with retry - supports both opening new positions and adding to existing ones

        Args:
            quantity: If positive, adds to position. If negative, reduces position.
            avg_price: New entry price (for new positions or additions)
        """
        def operation():
            with self.get_connection_context() as conn:
                cursor = conn.cursor()

                # Check if position exists
                cursor.execute('''
                    SELECT quantity, avg_price FROM portfolios
                    WHERE model_id = ? AND coin = ? AND side = ?
                ''', (model_id, coin, side))
                existing = cursor.fetchone()

                if existing:
                    # Position exists - update quantity and average price
                    old_quantity = existing['quantity']
                    old_avg_price = existing['avg_price']

                    if quantity > 0:
                        # Adding to position - calculate new average price
                        new_quantity = old_quantity + quantity
                        new_avg_price = (old_quantity * old_avg_price + quantity * avg_price) / new_quantity
                    else:
                        # Reducing position - keep old average price
                        new_quantity = old_quantity + quantity  # quantity is negative
                        new_avg_price = old_avg_price

                        # If quantity becomes zero or negative, delete the position
                        if new_quantity <= 0:
                            cursor.execute('''
                                DELETE FROM portfolios WHERE model_id = ? AND coin = ? AND side = ?
                            ''', (model_id, coin, side))
                            conn.commit()
                            return

                    # Update existing position
                    cursor.execute('''
                        UPDATE portfolios
                        SET quantity = ?, avg_price = ?, leverage = ?, updated_at = CURRENT_TIMESTAMP
                        WHERE model_id = ? AND coin = ? AND side = ?
                    ''', (new_quantity, new_avg_price, leverage, model_id, coin, side))
                else:
                    # New position - insert
                    if quantity <= 0:
                        # Cannot create a new position with negative quantity
                        return

                    cursor.execute('''
                        INSERT INTO portfolios (model_id, coin, quantity, avg_price, leverage, side, updated_at)
                        VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                    ''', (model_id, coin, quantity, avg_price, leverage, side))

                conn.commit()

        self.execute_with_retry(operation)
    
    def get_portfolio(self, model_id: int, current_prices: Dict = None) -> Dict:
        """Get portfolio with positions and P&L with retry

        Args:
            model_id: Model ID
            current_prices: Current market prices {coin: price} for unrealized P&L calculation
        """
        def operation():
            with self.get_connection_context() as conn:
                cursor = conn.cursor()

                # Get positions
                cursor.execute('''
                    SELECT * FROM portfolios WHERE model_id = ? AND quantity > 0
                ''', (model_id,))
                positions = [dict(row) for row in cursor.fetchall()]

                # Get initial capital
                cursor.execute('SELECT initial_capital FROM models WHERE id = ?', (model_id,))
                initial_capital = cursor.fetchone()['initial_capital']

                # Calculate realized P&L (sum of all trade P&L)
                cursor.execute('''
                    SELECT COALESCE(SUM(pnl), 0) as total_pnl FROM trades WHERE model_id = ?
                ''', (model_id,))
                realized_pnl = cursor.fetchone()['total_pnl']

                # Calculate margin used
                margin_used = sum([p['quantity'] * p['avg_price'] / p['leverage'] for p in positions])

                # Calculate unrealized P&L (if prices provided)
                unrealized_pnl = 0
                if current_prices:
                    for pos in positions:
                        coin = pos['coin']
                        if coin in current_prices:
                            current_price = current_prices[coin]
                            entry_price = pos['avg_price']
                            quantity = pos['quantity']

                            # Add current price to position
                            pos['current_price'] = current_price

                            # Calculate position P&L
                            if pos['side'] == 'long':
                                pos_pnl = (current_price - entry_price) * quantity
                            else:  # short
                                pos_pnl = (entry_price - current_price) * quantity

                            pos['pnl'] = pos_pnl
                            unrealized_pnl += pos_pnl
                        else:
                            pos['current_price'] = None
                            pos['pnl'] = 0
                else:
                    for pos in positions:
                        pos['current_price'] = None
                        pos['pnl'] = 0

                # FIXED: Cash = initial capital + realized P&L + unrealized P&L - margin used
                # 可用现金 = 初始资金 + 已实现盈亏 + 未实现盈亏 - 已占用保证金
                #
                # 解释：
                # 1. 初始资金：账户起始金额
                # 2. 已实现盈亏：已平仓交易的累计盈亏
                # 3. 未实现盈亏：当前持仓的浮动盈亏（影响账户净值和可用资金）
                # 4. 已占用保证金：持仓占用的保证金 = Σ(持仓价值 / 杠杆倍数)
                #
                # 示例（账户10万，BTC持仓）：
                # - 初始资金：100,000
                # - 已实现盈亏：+5,000（之前平仓赚了5000）
                # - 持仓：1 BTC @ 50,000（开仓价），当前价51,000，杠杆10x
                #   * 持仓价值：1 × 50,000 = 50,000
                #   * 占用保证金：50,000 / 10 = 5,000
                #   * 未实现盈亏：(51,000 - 50,000) × 1 = +1,000
                # - 可用现金 = 100,000 + 5,000 + 1,000 - 5,000 = 101,000
                cash = initial_capital + realized_pnl + unrealized_pnl - margin_used

                # Position value = quantity * entry price (not margin!)
                positions_value = sum([p['quantity'] * p['avg_price'] for p in positions])

                # Total account value = initial capital + realized P&L + unrealized P&L
                total_value = initial_capital + realized_pnl + unrealized_pnl

                return {
                    'model_id': model_id,
                    'cash': cash,
                    'positions': positions,
                    'positions_value': positions_value,
                    'margin_used': margin_used,
                    'total_value': total_value,
                    'realized_pnl': realized_pnl,
                    'unrealized_pnl': unrealized_pnl
                }

        return self.execute_with_retry(operation)
    
    def close_position(self, model_id: int, coin: str, side: str = 'long'):
        """Close position with retry"""
        def operation():
            with self.get_connection_context() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    DELETE FROM portfolios WHERE model_id = ? AND coin = ? AND side = ?
                ''', (model_id, coin, side))
                conn.commit()
        self.execute_with_retry(operation)
    
    # ============ Trade Records ============

    def add_trade(self, model_id: int, coin: str, signal: str, quantity: float,
                  price: float, leverage: int = 1, side: str = 'long', pnl: float = 0):
        """Add trade record with retry"""
        def operation():
            with self.get_connection_context() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    INSERT INTO trades (model_id, coin, signal, quantity, price, leverage, side, pnl)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ''', (model_id, coin, signal, quantity, price, leverage, side, pnl))
                conn.commit()
        self.execute_with_retry(operation)

    def get_trades(self, model_id: int, limit: int = 50) -> List[Dict]:
        """Get trade history with retry"""
        def operation():
            with self.get_connection_context() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT * FROM trades WHERE model_id = ?
                    ORDER BY timestamp DESC LIMIT ?
                ''', (model_id, limit))
                rows = cursor.fetchall()
                return [dict(row) for row in rows]
        return self.execute_with_retry(operation)

    # ============ Conversation History ============

    def add_conversation(self, model_id: int, user_prompt: str,
                        ai_response: str, cot_trace: str = ''):
        """Add conversation record with retry"""
        def operation():
            with self.get_connection_context() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    INSERT INTO conversations (model_id, user_prompt, ai_response, cot_trace)
                    VALUES (?, ?, ?, ?)
                ''', (model_id, user_prompt, ai_response, cot_trace))
                conn.commit()
        self.execute_with_retry(operation)

    def get_conversations(self, model_id: int, limit: int = 20) -> List[Dict]:
        """Get conversation history with retry"""
        def operation():
            with self.get_connection_context() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT * FROM conversations WHERE model_id = ?
                    ORDER BY timestamp DESC LIMIT ?
                ''', (model_id, limit))
                rows = cursor.fetchall()
                return [dict(row) for row in rows]
        return self.execute_with_retry(operation)
    
    # ============ Account Value History ============

    def record_account_value(self, model_id: int, total_value: float,
                            cash: float, positions_value: float):
        """Record account value snapshot with retry"""
        def operation():
            with self.get_connection_context() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    INSERT INTO account_values (model_id, total_value, cash, positions_value)
                    VALUES (?, ?, ?, ?)
                ''', (model_id, total_value, cash, positions_value))
                conn.commit()
        self.execute_with_retry(operation)

    def get_account_value_history(self, model_id: int, limit: int = 100) -> List[Dict]:
        """Get account value history with retry"""
        def operation():
            with self.get_connection_context() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT * FROM account_values WHERE model_id = ?
                    ORDER BY timestamp DESC LIMIT ?
                ''', (model_id, limit))
                rows = cursor.fetchall()
                return [dict(row) for row in rows]
        return self.execute_with_retry(operation)

    def get_account_value_history_by_timeframe(self, model_id: int, timeframe: str = '1m', limit: int = 100) -> List[Dict]:
        """
        Get account value history aggregated by timeframe

        Args:
            model_id: Model ID
            timeframe: Time period ('1m', '3m', '5m', '15m', '30m', '1h', '4h', '1d', '1w', '1M')
            limit: Maximum number of data points to return

        Returns:
            List of aggregated account value records
        """
        conn = self.get_connection()
        cursor = conn.cursor()

        # 定义时间聚合SQL
        if timeframe in ['1m', '3m', '5m', '15m', '30m']:
            # 分钟级：直接查询，但根据timeframe过滤
            minutes = int(timeframe[:-1])
            cursor.execute('''
                SELECT * FROM account_values
                WHERE model_id = ?
                AND (strftime('%s', timestamp) / 60) % ? = 0
                ORDER BY timestamp DESC
                LIMIT ?
            ''', (model_id, minutes, limit))
        elif timeframe == '1h':
            # 小时级：每小时取最后一条记录
            cursor.execute('''
                SELECT id, model_id, total_value, cash, positions_value,
                       MAX(timestamp) as timestamp
                FROM account_values
                WHERE model_id = ?
                GROUP BY strftime('%Y-%m-%d %H', timestamp)
                ORDER BY timestamp DESC
                LIMIT ?
            ''', (model_id, limit))
        elif timeframe == '4h':
            # 4小时级：每4小时取最后一条记录
            cursor.execute('''
                SELECT id, model_id, total_value, cash, positions_value,
                       MAX(timestamp) as timestamp
                FROM account_values
                WHERE model_id = ?
                GROUP BY strftime('%Y-%m-%d', timestamp),
                         CAST(strftime('%H', timestamp) AS INTEGER) / 4
                ORDER BY timestamp DESC
                LIMIT ?
            ''', (model_id, limit))
        elif timeframe == '1d':
            # 日级：每天取最后一条记录
            cursor.execute('''
                SELECT id, model_id, total_value, cash, positions_value,
                       MAX(timestamp) as timestamp
                FROM account_values
                WHERE model_id = ?
                GROUP BY strftime('%Y-%m-%d', timestamp)
                ORDER BY timestamp DESC
                LIMIT ?
            ''', (model_id, limit))
        elif timeframe == '1w':
            # 周级：每周取最后一条记录
            cursor.execute('''
                SELECT id, model_id, total_value, cash, positions_value,
                       MAX(timestamp) as timestamp
                FROM account_values
                WHERE model_id = ?
                GROUP BY strftime('%Y-%W', timestamp)
                ORDER BY timestamp DESC
                LIMIT ?
            ''', (model_id, limit))
        elif timeframe == '1M':
            # 月级：每月取最后一条记录
            cursor.execute('''
                SELECT id, model_id, total_value, cash, positions_value,
                       MAX(timestamp) as timestamp
                FROM account_values
                WHERE model_id = ?
                GROUP BY strftime('%Y-%m', timestamp)
                ORDER BY timestamp DESC
                LIMIT ?
            ''', (model_id, limit))
        else:
            # 默认：返回所有记录
            cursor.execute('''
                SELECT * FROM account_values WHERE model_id = ?
                ORDER BY timestamp DESC LIMIT ?
            ''', (model_id, limit))

        rows = cursor.fetchall()
        conn.close()
        return [dict(row) for row in rows]

