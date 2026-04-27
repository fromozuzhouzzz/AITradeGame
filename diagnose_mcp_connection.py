"""
MCP 连接诊断工具
用于诊断 MCP 服务器连接问题、代理配置和网络连通性
"""

import sys
import socket
import requests
import os
from urllib.parse import urlparse


def print_header(title):
    """打印标题"""
    print("\n" + "="*70)
    print(f"🔍 {title}")
    print("="*70)


def test_environment_variables():
    """检查系统环境变量中的代理配置"""
    print_header("1. 检查系统代理环境变量")
    
    proxy_vars = ['HTTP_PROXY', 'HTTPS_PROXY', 'http_proxy', 'https_proxy', 
                  'ALL_PROXY', 'all_proxy', 'NO_PROXY', 'no_proxy']
    
    found_proxy = False
    for var in proxy_vars:
        value = os.environ.get(var)
        if value:
            print(f"  ⚠️  {var} = {value}")
            found_proxy = True
    
    if not found_proxy:
        print("  ✅ 未检测到系统代理环境变量")
    else:
        print("\n  💡 建议: 如果不需要代理，请清除这些环境变量")
        print("     Windows: set HTTP_PROXY=")
        print("     Linux/Mac: unset HTTP_PROXY")
    
    return found_proxy


def test_dns_resolution(hostname):
    """测试 DNS 解析"""
    print_header(f"2. DNS 解析测试: {hostname}")
    
    try:
        ip = socket.gethostbyname(hostname)
        print(f"  ✅ DNS 解析成功")
        print(f"     {hostname} -> {ip}")
        return ip
    except socket.gaierror as e:
        print(f"  ❌ DNS 解析失败: {e}")
        print(f"     无法解析主机名: {hostname}")
        return None


def test_port_connectivity(host, port):
    """测试端口连通性"""
    print_header(f"3. 端口连通性测试: {host}:{port}")
    
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(5)
        result = sock.connect_ex((host, port))
        sock.close()
        
        if result == 0:
            print(f"  ✅ 端口 {port} 可访问")
            return True
        else:
            print(f"  ❌ 端口 {port} 无法访问 (错误码: {result})")
            print(f"     可能原因:")
            print(f"     - 服务器未运行")
            print(f"     - 防火墙阻止")
            print(f"     - 网络不可达")
            return False
    except Exception as e:
        print(f"  ❌ 连接测试失败: {e}")
        return False


def test_http_request(url, timeout=10):
    """测试 HTTP 请求"""
    print_header(f"4. HTTP 请求测试: {url}")
    
    try:
        # 创建不使用代理的 session
        session = requests.Session()
        session.trust_env = False  # 禁用代理
        
        print(f"  📡 发送请求 (超时: {timeout}s)...")
        response = session.get(url, timeout=timeout)
        
        print(f"  ✅ 请求成功")
        print(f"     状态码: {response.status_code}")
        print(f"     响应大小: {len(response.content)} 字节")
        
        if response.status_code == 200:
            print(f"     响应内容: {response.text[:100]}...")
        
        return True
    except requests.exceptions.Timeout:
        print(f"  ❌ 请求超时 ({timeout}s)")
        print(f"     可能原因:")
        print(f"     - 服务器响应慢")
        print(f"     - 网络延迟高")
        print(f"     - 防火墙阻止")
        return False
    except requests.exceptions.ConnectionError as e:
        print(f"  ❌ 连接错误: {e}")
        return False
    except Exception as e:
        print(f"  ❌ 请求失败: {e}")
        return False


def test_mcp_client(mcp_url):
    """测试 MCP 客户端"""
    print_header(f"5. MCP 客户端测试")
    
    try:
        from mcp_client import MCPAkToolsClient
        
        print(f"  📡 初始化 MCP 客户端...")
        client = MCPAkToolsClient(base_url=mcp_url, disable_proxy=True)
        
        print(f"  📡 执行健康检查...")
        if client.health_check():
            print(f"  ✅ MCP 客户端连接成功")
            return True
        else:
            print(f"  ❌ MCP 健康检查失败")
            return False
    except Exception as e:
        print(f"  ❌ MCP 客户端测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """主诊断流程"""
    print("\n" + "="*70)
    print("🚀 MCP 连接诊断工具")
    print("="*70)
    
    # 配置
    mcp_url = "http://27.106.106.133:8808/mcp"
    parsed_url = urlparse(mcp_url)
    hostname = parsed_url.hostname
    port = parsed_url.port or 80
    
    print(f"\n📋 诊断配置:")
    print(f"   MCP 服务器: {mcp_url}")
    print(f"   主机名: {hostname}")
    print(f"   端口: {port}")
    
    # 执行诊断
    results = {}
    
    # 1. 检查环境变量
    results['env_proxy'] = test_environment_variables()
    
    # 2. DNS 解析
    ip = test_dns_resolution(hostname)
    results['dns'] = ip is not None
    
    # 3. 端口连通性
    if ip:
        results['port'] = test_port_connectivity(ip, port)
    else:
        results['port'] = False
    
    # 4. HTTP 请求
    results['http'] = test_http_request(f"{mcp_url}/health", timeout=10)
    
    # 5. MCP 客户端
    results['mcp_client'] = test_mcp_client(mcp_url)
    
    # 总结
    print_header("📊 诊断总结")
    
    print("\n测试结果:")
    print(f"  {'环境代理配置':<20} {'❌ 检测到代理' if results['env_proxy'] else '✅ 无代理'}")
    print(f"  {'DNS 解析':<20} {'✅ 成功' if results['dns'] else '❌ 失败'}")
    print(f"  {'端口连通性':<20} {'✅ 可访问' if results['port'] else '❌ 不可访问'}")
    print(f"  {'HTTP 请求':<20} {'✅ 成功' if results['http'] else '❌ 失败'}")
    print(f"  {'MCP 客户端':<20} {'✅ 连接成功' if results['mcp_client'] else '❌ 连接失败'}")
    
    # 建议
    print("\n💡 故障排除建议:")
    
    if not results['dns']:
        print("  1. DNS 解析失败:")
        print("     - 检查网络连接")
        print("     - 尝试 ping 27.106.106.133")
        print("     - 检查 DNS 设置")
    
    if not results['port']:
        print("  2. 端口不可访问:")
        print("     - 确认 MCP 服务器已启动")
        print("     - 检查防火墙设置")
        print("     - 尝试: telnet 27.106.106.133 8808")
    
    if not results['http']:
        print("  3. HTTP 请求失败:")
        print("     - 检查服务器是否在线")
        print("     - 尝试: curl http://27.106.106.133:8808/mcp/health")
        print("     - 检查网络延迟")
    
    if results['env_proxy']:
        print("  4. 检测到系统代理:")
        print("     - 代理可能导致连接超时")
        print("     - 已在 MCP 客户端中禁用代理")
        print("     - 如果仍有问题，请清除代理环境变量")
    
    # 最终状态
    print("\n" + "="*70)
    if results['mcp_client']:
        print("✅ 诊断完成: MCP 连接正常！")
        print("="*70)
        return 0
    else:
        print("❌ 诊断完成: MCP 连接存在问题")
        print("="*70)
        print("\n🔧 快速修复步骤:")
        print("  1. 确认 MCP 服务器运行: docker-compose ps")
        print("  2. 检查服务器日志: docker-compose logs -f")
        print("  3. 测试网络连通性: ping 27.106.106.133")
        print("  4. 清除代理: set HTTP_PROXY= (Windows) 或 unset HTTP_PROXY (Linux)")
        print("  5. 重新运行此诊断脚本")
        return 1


if __name__ == "__main__":
    sys.exit(main())

