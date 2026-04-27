"""清除MarketDataFetcher的缓存，强制重新获取数据"""
import requests

print("="*70)
print("清除市场数据缓存")
print("="*70)

# 方法1：通过API触发缓存刷新
print("\n[方法1] 通过API触发缓存刷新...")
try:
    # 请求市场健康状态（这会触发一次数据获取）
    response = requests.get("http://localhost:5000/api/market/health", timeout=5)
    if response.status_code == 200:
        health = response.json()
        print(f"✅ API健康状态: {health}")
    else:
        print(f"❌ 请求失败: HTTP {response.status_code}")
except Exception as e:
    print(f"❌ 请求失败: {e}")

# 方法2：等待缓存过期（30秒）
print("\n[方法2] 等待缓存自动过期...")
print("提示：market_data.py中的缓存时间为30秒")
print("请等待30秒后再次测试前端API")

# 方法3：重启Flask应用
print("\n[方法3] 重启Flask应用（推荐）")
print("请在Flask应用的终端中按 Ctrl+C 停止，然后重新运行:")
print("  python app.py")

print("\n" + "="*70)
print("建议：重启Flask应用以确保使用最新的market_data.py代码")
print("="*70)

