"""
全面的 MCP 服务器诊断工具
用于诊断 MCP 服务器连接问题、API 端点、认证等
"""

import sys
import socket
import requests
import os
import json
from urllib.parse import urlparse
import subprocess


def print_header(title):
    """打印标题"""
    print("\n" + "="*70)
    print(f"🔍 {title}")
    print("="*70)


def test_basic_connectivity(host, port):
    """测试基本网络连通性"""
    print_header("1. 基本网络连通性测试")
    
    print(f"  📡 测试 TCP 连接到 {host}:{port}...")
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(5)
        result = sock.connect_ex((host, port))
        sock.close()
        
        if result == 0:
            print(f"  ✅ TCP 连接成功")
            return True
        else:
            print(f"  ❌ TCP 连接失败 (错误码: {result})")
            return False
    except Exception as e:
        print(f"  ❌ 连接测试异常: {e}")
        return False


def test_http_endpoints(base_url):
    """测试多个 HTTP 端点"""
    print_header("2. HTTP 端点测试")
    
    session = requests.Session()
    session.trust_env = False
    
    # 测试多个可能的端点
    endpoints = [
        ("/health", "健康检查 (标准)"),
        ("/mcp/health", "健康检查 (MCP 路径)"),
        ("/api/health", "健康检查 (API 路径)"),
        ("/", "根路径"),
        ("/mcp", "MCP 根路径"),
        ("/api", "API 根路径"),
        ("/status", "状态端点"),
        ("/mcp/status", "MCP 状态端点"),
    ]
    
    results = {}
    for endpoint, description in endpoints:
        url = f"{base_url.rstrip('/')}{endpoint}"
        try:
            print(f"\n  📡 测试: {description}")
            print(f"     URL: {url}")
            
            response = session.get(url, timeout=5)
            print(f"     ✅ 状态码: {response.status_code}")
            print(f"     📝 响应大小: {len(response.content)} 字节")
            
            if response.status_code == 200:
                try:
                    data = response.json()
                    print(f"     📊 JSON 响应: {json.dumps(data, indent=6)[:200]}...")
                except:
                    print(f"     📄 文本响应: {response.text[:100]}...")
            
            results[endpoint] = {
                'status': response.status_code,
                'success': response.status_code == 200
            }
        except requests.exceptions.Timeout:
            print(f"     ❌ 超时 (5s)")
            results[endpoint] = {'status': 'timeout', 'success': False}
        except requests.exceptions.ConnectionError as e:
            print(f"     ❌ 连接错误: {str(e)[:50]}")
            results[endpoint] = {'status': 'connection_error', 'success': False}
        except Exception as e:
            print(f"     ❌ 错误: {str(e)[:50]}")
            results[endpoint] = {'status': 'error', 'success': False}
    
    return results


def test_api_calls(base_url):
    """测试实际的 API 调用"""
    print_header("3. API 功能测试")
    
    session = requests.Session()
    session.trust_env = False
    session.headers.update({
        'Content-Type': 'application/json',
        'Accept': 'application/json',
    })
    
    # 测试多个可能的 API 端点
    api_tests = [
        {
            'name': '新闻 API (MCP 格式)',
            'endpoint': '/call',
            'method': 'POST',
            'payload': {
                "method": "tools/call",
                "params": {
                    "name": "get_crypto_news",
                    "arguments": {"symbol": "BTC", "limit": 1}
                }
            }
        },
        {
            'name': '技术指标 API (MCP 格式)',
            'endpoint': '/call',
            'method': 'POST',
            'payload': {
                "method": "tools/call",
                "params": {
                    "name": "get_technical_indicators",
                    "arguments": {"symbol": "BTC", "timeframe": "1d"}
                }
            }
        },
        {
            'name': '新闻 API (REST 格式)',
            'endpoint': '/news',
            'method': 'GET',
            'params': {'symbol': 'BTC', 'limit': 1}
        },
        {
            'name': '指标 API (REST 格式)',
            'endpoint': '/indicators',
            'method': 'GET',
            'params': {'symbol': 'BTC', 'timeframe': '1d'}
        },
    ]
    
    results = {}
    for test in api_tests:
        url = f"{base_url.rstrip('/')}{test['endpoint']}"
        try:
            print(f"\n  📡 测试: {test['name']}")
            print(f"     URL: {url}")
            
            if test['method'] == 'POST':
                response = session.post(url, json=test['payload'], timeout=10)
            else:
                response = session.get(url, params=test.get('params'), timeout=10)
            
            print(f"     ✅ 状态码: {response.status_code}")
            
            if response.status_code in [200, 201]:
                try:
                    data = response.json()
                    print(f"     📊 响应: {json.dumps(data, indent=6)[:200]}...")
                    results[test['name']] = {'status': response.status_code, 'success': True}
                except:
                    print(f"     📄 文本响应: {response.text[:100]}...")
                    results[test['name']] = {'status': response.status_code, 'success': True}
            else:
                print(f"     ⚠️  状态码: {response.status_code}")
                results[test['name']] = {'status': response.status_code, 'success': False}
        except requests.exceptions.Timeout:
            print(f"     ❌ 超时 (10s)")
            results[test['name']] = {'status': 'timeout', 'success': False}
        except Exception as e:
            print(f"     ❌ 错误: {str(e)[:50]}")
            results[test['name']] = {'status': 'error', 'success': False}
    
    return results


def test_authentication(base_url):
    """测试认证需求"""
    print_header("4. 认证测试")
    
    session = requests.Session()
    session.trust_env = False
    
    auth_headers = [
        {'name': '无认证', 'headers': {}},
        {'name': 'Bearer Token', 'headers': {'Authorization': 'Bearer test-token'}},
        {'name': 'API Key', 'headers': {'X-API-Key': 'test-key'}},
        {'name': 'Basic Auth', 'headers': {'Authorization': 'Basic dGVzdDp0ZXN0'}},
    ]
    
    url = f"{base_url.rstrip('/')}/health"
    
    for auth in auth_headers:
        try:
            print(f"\n  📡 测试: {auth['name']}")
            
            headers = session.headers.copy()
            headers.update(auth['headers'])
            
            response = requests.get(url, headers=headers, timeout=5)
            print(f"     状态码: {response.status_code}")
            
            if response.status_code == 200:
                print(f"     ✅ 成功")
            elif response.status_code == 401:
                print(f"     ⚠️  需要认证 (401)")
            elif response.status_code == 403:
                print(f"     ⚠️  禁止访问 (403)")
            else:
                print(f"     ℹ️  其他状态")
        except Exception as e:
            print(f"     ❌ 错误: {str(e)[:50]}")


def test_server_info(base_url):
    """获取服务器信息"""
    print_header("5. 服务器信息")
    
    session = requests.Session()
    session.trust_env = False
    
    # 尝试获取服务器信息
    info_endpoints = ['/info', '/version', '/about', '/mcp/info']
    
    for endpoint in info_endpoints:
        url = f"{base_url.rstrip('/')}{endpoint}"
        try:
            response = session.get(url, timeout=5)
            if response.status_code == 200:
                print(f"\n  ✅ 找到服务器信息端点: {endpoint}")
                try:
                    data = response.json()
                    print(f"     {json.dumps(data, indent=6)}")
                except:
                    print(f"     {response.text}")
                return
        except:
            pass
    
    print(f"\n  ℹ️  未找到服务器信息端点")


def main():
    """主诊断流程"""
    print("\n" + "="*70)
    print("🚀 全面 MCP 服务器诊断工具")
    print("="*70)
    
    # 配置
    mcp_url = "http://27.106.106.133:8808/mcp"
    parsed_url = urlparse(mcp_url)
    hostname = parsed_url.hostname
    port = parsed_url.port or 80
    
    print(f"\n📋 诊断配置:")
    print(f"   MCP 服务器: {mcp_url}")
    print(f"   主机: {hostname}")
    print(f"   端口: {port}")
    
    # 执行诊断
    print(f"\n⏳ 开始诊断...")
    
    # 1. 基本连通性
    connectivity = test_basic_connectivity(hostname, port)
    
    if not connectivity:
        print("\n" + "="*70)
        print("❌ 网络连接失败，无法继续诊断")
        print("="*70)
        print("\n🔧 快速修复:")
        print("  1. 检查网络连接: ping 27.106.106.133")
        print("  2. 检查防火墙: telnet 27.106.106.133 8808")
        print("  3. 确认 MCP 服务器运行")
        return 1
    
    # 2. HTTP 端点测试
    endpoints = test_http_endpoints(mcp_url)
    
    # 3. API 功能测试
    api_results = test_api_calls(mcp_url)
    
    # 4. 认证测试
    test_authentication(mcp_url)
    
    # 5. 服务器信息
    test_server_info(mcp_url)
    
    # 总结
    print_header("📊 诊断总结")
    
    successful_endpoints = [ep for ep, res in endpoints.items() if res.get('success')]
    successful_apis = [api for api, res in api_results.items() if res.get('success')]
    
    print(f"\n✅ 成功的端点: {len(successful_endpoints)}/{len(endpoints)}")
    for ep in successful_endpoints:
        print(f"   - {ep}")
    
    print(f"\n✅ 成功的 API: {len(successful_apis)}/{len(api_results)}")
    for api in successful_apis:
        print(f"   - {api}")
    
    # 建议
    print("\n💡 建议:")
    
    if not successful_endpoints:
        print("  - 未找到任何可用的健康检查端点")
        print("  - 可能的原因:")
        print("    1. MCP 服务器未启动")
        print("    2. 服务器配置不正确")
        print("    3. 防火墙阻止")
    
    if successful_apis:
        print(f"  - 找到 {len(successful_apis)} 个可用的 API 端点")
        print("  - 可以跳过健康检查，直接使用这些端点")
    
    print("\n" + "="*70)
    if successful_endpoints or successful_apis:
        print("✅ 诊断完成: 服务器可访问")
    else:
        print("❌ 诊断完成: 服务器不可访问")
    print("="*70)
    
    return 0 if (successful_endpoints or successful_apis) else 1


if __name__ == "__main__":
    sys.exit(main())

