"""检查BNB数据缺失问题"""
import sqlite3
from market_data import MarketDataFetcher

print("="*70)
print("BNB数据诊断工具")
print("="*70)

# 1. 检查API数据获取
print("\n[1] 测试API数据获取...")
fetcher = MarketDataFetcher()
coins = ['BTC', 'ETH', 'BNB', 'SOL', 'XRP', 'DOGE']
prices = fetcher.get_current_prices(coins)

print(f"\n获取到 {len(prices)} 个币种的价格:")
for coin in coins:
    if coin in prices:
        print(f"  ✅ {coin}: ${prices[coin]['price']:.2f} ({prices[coin]['change_24h']:+.2f}%)")
    else:
        print(f"  ❌ {coin}: 数据缺失")

# 2. 检查数据库缓存
print("\n[2] 检查数据库缓存...")
conn = sqlite3.connect('trading_bot.db')
cursor = conn.cursor()

# 检查历史价格缓存
cursor.execute('SELECT DISTINCT coin FROM market_data_cache')
cached_coins = [row[0] for row in cursor.fetchall()]
print(f"\n历史价格缓存的币种: {cached_coins}")

for coin in coins:
    cursor.execute('SELECT COUNT(*) FROM market_data_cache WHERE coin = ?', (coin,))
    count = cursor.fetchone()[0]
    if count > 0:
        print(f"  ✅ {coin}: {count}条历史价格记录")
    else:
        print(f"  ⚠️ {coin}: 无历史价格缓存")

# 检查技术指标缓存
cursor.execute('SELECT DISTINCT coin FROM technical_indicators_cache')
indicator_coins = [row[0] for row in cursor.fetchall()]
print(f"\n技术指标缓存的币种: {indicator_coins}")

for coin in coins:
    cursor.execute('SELECT COUNT(*) FROM technical_indicators_cache WHERE coin = ?', (coin,))
    count = cursor.fetchone()[0]
    if count > 0:
        cursor.execute('SELECT calculated_at FROM technical_indicators_cache WHERE coin = ? ORDER BY calculated_at DESC LIMIT 1', (coin,))
        last_update = cursor.fetchone()[0]
        print(f"  ✅ {coin}: {count}条技术指标记录 (最后更新: {last_update})")
    else:
        print(f"  ⚠️ {coin}: 无技术指标缓存")

conn.close()

# 3. 测试技术指标计算
print("\n[3] 测试技术指标计算...")
for coin in ['BTC', 'BNB']:
    print(f"\n测试 {coin} 技术指标:")
    indicators = fetcher.calculate_technical_indicators(coin)
    if indicators:
        print(f"  ✅ 成功获取技术指标")
        print(f"     - EMA3m_12: {indicators.get('ema3m_12', 'N/A')}")
        print(f"     - RSI3m: {indicators.get('rsi3m', 'N/A')}")
        print(f"     - MACD4h: {indicators.get('macd4h', 'N/A')}")
    else:
        print(f"  ❌ 技术指标获取失败")

# 4. 测试完整市场状态（使用get_comprehensive_market_state）
print("\n[4] 测试完整市场状态...")
try:
    market_state = fetcher.get_comprehensive_market_state(coins)
    print(f"\n市场状态包含 {len(market_state)} 个币种:")
    for coin in coins:
        if coin in market_state:
            has_price = 'price' in market_state[coin]
            has_indicators = 'indicators' in market_state[coin]
            print(f"  ✅ {coin}: 价格={has_price}, 技术指标={has_indicators}")
            if has_indicators:
                indicators = market_state[coin]['indicators']
                print(f"      指标数量: {len(indicators)} 个")
        else:
            print(f"  ❌ {coin}: 市场状态缺失")
except Exception as e:
    print(f"  ❌ 获取市场状态失败: {e}")

print("\n" + "="*70)
print("诊断完成")
print("="*70)

