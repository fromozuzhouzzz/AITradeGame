"""分析最近的交易资金使用情况"""
import sqlite3

conn = sqlite3.connect('trading_bot.db')
cursor = conn.cursor()

# 获取账户信息
cursor.execute('SELECT id, name, initial_capital FROM models')
models = cursor.fetchall()

print("=" * 80)
print("资金使用率分析")
print("=" * 80)

for model_id, model_name, initial_capital in models:
    print(f"\n模型: {model_name} (ID: {model_id})")
    print(f"初始资金: ${initial_capital:,.2f}")
    print("-" * 80)
    
    # 获取最近5笔交易
    cursor.execute('''
        SELECT coin, signal, quantity, price, leverage, timestamp 
        FROM trades 
        WHERE model_id = ?
        ORDER BY timestamp DESC 
        LIMIT 5
    ''', (model_id,))
    
    trades = cursor.fetchall()
    
    if not trades:
        print("  ❌ 没有交易记录")
        continue
    
    print("\n最近5笔交易:")
    print(f"{'时间':<20} {'币种':<8} {'信号':<18} {'数量':<12} {'价格':<10} {'杠杆':<6} {'保证金':<12} {'使用率':<8}")
    print("-" * 120)
    
    for coin, signal, quantity, price, leverage, timestamp in trades:
        if price and price > 0:
            margin = (quantity * price) / leverage
            usage_pct = (margin / initial_capital) * 100
            print(f"{timestamp:<20} {coin:<8} {signal:<18} {quantity:<12.2f} ${price:<9.2f} {leverage:<6}x ${margin:<11.2f} {usage_pct:<7.2f}%")
        else:
            print(f"{timestamp:<20} {coin:<8} {signal:<18} {quantity:<12.2f} {'N/A':<10} {leverage:<6}x {'N/A':<12} {'N/A':<8}")
    
    # 获取当前持仓
    cursor.execute('''
        SELECT coin, quantity, avg_price, leverage, side
        FROM portfolios
        WHERE model_id = ? AND quantity > 0
    ''', (model_id,))
    
    positions = cursor.fetchall()
    
    if positions:
        print("\n当前持仓:")
        print(f"{'币种':<8} {'方向':<6} {'数量':<12} {'均价':<10} {'杠杆':<6} {'保证金':<12} {'使用率':<8}")
        print("-" * 80)
        
        total_margin = 0
        for coin, quantity, avg_price, leverage, side in positions:
            margin = (quantity * avg_price) / leverage
            usage_pct = (margin / initial_capital) * 100
            total_margin += margin
            print(f"{coin:<8} {side:<6} {quantity:<12.2f} ${avg_price:<9.2f} {leverage:<6}x ${margin:<11.2f} {usage_pct:<7.2f}%")
        
        total_usage_pct = (total_margin / initial_capital) * 100
        print("-" * 80)
        print(f"{'总计':<8} {'':<6} {'':<12} {'':<10} {'':<6} ${total_margin:<11.2f} {total_usage_pct:<7.2f}%")
    else:
        print("\n  ❌ 当前无持仓")

conn.close()

print("\n" + "=" * 80)
print("分析完成")
print("=" * 80)

