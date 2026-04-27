"""
MCP Client for AkTools Server Integration (FastMCP 2.0)
提供加密货币技术指标和新闻资讯的MCP服务器客户端

使用 FastMCP 官方客户端库，支持 Streamable-HTTP 传输协议
"""

import asyncio
import json
from typing import Dict, List, Optional
from datetime import datetime, timedelta

try:
    from fastmcp import Client
except ImportError:
    print("[MCP ERROR] fastmcp not installed. Please run: pip install fastmcp")
    raise


class MCPAkToolsClient:
    """
    MCP AkTools服务器客户端（基于 FastMCP 2.0）
    用于获取加密货币的技术分析指标和最新新闻资讯
    
    使用 FastMCP 官方客户端，支持 Streamable-HTTP 协议
    """

    def __init__(self, server_url: str = "http://27.106.106.133:8808/mcp"):
        """
        初始化MCP客户端

        Args:
            server_url: MCP服务器完整URL（包含 /mcp 路径）
        """
        self.server_url = server_url
        self.client = None
        self._connected = False
        self._event_loop = None
        
        # 缓存机制
        self._news_cache = {}
        self._news_cache_time = {}
        self._cache_duration = 300  # 新闻缓存5分钟
        
        print(f"[MCP] Initialized FastMCP client for: {self.server_url}")
        
        # 同步初始化：建立连接
        self._sync_connect()
    
    def _sync_connect(self):
        """
        同步方式建立 MCP 连接
        创建新的事件循环并在其中运行异步连接
        """
        try:
            # 创建新的事件循环
            self._event_loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self._event_loop)
            
            # 在事件循环中运行异步连接
            self._event_loop.run_until_complete(self._async_connect())
        except Exception as e:
            print(f"[MCP ERROR] Failed to connect: {e}")
            self._connected = False
    
    async def _async_connect(self):
        """
        异步建立 MCP 连接
        """
        try:
            print(f"[MCP] Connecting to {self.server_url}...")
            
            # 创建 FastMCP 客户端
            self.client = Client(self.server_url)
            
            # 进入上下文管理器
            await self.client.__aenter__()
            
            self._connected = True
            print(f"[MCP] Successfully connected to MCP server")
            
            # 列出可用工具（用于验证连接）
            try:
                tools = await self.client.list_tools()
                print(f"[MCP] Available tools: {len(tools.tools)}")
                for tool in tools.tools:
                    print(f"[MCP]   - {tool.name}: {tool.description}")
            except Exception as e:
                print(f"[MCP WARNING] Could not list tools: {e}")
                
        except Exception as e:
            print(f"[MCP ERROR] Connection failed: {e}")
            self._connected = False
            raise
    
    def _run_async(self, coro):
        """
        在事件循环中运行异步协程
        
        Args:
            coro: 异步协程
            
        Returns:
            协程的返回值
        """
        if not self._event_loop:
            self._event_loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self._event_loop)
        
        return self._event_loop.run_until_complete(coro)
    
    def get_crypto_news(self, coin: str, limit: int = 5) -> List[Dict]:
        """
        获取加密货币相关新闻（同步接口）

        Args:
            coin: 币种符号（如 BTC, ETH）
            limit: 返回新闻数量

        Returns:
            新闻列表，每条新闻包含：title, summary, published_time, sentiment
        """
        # 检查缓存
        cache_key = f"{coin}_{limit}"
        if cache_key in self._news_cache:
            cache_time = self._news_cache_time.get(cache_key)
            if cache_time and (datetime.now() - cache_time) < timedelta(seconds=self._cache_duration):
                print(f"[MCP] Using cached news for {coin}")
                return self._news_cache[cache_key]
        
        # 运行异步方法
        try:
            return self._run_async(self._async_get_crypto_news(coin, limit))
        except Exception as e:
            print(f"[MCP ERROR] Failed to get news for {coin}: {e}")
            return []
    
    async def _async_get_crypto_news(self, coin: str, limit: int = 5) -> List[Dict]:
        """
        异步获取加密货币相关新闻

        Args:
            coin: 币种符号（如 BTC, ETH）
            limit: 返回新闻数量

        Returns:
            新闻列表
        """
        if not self._connected or not self.client:
            print(f"[MCP ERROR] Not connected to MCP server")
            return []
        
        try:
            print(f"[MCP DEBUG] Calling stock_news tool: keyword={coin}, news_count={limit}")
            
            # 使用 FastMCP 客户端调用工具
            result = await self.client.call_tool(
                "stock_news",
                {"keyword": coin, "news_count": limit}
            )
            
            print(f"[MCP DEBUG] Tool call successful, result type: {type(result)}")
            
            # 解析结果
            news_list = self._parse_news_result(result, coin)
            
            # 更新缓存
            cache_key = f"{coin}_{limit}"
            self._news_cache[cache_key] = news_list
            self._news_cache_time[cache_key] = datetime.now()
            
            print(f"[MCP] Retrieved {len(news_list)} news items for {coin}")
            return news_list
            
        except Exception as e:
            print(f"[MCP ERROR] Failed to call stock_news tool: {e}")
            import traceback
            traceback.print_exc()
            return []
    
    def _parse_news_result(self, result, coin: str) -> List[Dict]:
        """
        解析 FastMCP 工具调用结果
        
        Args:
            result: FastMCP 工具调用结果
            coin: 币种符号
            
        Returns:
            新闻列表
        """
        news_list = []
        
        try:
            # FastMCP 结果通常包含 content 列表
            if hasattr(result, 'content'):
                for content_item in result.content:
                    if hasattr(content_item, 'text'):
                        # 解析文本内容
                        text = content_item.text
                        
                        # 如果是换行分隔的新闻列表
                        if '\n' in text:
                            news_items = text.split('\n')
                            for i, item in enumerate(news_items[:limit], 1):
                                if item.strip():
                                    news_list.append({
                                        'title': f"{coin} News {i}",
                                        'summary': item.strip(),
                                        'published_time': datetime.now().isoformat(),
                                        'sentiment': 'neutral'
                                    })
                        else:
                            # 单条新闻
                            news_list.append({
                                'title': f"{coin} News",
                                'summary': text,
                                'published_time': datetime.now().isoformat(),
                                'sentiment': 'neutral'
                            })
            
            return news_list
            
        except Exception as e:
            print(f"[MCP ERROR] Failed to parse news result: {e}")
            return []
    
    def get_technical_indicators(self, coin: str, timeframe: str = "1d") -> Dict:
        """
        获取加密货币技术指标（同步接口）

        Args:
            coin: 币种符号（如 BTC, ETH）
            timeframe: 时间框架（如 1d, 4h, 1h）

        Returns:
            技术指标字典
        """
        try:
            return self._run_async(self._async_get_technical_indicators(coin, timeframe))
        except Exception as e:
            print(f"[MCP ERROR] Failed to get indicators for {coin}: {e}")
            return {}
    
    async def _async_get_technical_indicators(self, coin: str, timeframe: str = "1d") -> Dict:
        """
        异步获取加密货币技术指标

        Args:
            coin: 币种符号
            timeframe: 时间框架

        Returns:
            技术指标字典
        """
        if not self._connected or not self.client:
            print(f"[MCP ERROR] Not connected to MCP server")
            return {}
        
        try:
            # 转换时间框架格式
            bar = timeframe.upper().replace('D', 'D').replace('H', 'H').replace('M', 'M')
            
            print(f"[MCP DEBUG] Calling okx_prices tool: instId={coin}-USDT, bar={bar}, limit=30")
            
            # 使用 FastMCP 客户端调用工具
            result = await self.client.call_tool(
                "okx_prices",
                {"instId": f"{coin}-USDT", "bar": bar, "limit": 30}
            )
            
            print(f"[MCP DEBUG] Tool call successful, result type: {type(result)}")
            
            # 解析结果
            indicators = self._parse_indicators_result(result)
            
            print(f"[MCP] Retrieved indicators for {coin}")
            return indicators
            
        except Exception as e:
            print(f"[MCP ERROR] Failed to call okx_prices tool: {e}")
            import traceback
            traceback.print_exc()
            return {}
    
    def _parse_indicators_result(self, result) -> Dict:
        """
        解析技术指标结果
        
        Args:
            result: FastMCP 工具调用结果
            
        Returns:
            技术指标字典
        """
        indicators = {}
        
        try:
            # FastMCP 结果通常包含 content 列表
            if hasattr(result, 'content'):
                for content_item in result.content:
                    if hasattr(content_item, 'text'):
                        text = content_item.text
                        # 尝试解析 JSON
                        try:
                            data = json.loads(text)
                            indicators = data
                        except json.JSONDecodeError:
                            # 如果不是 JSON，尝试其他解析方式
                            print(f"[MCP DEBUG] Result is not JSON: {text[:200]}")
            
            return indicators
            
        except Exception as e:
            print(f"[MCP ERROR] Failed to parse indicators result: {e}")
            return {}
    
    def __del__(self):
        """
        清理资源
        """
        if self._event_loop and self.client and self._connected:
            try:
                self._event_loop.run_until_complete(self.client.__aexit__(None, None, None))
            except:
                pass
            
            try:
                self._event_loop.close()
            except:
                pass

