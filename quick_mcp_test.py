"""
快速 MCP 连接测试
验证 MCP 客户端是否能正常连接和获取数据
"""

import sys
from mcp_client import MCPAkToolsClient


def test_basic_connection():
    """测试基本连接"""
    print("\n" + "="*70)
    print("测试 1: 基本连接")
    print("="*70)
    
    try:
        print("📡 初始化 MCP 客户端...")
        client = MCPAkToolsClient(
            base_url="http://27.106.106.133:8808/mcp",
            disable_proxy=True
        )
        print("✅ 客户端初始化成功")
        return client
    except Exception as e:
        print(f"❌ 初始化失败: {e}")
        return None


def test_health_check(client):
    """测试健康检查"""
    print("\n" + "="*70)
    print("测试 2: 健康检查")
    print("="*70)
    
    if not client:
        print("❌ 跳过（客户端未初始化）")
        return False
    
    try:
        result = client.health_check()
        if result:
            print("✅ 健康检查通过")
            return True
        else:
            print("❌ 健康检查失败")
            return False
    except Exception as e:
        print(f"❌ 健康检查异常: {e}")
        return False


def test_news_fetch(client):
    """测试新闻获取"""
    print("\n" + "="*70)
    print("测试 3: 新闻获取")
    print("="*70)
    
    if not client:
        print("❌ 跳过（客户端未初始化）")
        return False
    
    try:
        print("📰 获取 BTC 新闻...")
        news = client.get_crypto_news("BTC", limit=3)
        
        if news:
            print(f"✅ 成功获取 {len(news)} 条新闻")
            for idx, item in enumerate(news, 1):
                print(f"  {idx}. [{item.get('sentiment', 'unknown').upper()}] {item.get('title', 'N/A')[:50]}...")
            return True
        else:
            print("⚠️  未获取到新闻（可能是 API 格式问题）")
            return False
    except Exception as e:
        print(f"❌ 新闻获取失败: {e}")
        return False


def test_indicators_fetch(client):
    """测试技术指标获取"""
    print("\n" + "="*70)
    print("测试 4: 技术指标获取")
    print("="*70)
    
    if not client:
        print("❌ 跳过（客户端未初始化）")
        return False
    
    try:
        print("📊 获取 BTC 技术指标...")
        indicators = client.get_technical_indicators("BTC", timeframe="1d")
        
        if indicators:
            print(f"✅ 成功获取技术指标")
            print(f"  • RSI: {indicators.get('rsi', 'N/A')}")
            print(f"  • MACD: {indicators.get('macd', 'N/A')}")
            print(f"  • Bollinger Upper: {indicators.get('bollinger_upper', 'N/A')}")
            return True
        else:
            print("⚠️  未获取到指标（可能是 API 格式问题）")
            return False
    except Exception as e:
        print(f"❌ 指标获取失败: {e}")
        return False


def main():
    """主测试流程"""
    print("\n" + "="*70)
    print("🚀 快速 MCP 连接测试")
    print("="*70)
    
    print("\n📋 测试配置:")
    print("   MCP 服务器: http://27.106.106.133:8808/mcp")
    print("   代理: 已禁用")
    print("   超时: 10 秒")
    
    # 执行测试
    results = {}
    
    # 1. 基本连接
    client = test_basic_connection()
    results['connection'] = client is not None
    
    # 2. 健康检查
    results['health'] = test_health_check(client)
    
    # 3. 新闻获取
    results['news'] = test_news_fetch(client)
    
    # 4. 指标获取
    results['indicators'] = test_indicators_fetch(client)
    
    # 总结
    print("\n" + "="*70)
    print("📊 测试总结")
    print("="*70)
    
    print("\n测试结果:")
    print(f"  {'基本连接':<20} {'✅ 成功' if results['connection'] else '❌ 失败'}")
    print(f"  {'健康检查':<20} {'✅ 通过' if results['health'] else '❌ 失败'}")
    print(f"  {'新闻获取':<20} {'✅ 成功' if results['news'] else '⚠️  失败/未实现'}")
    print(f"  {'指标获取':<20} {'✅ 成功' if results['indicators'] else '⚠️  失败/未实现'}")
    
    passed = sum(1 for v in results.values() if v)
    total = len(results)
    
    print(f"\n总计: {passed}/{total} 测试通过")
    
    # 建议
    print("\n" + "="*70)
    if results['health']:
        print("✅ MCP 连接正常！系统已准备就绪")
        print("="*70)
        print("\n下一步:")
        print("  1. 运行 python app.py 启动交易系统")
        print("  2. 系统将自动使用 MCP 增强数据")
        print("  3. 查看日志确认新闻和指标已集成")
        return 0
    else:
        print("❌ MCP 连接存在问题")
        print("="*70)
        print("\n故障排除:")
        print("  1. 运行诊断工具: python diagnose_mcp_connection.py")
        print("  2. 检查 MCP 服务器状态: docker-compose ps")
        print("  3. 查看服务器日志: docker-compose logs -f")
        print("  4. 验证网络连通性: ping 27.106.106.133")
        print("  5. 清除代理设置: set HTTP_PROXY= (Windows)")
        return 1


if __name__ == "__main__":
    sys.exit(main())

