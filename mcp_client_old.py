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
        使用 asyncio.run() 在同步上下文中运行异步连接
        """
        try:
            asyncio.run(self._async_connect())
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

    def get_crypto_news(self, coin: str, limit: int = 5) -> List[Dict]:
        """
        获取加密货币相关新闻

        Args:
            coin: 币种符号（如 BTC, ETH）
            limit: 返回新闻数量

        Returns:
            新闻列表，每条新闻包含：title, summary, published_time, sentiment
        """
        # 检查缓存
        cache_key = f"{coin}_{limit}"
        if cache_key in self._news_cache:
            import time
            if time.time() - self._news_cache_time[cache_key] < self._cache_duration:
                print(f"[MCP] Using cached news for {coin}")
                return self._news_cache[cache_key]

        try:
            # 调用MCP服务器的新闻工具
            # 根据 mcp-aktools 源代码，stock_news 工具的正确参数是：
            # - keyword: 关键词（必需）
            # - news_count: 新闻数量（可选，默认15）
            payload = {
                "jsonrpc": "2.0",
                "id": str(uuid.uuid4()),
                "method": "tools/call",
                "params": {
                    "name": "stock_news",
                    "arguments": {
                        "keyword": coin,
                        "news_count": limit
                    }
                }
            }

            # 调试：打印请求
            print(f"[MCP DEBUG] News request payload: {json.dumps(payload, indent=2)}")

            # 添加 session ID 到请求头
            headers = {}
            if self.session_id:
                headers['mcp-session-id'] = self.session_id

            response = self.session.post(
                self.mcp_endpoint,
                json=payload,
                headers=headers,
                timeout=15
            )

            # 调试：打印响应
            print(f"[MCP DEBUG] News response status: {response.status_code}")
            print(f"[MCP DEBUG] News response text (first 500 chars): {response.text[:500]}")

            if response.status_code == 200:
                # Parse SSE (Server-Sent Events) response
                data = self._parse_sse_response(response.text)
                if data:
                    news_list = self._parse_news_response(data, coin)

                    # 更新缓存
                    import time
                    self._news_cache[cache_key] = news_list
                    self._news_cache_time[cache_key] = time.time()

                    print(f"[MCP] Fetched {len(news_list)} news items for {coin}")
                    return news_list
                else:
                    print(f"[MCP WARNING] Failed to parse SSE response")
                    return []
            else:
                print(f"[MCP WARNING] News API returned status {response.status_code}")
                return []
                
        except Exception as e:
            print(f"[MCP ERROR] Failed to fetch news for {coin}: {e}")
            return []
    
    def get_technical_indicators(self, coin: str, timeframe: str = "1d") -> Dict:
        """
        从MCP服务器获取技术指标
        
        Args:
            coin: 币种符号（如 BTC, ETH）
            timeframe: 时间框架（1h, 4h, 1d等）
            
        Returns:
            技术指标字典，包含：RSI, MACD, EMA, 布林带等
        """
        try:
            # mcp-aktools 使用 okx_prices 工具获取K线数据（包含技术指标）
            # 参数：instId (如 BTC-USDT), bar (如 1H, 1D), limit (数量)
            # JSON-RPC 2.0 规范要求包含 jsonrpc 和 id 字段

            # 转换时间周期格式：1d -> 1D, 1h -> 1H
            bar = timeframe.replace('d', 'D').replace('h', 'H').replace('m', 'm')

            payload = {
                "jsonrpc": "2.0",
                "id": str(uuid.uuid4()),
                "method": "tools/call",
                "params": {
                    "name": "okx_prices",
                    "arguments": {
                        "instId": f"{coin}-USDT",
                        "bar": bar,
                        "limit": 30
                    }
                }
            }

            # 添加 session ID 到请求头
            headers = {}
            if self.session_id:
                headers['mcp-session-id'] = self.session_id

            response = self.session.post(
                self.mcp_endpoint,
                json=payload,
                headers=headers,
                timeout=15
            )

            if response.status_code == 200:
                # Parse SSE (Server-Sent Events) response
                data = self._parse_sse_response(response.text)
                if data:
                    indicators = self._parse_indicators_response(data)
                    print(f"[MCP] Fetched technical indicators for {coin} ({timeframe})")
                    return indicators
                else:
                    print(f"[MCP WARNING] Failed to parse SSE response for indicators")
                    return {}
            else:
                print(f"[MCP WARNING] Indicators API returned status {response.status_code}")
                return {}
                
        except Exception as e:
            print(f"[MCP ERROR] Failed to fetch indicators for {coin}: {e}")
            return {}
    
    def get_historical_data(self, coin: str, days: int = 30) -> List[Dict]:
        """
        获取历史价格数据（带技术指标）
        
        Args:
            coin: 币种符号
            days: 历史天数
            
        Returns:
            历史数据列表
        """
        try:
            # JSON-RPC 2.0 规范要求包含 jsonrpc 和 id 字段
            payload = {
                "jsonrpc": "2.0",
                "id": str(uuid.uuid4()),
                "method": "tools/call",
                "params": {
                    "name": "get_historical_prices",
                    "arguments": {
                        "symbol": coin,
                        "days": days
                    }
                }
            }
            
            # 添加 session ID 到请求头
            headers = {}
            if self.session_id:
                headers['mcp-session-id'] = self.session_id

            response = self.session.post(
                self.mcp_endpoint,
                json=payload,
                headers=headers,
                timeout=20
            )

            if response.status_code == 200:
                # Parse SSE (Server-Sent Events) response
                data = self._parse_sse_response(response.text)
                if data:
                    historical = self._parse_historical_response(data)
                    print(f"[MCP] Fetched {len(historical)} historical data points for {coin}")
                    return historical
                else:
                    print(f"[MCP WARNING] Failed to parse SSE response for historical data")
                    return []
            else:
                print(f"[MCP WARNING] Historical data API returned status {response.status_code}")
                return []
                
        except Exception as e:
            print(f"[MCP ERROR] Failed to fetch historical data for {coin}: {e}")
            return []
    
    def _parse_sse_response(self, response_text: str) -> Dict:
        """
        解析 Server-Sent Events (SSE) 格式的响应

        SSE 格式示例:
        event: message
        data: {"jsonrpc":"2.0","id":"...","result":{...}}

        Returns:
            解析后的 JSON 数据，如果解析失败返回 None
        """
        try:
            # SSE 格式：每行以 "data: " 开头
            for line in response_text.split('\n'):
                line = line.strip()
                if line.startswith('data: '):
                    json_str = line[6:]  # 移除 "data: " 前缀
                    data = json.loads(json_str)

                    # 检查 JSON-RPC 错误
                    if 'error' in data:
                        error_code = data['error'].get('code', 'N/A')
                        error_msg = data['error'].get('message', 'Unknown error')
                        error_data = data['error'].get('data', '')
                        print(f"[MCP ERROR] JSON-RPC error {error_code}: {error_msg}")
                        if error_data:
                            print(f"[MCP ERROR] Error details: {error_data}")
                        return None

                    return data

            # 如果没有找到 "data: " 行，尝试直接解析整个响应
            data = json.loads(response_text)

            # 检查 JSON-RPC 错误
            if 'error' in data:
                error_code = data['error'].get('code', 'N/A')
                error_msg = data['error'].get('message', 'Unknown error')
                error_data = data['error'].get('data', '')
                print(f"[MCP ERROR] JSON-RPC error {error_code}: {error_msg}")
                if error_data:
                    print(f"[MCP ERROR] Error details: {error_data}")
                return None

            return data

        except json.JSONDecodeError as e:
            print(f"[MCP ERROR] Failed to parse SSE response: {e}")
            print(f"[MCP DEBUG] Response text: {response_text[:200]}")
            return None
        except Exception as e:
            print(f"[MCP ERROR] Unexpected error parsing SSE: {e}")
            return None

    def _parse_news_response(self, data: Dict, coin: str) -> List[Dict]:
        """解析新闻响应数据"""
        news_list = []

        try:
            # 调试：打印实际响应结构
            print(f"[MCP DEBUG] News response data keys: {list(data.keys())}")
            if 'result' in data:
                print(f"[MCP DEBUG] Result type: {type(data['result'])}")
                print(f"[MCP DEBUG] Result content: {str(data['result'])[:200]}")

            # 根据实际MCP响应格式解析
            # 这里提供一个通用的解析逻辑
            if 'result' in data and isinstance(data['result'], list):
                for item in data['result']:
                    news_item = {
                        'title': item.get('title', ''),
                        'summary': item.get('summary', item.get('description', '')),
                        'published_time': item.get('published_time', item.get('date', '')),
                        'sentiment': self._analyze_sentiment(item.get('title', '') + ' ' + item.get('summary', '')),
                        'source': item.get('source', 'Unknown'),
                        'url': item.get('url', '')
                    }
                    news_list.append(news_item)

            return news_list[:5]  # 限制返回5条

        except Exception as e:
            print(f"[MCP ERROR] Failed to parse news response: {e}")
            import traceback
            traceback.print_exc()
            return []
    
    def _parse_indicators_response(self, data: Dict) -> Dict:
        """解析技术指标响应数据"""
        try:
            # 调试：打印实际响应结构
            print(f"[MCP DEBUG] Indicators response data keys: {list(data.keys())}")
            if 'result' in data:
                print(f"[MCP DEBUG] Result type: {type(data['result'])}")
                print(f"[MCP DEBUG] Result content: {str(data['result'])[:200]}")

            if 'result' in data:
                result = data['result']

                # 标准化指标名称
                indicators = {
                    'rsi': result.get('rsi', result.get('RSI', 50)),
                    'macd': result.get('macd', result.get('MACD', 0)),
                    'macd_signal': result.get('macd_signal', result.get('MACD_signal', 0)),
                    'macd_histogram': result.get('macd_histogram', result.get('MACD_histogram', 0)),
                    'ema_12': result.get('ema_12', result.get('EMA_12', 0)),
                    'ema_26': result.get('ema_26', result.get('EMA_26', 0)),
                    'sma_20': result.get('sma_20', result.get('SMA_20', 0)),
                    'bollinger_upper': result.get('bollinger_upper', result.get('BB_upper', 0)),
                    'bollinger_middle': result.get('bollinger_middle', result.get('BB_middle', 0)),
                    'bollinger_lower': result.get('bollinger_lower', result.get('BB_lower', 0)),
                }

                return indicators

            return {}

        except Exception as e:
            print(f"[MCP ERROR] Failed to parse indicators response: {e}")
            import traceback
            traceback.print_exc()
            return {}
    
    def _parse_historical_response(self, data: Dict) -> List[Dict]:
        """解析历史数据响应"""
        try:
            if 'result' in data and isinstance(data['result'], list):
                return data['result']
            return []
        except Exception as e:
            print(f"[MCP ERROR] Failed to parse historical response: {e}")
            return []
    
    def _analyze_sentiment(self, text: str) -> str:
        """
        简单的情绪分析
        
        Returns:
            'positive', 'negative', 'neutral'
        """
        text_lower = text.lower()
        
        # 积极关键词
        positive_keywords = ['surge', 'rally', 'bullish', 'gain', 'rise', 'up', 'high', 
                           'breakthrough', 'record', 'soar', 'pump', 'moon', 'bull']
        
        # 消极关键词
        negative_keywords = ['crash', 'drop', 'bearish', 'fall', 'down', 'low', 
                           'decline', 'plunge', 'dump', 'bear', 'collapse', 'fear']
        
        positive_count = sum(1 for word in positive_keywords if word in text_lower)
        negative_count = sum(1 for word in negative_keywords if word in text_lower)
        
        if positive_count > negative_count:
            return 'positive'
        elif negative_count > positive_count:
            return 'negative'
        else:
            return 'neutral'
    
    def health_check(self) -> bool:
        """
        检查MCP服务器健康状态

        对于 mcp-aktools 服务器，如果会话建立成功，就认为服务器可用
        因为 mcp-aktools 可能不支持标准的 MCP 协议方法（如 tools/list）

        Returns:
            True if server is healthy, False otherwise
        """
        # 如果会话已经建立，说明服务器可用
        if self.session_id:
            print(f"[MCP] Health check successful (session established)")
            return True

        # 如果会话未建立，尝试建立会话
        if self._establish_session():
            print(f"[MCP] Health check successful (session established)")
            return True

        print(f"[MCP WARNING] Health check failed (unable to establish session)")
        return False

