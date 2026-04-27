"""强制清除Flask应用的缓存"""
import requests
import time

print("="*70)
print("强制清除Flask应用缓存")
print("="*70)

# 尝试多次请求以触发缓存刷新
print("\n[1] 发送多次请求以触发缓存刷新...")

for i in range(3):
    try:
        # 添加时间戳参数以绕过缓存
        timestamp = int(time.time() * 1000)
        url = f"http://localhost:5000/api/market/prices?_t={timestamp}"
        
        print(f"\n请求 #{i+1}: {url}")
        response = requests.get(url, timeout=10)
        
        if response.status_code == 200:
            prices = response.json()
            print(f"  返回币种数量: {len(prices)}")
            print(f"  币种列表: {list(prices.keys())}")
            
            if 'BNB' in prices:
                print(f"  ✅ BNB数据已恢复: ${prices['BNB']['price']:.2f}")
                break
            else:
                print(f"  ❌ BNB仍然缺失")
        else:
            print(f"  ❌ 请求失败: HTTP {response.status_code}")
    
    except Exception as e:
        print(f"  ❌ 请求失败: {e}")
    
    if i < 2:
        print("  等待5秒后重试...")
        time.sleep(5)

print("\n" + "="*70)
print("如果BNB仍然缺失，请手动重启Flask应用")
print("="*70)

