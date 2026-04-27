"""
验证可用现金计算修复的脚本

用法：
    python verify_cash_fix.py

功能：
    1. 连接到数据库
    2. 获取所有模型的投资组合
    3. 验证可用现金计算是否正确
    4. 显示详细的计算过程
"""

import sys
from database import Database
from market_data import MarketDataFetcher

def verify_cash_calculation():
    """验证可用现金计算是否正确"""
    
    print("=" * 80)
    print("可用现金计算验证工具")
    print("=" * 80)
    
    # 初始化数据库和市场数据获取器
    db = Database()
    market_fetcher = MarketDataFetcher()
    
    # 获取所有模型
    models = db.get_all_models()
    
    if not models:
        print("\n❌ 没有找到任何模型")
        return
    
    print(f"\n找到 {len(models)} 个模型\n")
    
    # 获取当前价格
    coins = ['BTC', 'ETH', 'SOL', 'BNB', 'XRP', 'DOGE']
    prices_data = market_fetcher.get_current_prices(coins)
    current_prices = {coin: prices_data[coin]['price'] for coin in prices_data}
    
    print("当前市场价格：")
    for coin, price in current_prices.items():
        print(f"  {coin}: ${price:,.2f}")
    print()
    
    # 验证每个模型
    for model in models:
        model_id = model['id']
        model_name = model['name']
        initial_capital = model['initial_capital']
        
        print("=" * 80)
        print(f"模型 #{model_id}: {model_name}")
        print("=" * 80)
        
        # 获取投资组合
        portfolio = db.get_portfolio(model_id, current_prices)
        
        # 提取数据
        cash = portfolio['cash']
        positions = portfolio['positions']
        margin_used = portfolio['margin_used']
        total_value = portfolio['total_value']
        realized_pnl = portfolio['realized_pnl']
        unrealized_pnl = portfolio['unrealized_pnl']
        
        # 显示账户信息
        print(f"\n【账户信息】")
        print(f"初始资金: ${initial_capital:,.2f}")
        print(f"已实现盈亏: ${realized_pnl:,.2f}")
        print(f"未实现盈亏: ${unrealized_pnl:,.2f}")
        print(f"账户总值: ${total_value:,.2f}")
        print(f"可用现金: ${cash:,.2f}")
        print(f"已占用保证金: ${margin_used:,.2f}")
        
        # 显示持仓信息
        if positions:
            print(f"\n【持仓详情】（共 {len(positions)} 个）")
            print("-" * 80)
            
            total_position_value = 0
            total_margin = 0
            total_unrealized = 0
            
            for i, pos in enumerate(positions, 1):
                coin = pos['coin']
                quantity = pos['quantity']
                entry_price = pos['avg_price']
                current_price = pos.get('current_price', entry_price)
                leverage = pos['leverage']
                side = pos['side']
                pos_pnl = pos.get('pnl', 0)
                
                position_value = quantity * entry_price
                position_margin = position_value / leverage
                
                total_position_value += position_value
                total_margin += position_margin
                total_unrealized += pos_pnl
                
                print(f"\n持仓 {i}: {coin} ({side.upper()})")
                print(f"  数量: {quantity:.4f}")
                print(f"  开仓价: ${entry_price:,.2f}")
                print(f"  当前价: ${current_price:,.2f}")
                print(f"  杠杆: {leverage}x")
                print(f"  持仓价值: ${position_value:,.2f}")
                print(f"  占用保证金: ${position_margin:,.2f}")
                print(f"  未实现盈亏: ${pos_pnl:,.2f}")
            
            print("\n" + "-" * 80)
            print(f"持仓汇总:")
            print(f"  总持仓价值: ${total_position_value:,.2f}")
            print(f"  总占用保证金: ${total_margin:,.2f}")
            print(f"  总未实现盈亏: ${total_unrealized:,.2f}")
        else:
            print(f"\n【持仓详情】无持仓")
        
        # 验证计算
        print(f"\n【计算验证】")
        print("-" * 80)
        
        # 手动计算可用现金
        calculated_cash = initial_capital + realized_pnl + unrealized_pnl - margin_used
        calculated_total = initial_capital + realized_pnl + unrealized_pnl
        
        print(f"公式: 可用现金 = 初始资金 + 已实现盈亏 + 未实现盈亏 - 已占用保证金")
        print(f"计算: ${initial_capital:,.2f} + ${realized_pnl:,.2f} + ${unrealized_pnl:,.2f} - ${margin_used:,.2f}")
        print(f"     = ${calculated_cash:,.2f}")
        print(f"\n数据库返回: ${cash:,.2f}")
        
        # 检查是否一致
        if abs(calculated_cash - cash) < 0.01:  # 允许0.01的浮点误差
            print(f"✅ 验证通过！计算结果一致")
        else:
            print(f"❌ 验证失败！计算结果不一致")
            print(f"   差异: ${abs(calculated_cash - cash):,.2f}")
        
        # 验证账户总值
        print(f"\n公式: 账户总值 = 初始资金 + 已实现盈亏 + 未实现盈亏")
        print(f"计算: ${initial_capital:,.2f} + ${realized_pnl:,.2f} + ${unrealized_pnl:,.2f}")
        print(f"     = ${calculated_total:,.2f}")
        print(f"\n数据库返回: ${total_value:,.2f}")
        
        if abs(calculated_total - total_value) < 0.01:
            print(f"✅ 验证通过！账户总值计算正确")
        else:
            print(f"❌ 验证失败！账户总值计算不正确")
            print(f"   差异: ${abs(calculated_total - total_value):,.2f}")
        
        # 验证关系：账户总值 = 可用现金 + 已占用保证金
        relationship_check = cash + margin_used
        print(f"\n关系验证: 账户总值 = 可用现金 + 已占用保证金")
        print(f"计算: ${cash:,.2f} + ${margin_used:,.2f} = ${relationship_check:,.2f}")
        print(f"账户总值: ${total_value:,.2f}")
        
        if abs(relationship_check - total_value) < 0.01:
            print(f"✅ 验证通过！关系正确")
        else:
            print(f"❌ 验证失败！关系不正确")
            print(f"   差异: ${abs(relationship_check - total_value):,.2f}")
        
        print()
    
    print("=" * 80)
    print("验证完成！")
    print("=" * 80)

if __name__ == "__main__":
    try:
        verify_cash_calculation()
    except Exception as e:
        print(f"\n❌ 验证过程中发生错误: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

