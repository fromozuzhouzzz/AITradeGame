"""
手动启用SQLite WAL模式
"""
import sqlite3

def enable_wal_mode(db_path='trading_bot.db'):
    """启用WAL模式并优化数据库配置"""
    print(f"正在为 {db_path} 启用WAL模式...")
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # 启用WAL模式
    cursor.execute('PRAGMA journal_mode=WAL')
    result = cursor.fetchone()[0]
    print(f"✓ Journal模式设置为: {result}")

    # 设置同步模式为NORMAL（平衡性能和安全性）
    cursor.execute('PRAGMA synchronous=NORMAL')
    print(f"✓ 同步模式设置为: NORMAL")

    # 设置busy_timeout
    cursor.execute('PRAGMA busy_timeout=10000')
    print(f"✓ Busy超时设置为: 10000ms")

    # 设置cache_size（64MB）
    cursor.execute('PRAGMA cache_size=-64000')
    print(f"✓ 缓存大小设置为: 64MB")
    
    conn.close()
    
    # 验证设置
    print("\n验证配置...")
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    cursor.execute('PRAGMA journal_mode')
    journal_mode = cursor.fetchone()[0]
    
    cursor.execute('PRAGMA synchronous')
    sync_mode = cursor.fetchone()[0]
    
    cursor.execute('PRAGMA busy_timeout')
    timeout = cursor.fetchone()[0]
    
    conn.close()
    
    print(f"\n当前配置:")
    print(f"  Journal模式: {journal_mode}")
    print(f"  同步模式: {sync_mode}")
    print(f"  Busy超时: {timeout}ms")
    
    if journal_mode.upper() == 'WAL':
        print("\n✅ WAL模式已成功启用！")
        print("\nWAL模式的优势:")
        print("  ✓ 读操作不会阻塞写操作")
        print("  ✓ 写操作不会阻塞读操作")
        print("  ✓ 大幅提升并发性能")
        print("  ✓ 减少'database is locked'错误")
        return True
    else:
        print("\n⚠️ WAL模式启用失败")
        return False


if __name__ == '__main__':
    print("="*80)
    print("SQLite WAL模式启用工具")
    print("="*80)
    print()
    
    success = enable_wal_mode('trading_bot.db')
    
    if success:
        print("\n" + "="*80)
        print("下一步:")
        print("  1. 重启Flask应用 (python app.py)")
        print("  2. 运行测试脚本验证 (python test_db_optimization.py)")
        print("="*80)
    else:
        print("\n请检查数据库文件权限和路径")

