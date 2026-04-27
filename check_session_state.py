"""检查MarketDataFetcher的session状态"""
from market_data import MarketDataFetcher

print("="*70)
print("检查MarketDataFetcher Session状态")
print("="*70)

fetcher = MarketDataFetcher()

print(f"\n当前Session ID: {fetcher._current_session_id}")
print(f"Session快照数量: {len(fetcher._session_snapshot)}")

if fetcher._session_snapshot:
    print("\nSession快照详情:")
    for session_id, snapshot_data in fetcher._session_snapshot.items():
        print(f"\n  Session: {session_id}")
        print(f"    时间戳: {snapshot_data['timestamp']}")
        print(f"    API调用次数: {snapshot_data['api_calls']}")
        print(f"    数据键: {list(snapshot_data['data'].keys())}")
        
        if 'market_state' in snapshot_data['data']:
            market_state = snapshot_data['data']['market_state']
            print(f"    市场状态币种: {list(market_state.keys())}")
            
            if 'BNB' in market_state:
                print(f"      ✅ BNB存在于快照中")
            else:
                print(f"      ❌ BNB不在快照中")
else:
    print("\n没有活跃的session快照")

# 测试直接获取价格（不使用session）
print("\n" + "="*70)
print("测试直接获取价格（绕过session）")
print("="*70)

coins = ['BTC', 'ETH', 'BNB', 'SOL', 'XRP', 'DOGE']
prices = fetcher.get_current_prices(coins)

print(f"\n获取到 {len(prices)} 个币种:")
for coin in coins:
    if coin in prices:
        print(f"  ✅ {coin}: ${prices[coin]['price']:.2f}")
    else:
        print(f"  ❌ {coin}: 缺失")

print("\n" + "="*70)

