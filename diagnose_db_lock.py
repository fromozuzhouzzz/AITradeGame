"""
诊断SQLite数据库锁定问题
"""
import sqlite3
import time
import threading
from database import Database

def test_concurrent_reads():
    """测试并发读取操作"""
    print("\n" + "="*80)
    print("测试1: 并发读取操作")
    print("="*80)
    
    db = Database('trading_bot.db')
    
    def read_operation(thread_id):
        try:
            start = time.time()
            trades = db.get_trades(21, limit=50)
            conversations = db.get_conversations(21, limit=20)
            portfolio = db.get_portfolio(21)
            elapsed = time.time() - start
            print(f"[线程 {thread_id}] 读取成功，耗时: {elapsed:.3f}秒")
            return True
        except Exception as e:
            print(f"[线程 {thread_id}] 读取失败: {e}")
            return False
    
    # 启动10个并发读取线程
    threads = []
    for i in range(10):
        t = threading.Thread(target=read_operation, args=(i,))
        threads.append(t)
        t.start()
    
    for t in threads:
        t.join()
    
    print("✓ 并发读取测试完成")


def test_concurrent_writes():
    """测试并发写入操作"""
    print("\n" + "="*80)
    print("测试2: 并发写入操作")
    print("="*80)
    
    db = Database('trading_bot.db')
    
    def write_operation(thread_id):
        try:
            start = time.time()
            # 模拟交易执行中的写入操作
            db.add_trade(21, 'BTC', 'hold', 0, 90000, 1, 'long', 0)
            elapsed = time.time() - start
            print(f"[线程 {thread_id}] 写入成功，耗时: {elapsed:.3f}秒")
            return True
        except sqlite3.OperationalError as e:
            if "database is locked" in str(e):
                print(f"[线程 {thread_id}] ⚠️ 数据库锁定: {e}")
                return False
            raise
        except Exception as e:
            print(f"[线程 {thread_id}] 写入失败: {e}")
            return False
    
    # 启动5个并发写入线程
    threads = []
    for i in range(5):
        t = threading.Thread(target=write_operation, args=(i,))
        threads.append(t)
        t.start()
    
    for t in threads:
        t.join()
    
    print("✓ 并发写入测试完成")


def test_read_write_conflict():
    """测试读写冲突"""
    print("\n" + "="*80)
    print("测试3: 读写冲突场景（模拟实际问题）")
    print("="*80)
    
    db = Database('trading_bot.db')
    
    def long_write_operation():
        """模拟长时间写入操作（交易执行）"""
        try:
            conn = db.get_connection()
            cursor = conn.cursor()
            
            # 开始事务
            cursor.execute('BEGIN IMMEDIATE')
            print("[写入线程] 开始长时间写入事务...")
            
            # 模拟多个写入操作
            for i in range(5):
                cursor.execute('''
                    INSERT INTO trades (model_id, coin, signal, quantity, price, leverage, side, pnl)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ''', (21, 'BTC', 'hold', 0, 90000, 1, 'long', 0))
                time.sleep(0.5)  # 模拟处理时间
            
            conn.commit()
            conn.close()
            print("[写入线程] ✓ 写入事务完成")
        except Exception as e:
            print(f"[写入线程] ✗ 写入失败: {e}")
    
    def read_operation(thread_id):
        """模拟前端API读取操作"""
        time.sleep(0.2 * thread_id)  # 错开启动时间
        try:
            start = time.time()
            trades = db.get_trades(21, limit=50)
            elapsed = time.time() - start
            print(f"[读取线程 {thread_id}] ✓ 读取成功，耗时: {elapsed:.3f}秒")
        except sqlite3.OperationalError as e:
            if "database is locked" in str(e):
                print(f"[读取线程 {thread_id}] ⚠️ 数据库锁定: {e}")
            else:
                raise
        except Exception as e:
            print(f"[读取线程 {thread_id}] ✗ 读取失败: {e}")
    
    # 启动写入线程
    write_thread = threading.Thread(target=long_write_operation)
    write_thread.start()
    
    # 启动多个读取线程（模拟前端轮询）
    read_threads = []
    for i in range(3):
        t = threading.Thread(target=read_operation, args=(i,))
        read_threads.append(t)
        t.start()
    
    write_thread.join()
    for t in read_threads:
        t.join()
    
    print("✓ 读写冲突测试完成")


def check_database_mode():
    """检查数据库模式"""
    print("\n" + "="*80)
    print("数据库配置检查")
    print("="*80)
    
    conn = sqlite3.connect('trading_bot.db')
    cursor = conn.cursor()
    
    # 检查journal模式
    cursor.execute('PRAGMA journal_mode')
    journal_mode = cursor.fetchone()[0]
    print(f"Journal模式: {journal_mode}")
    
    # 检查超时设置
    cursor.execute('PRAGMA busy_timeout')
    timeout = cursor.fetchone()[0]
    print(f"Busy超时: {timeout}ms")
    
    # 检查同步模式
    cursor.execute('PRAGMA synchronous')
    sync_mode = cursor.fetchone()[0]
    print(f"同步模式: {sync_mode}")
    
    # 检查锁定模式
    cursor.execute('PRAGMA locking_mode')
    locking_mode = cursor.fetchone()[0]
    print(f"锁定模式: {locking_mode}")
    
    conn.close()
    
    print("\n推荐配置:")
    print("  - Journal模式: WAL (Write-Ahead Logging)")
    print("  - Busy超时: 5000ms 或更高")
    print("  - 同步模式: NORMAL (1)")
    print("  - 锁定模式: NORMAL")


def analyze_connection_pattern():
    """分析当前代码的连接模式"""
    print("\n" + "="*80)
    print("代码模式分析")
    print("="*80)
    
    print("\n当前问题:")
    print("  ✗ 每次操作都创建新连接 (get_connection())")
    print("  ✗ 没有连接池")
    print("  ✗ 没有重试机制")
    print("  ✗ 默认journal模式 (DELETE)")
    print("  ✗ 默认busy_timeout (0ms)")
    
    print("\n问题场景:")
    print("  1. Model 21执行交易决策 (长时间写入)")
    print("     - add_conversation() - 写入")
    print("     - update_position() - 写入")
    print("     - add_trade() - 写入 (多次)")
    print("     - record_account_value() - 写入")
    print("  2. 前端同时轮询API (并发读取)")
    print("     - GET /api/models/28/trades")
    print("     - GET /api/models/28/conversations")
    print("     - GET /api/models/28/portfolio")
    print("  3. 结果: 数据库锁定冲突")


if __name__ == '__main__':
    print("SQLite数据库锁定问题诊断工具")
    print("="*80)
    
    # 检查数据库配置
    check_database_mode()
    
    # 分析代码模式
    analyze_connection_pattern()
    
    # 运行并发测试
    test_concurrent_reads()
    test_concurrent_writes()
    test_read_write_conflict()
    
    print("\n" + "="*80)
    print("诊断完成")
    print("="*80)

