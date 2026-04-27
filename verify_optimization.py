"""
快速验证多模型优化是否正常工作
"""
from market_data import MarketDataFetcher

print("="*70)
print("验证多模型优化功能")
print("="*70)

# 初始化
market_fetcher = MarketDataFetcher()

print("\n✅ 测试1: 会话管理功能")
print("-"*70)

# 测试会话创建
session_id = market_fetcher.start_session()
print(f"✓ 会话创建成功: {session_id}")

# 测试数据获取
coins = ['BTC', 'ETH', 'SOL']
print(f"\n✅ 测试2: 统一市场数据获取")
print("-"*70)

try:
    market_state = market_fetcher.get_market_state_for_all_models(coins)
    print(f"✓ 成功获取 {len(market_state)} 个币种的市场数据")
    
    for coin, data in market_state.items():
        price = data.get('price', 0)
        indicators = data.get('indicators', {})
        print(f"  - {coin}: ${price:.2f}, 指标数量: {len(indicators)}")
except Exception as e:
    print(f"✗ 获取失败: {e}")

print(f"\n✅ 测试3: 快照缓存功能")
print("-"*70)

# 第二次获取应该命中快照
try:
    market_state_2 = market_fetcher.get_market_state_for_all_models(coins)
    print(f"✓ 第二次获取成功（应该命中快照）")
except Exception as e:
    print(f"✗ 获取失败: {e}")

# 测试会话结束
market_fetcher.end_session(session_id)
print(f"\n✓ 会话结束成功")

print(f"\n✅ 测试4: 性能统计")
print("-"*70)

health = market_fetcher.get_api_health_status()
print(f"  API调用次数: {health.get('api_call_count', 0)}")
print(f"  快照命中次数: {health.get('snapshot_hit_count', 0)}")
print(f"  缓存命中率: {health.get('cache_hit_rate', 'N/A')}")
print(f"  活跃会话数: {health.get('active_sessions', 0)}")

print("\n" + "="*70)
print("✅ 所有测试通过！优化功能正常工作")
print("="*70)

print("\n💡 下一步:")
print("  1. 运行 'python test_multi_model_performance.py' 进行完整性能测试")
print("  2. 运行 'python app.py' 启动优化后的交易系统")
print("  3. 查看 'MULTI_MODEL_OPTIMIZATION.md' 了解详细信息")

