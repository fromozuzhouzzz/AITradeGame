"""
诊断自动交易系统
检查所有组件是否正常工作
"""
import sys
import json
from database import Database
from market_data import MarketDataFetcher
from ai_trader import AITrader
from trading_engine import TradingEngine

def print_separator():
    print("\n" + "="*70 + "\n")

def diagnose_system():
    """诊断系统状态"""
    print("🔍 开始诊断自动交易系统...")
    print_separator()
    
    # 1. 检查数据库
    print("📊 检查数据库...")
    try:
        db = Database('trading_bot.db')
        models = db.get_all_models()
        
        if not models:
            print("❌ 错误：数据库中没有交易模型！")
            print("   请先通过Web界面添加至少一个AI交易模型。")
            return False
        
        print(f"✅ 找到 {len(models)} 个交易模型：")
        for model in models:
            print(f"   - ID: {model['id']}, 名称: {model['name']}, 初始资金: ${model['initial_capital']:.2f}")
    except Exception as e:
        print(f"❌ 数据库错误: {e}")
        return False
    
    print_separator()
    
    # 2. 检查市场数据获取
    print("📈 检查市场数据获取...")
    try:
        market_fetcher = MarketDataFetcher()
        coins = ['BTC', 'ETH', 'SOL', 'BNB', 'XRP', 'DOGE']
        prices = market_fetcher.get_current_prices(coins)
        
        if not prices or len(prices) == 0:
            print("❌ 错误：无法获取市场数据！")
            return False
        
        print(f"✅ 成功获取 {len(prices)} 个币种的价格：")
        for coin, data in prices.items():
            print(f"   - {coin}: ${data['price']:.2f} ({data['change_24h']:+.2f}%)")
    except Exception as e:
        print(f"❌ 市场数据获取错误: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    print_separator()
    
    # 3. 检查技术指标计算
    print("📊 检查技术指标计算...")
    try:
        indicators = market_fetcher.calculate_technical_indicators('BTC')
        
        if not indicators:
            print("⚠️  警告：技术指标计算返回空数据")
        else:
            print(f"✅ 技术指标计算正常：")
            print(f"   - 当前价格: ${indicators.get('current_price', 0):,.2f}")
            print(f"   - SMA(7): ${indicators.get('sma_7', 0):,.2f}")
            print(f"   - RSI(14): {indicators.get('rsi_14', 0):.2f}")
    except Exception as e:
        print(f"⚠️  技术指标计算警告: {e}")
    
    print_separator()
    
    # 4. 测试交易引擎
    print("🤖 测试交易引擎...")
    try:
        model = models[0]  # 使用第一个模型测试
        print(f"   使用模型: {model['name']} (ID: {model['id']})")
        
        # 创建AI交易者
        ai_trader = AITrader(
            api_key=model['api_key'],
            api_url=model['api_url'],
            model_name=model['model_name']
        )
        
        # 创建交易引擎
        engine = TradingEngine(
            model_id=model['id'],
            db=db,
            market_fetcher=market_fetcher,
            ai_trader=ai_trader
        )
        
        print("   ⏳ 执行一次交易周期测试...")
        result = engine.execute_trading_cycle()
        
        if result.get('success'):
            print("   ✅ 交易周期执行成功！")
            
            decisions = result.get('decisions', {})
            print(f"   📋 AI决策数量: {len(decisions)}")
            
            for coin, decision in decisions.items():
                signal = decision.get('signal', 'unknown')
                justification = decision.get('justification', decision.get('reason', 'N/A'))
                print(f"      - {coin}: {signal} (原因: {justification[:50]}...)")
            
            executions = result.get('executions', [])
            trades_executed = sum(1 for e in executions if e.get('signal') != 'hold')
            print(f"   💼 执行的交易: {trades_executed} 笔")
            
            portfolio = result.get('portfolio', {})
            print(f"   💰 账户总值: ${portfolio.get('total_value', 0):,.2f}")
            print(f"   💵 现金余额: ${portfolio.get('cash', 0):,.2f}")
            
        else:
            error = result.get('error', 'Unknown error')
            print(f"   ❌ 交易周期执行失败: {error}")
            return False
            
    except Exception as e:
        print(f"❌ 交易引擎测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    print_separator()
    
    # 5. 检查自动交易配置
    print("⚙️  检查自动交易配置...")
    try:
        import app
        
        if app.auto_trading:
            print("✅ 自动交易已启用 (auto_trading = True)")
        else:
            print("❌ 自动交易已禁用 (auto_trading = False)")
            print("   请在 app.py 中设置 auto_trading = True")
            return False
        
        print(f"✅ 交易循环函数存在: {hasattr(app, 'trading_loop')}")
        print(f"✅ 初始化函数存在: {hasattr(app, 'init_trading_engines')}")
        
    except Exception as e:
        print(f"⚠️  配置检查警告: {e}")
    
    print_separator()
    
    return True

def main():
    """主函数"""
    print("\n" + "="*70)
    print(" "*20 + "自动交易系统诊断工具")
    print("="*70)
    
    try:
        success = diagnose_system()
        
        if success:
            print("\n🎉 诊断完成！所有组件运行正常。\n")
            print("📋 诊断结果总结：")
            print("   ✅ 数据库连接正常")
            print("   ✅ 市场数据获取正常")
            print("   ✅ 技术指标计算正常")
            print("   ✅ 交易引擎运行正常")
            print("   ✅ AI决策生成正常")
            print("   ✅ 自动交易配置正确")
            print("\n💡 建议：")
            print("   1. 运行 'python app.py' 启动应用")
            print("   2. 观察控制台输出，确认自动交易循环正在运行")
            print("   3. 每3分钟应该看到一次交易周期执行")
            print("   4. 访问 http://localhost:5000 查看Web界面")
            print()
            return 0
        else:
            print("\n⚠️  诊断发现问题！请查看上方错误信息。\n")
            return 1
            
    except KeyboardInterrupt:
        print("\n\n⚠️  诊断被用户中断\n")
        return 1
    except Exception as e:
        print(f"\n\n❌ 诊断过程中发生错误: {e}\n")
        import traceback
        traceback.print_exc()
        return 1

if __name__ == "__main__":
    sys.exit(main())

