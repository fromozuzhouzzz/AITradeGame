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

    def __init__(self, server_url: str = None, base_url: str = None, disable_proxy: bool = False):
        """
        初始化MCP客户端

        Args:
            server_url: MCP服务器完整URL（包含 /mcp 路径）
            base_url: MCP服务器基础URL（不包含 /mcp 路径，兼容旧接口）
        """
        # 兼容旧接口：如果提供 base_url，自动添加 /mcp
        primary_default = "http://127.0.0.1:8808/mcp"
        backup_default = "http://27.106.106.133:8808/mcp"
        self.server_url_candidates: List[str] = []

        if base_url:
            base = base_url.rstrip('/')
            # 兼容已经包含 /mcp 的地址，避免出现 /mcp/mcp
            if base.endswith('/mcp'):
                resolved_url = base
            else:
                resolved_url = f"{base}/mcp"

            if "27.106.106.133" in resolved_url or "127.0.0.1" in resolved_url:
                self.server_url_candidates = [primary_default, backup_default]
            else:
                self.server_url_candidates = [resolved_url]
        elif server_url:
            resolved_url = server_url.rstrip('/')
            if "27.106.106.133" in resolved_url or "127.0.0.1" in resolved_url:
                self.server_url_candidates = [primary_default, backup_default]
            else:
                self.server_url_candidates = [resolved_url]
        else:
            self.server_url_candidates = [primary_default, backup_default]

        self.server_url = self.server_url_candidates[0]

        self.client = None
        self._connected = False
        self._event_loop = None

        # 缓存机制
        self._news_cache = {}
        self._news_cache_time = {}
        self._cache_duration = 300  # 新闻缓存5分钟

        print(f"[MCP] Initialized FastMCP client for: {self.server_url}")

        # 同步初始化：建立连接
        try:
            self._sync_connect()
        except Exception as e:
            print(f"[MCP ERROR] Failed to initialize: {e}")
            self._connected = False
    
    def _sync_connect(self):
        """
        同步方式建立 MCP 连接
        创建新的事件循环并在其中运行异步连接
        """
        try:
            self._event_loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self._event_loop)

            max_retries = 3
            last_error = None
            candidates = getattr(self, "server_url_candidates", None) or [self.server_url]

            for server_index, candidate in enumerate(candidates, start=1):
                self.server_url = candidate
                for attempt in range(1, max_retries + 1):
                    try:
                        print(
                            f"[MCP] Trying server {self.server_url} "
                            f"(candidate {server_index}/{len(candidates)}, attempt {attempt}/{max_retries})"
                        )
                        self._event_loop.run_until_complete(
                            asyncio.wait_for(self._async_connect(), timeout=30.0)
                        )
                        return
                    except Exception as e:
                        print(f"[MCP ERROR] Failed to connect to {self.server_url} on attempt {attempt}/{max_retries}: {e}")
                        self._connected = False
                        last_error = e
                        if attempt == max_retries:
                            break

            if last_error is not None:
                raise last_error
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
                # FastMCP 可能返回列表或对象
                if isinstance(tools, list):
                    print(f"[MCP] Available tools: {len(tools)}")
                    for tool in tools:
                        tool_name = tool.name if hasattr(tool, 'name') else str(tool)
                        tool_desc = tool.description if hasattr(tool, 'description') else ''
                        print(f"[MCP]   - {tool_name}: {tool_desc}")
                elif hasattr(tools, 'tools'):
                    print(f"[MCP] Available tools: {len(tools.tools)}")
                    for tool in tools.tools:
                        print(f"[MCP]   - {tool.name}: {tool.description}")
                else:
                    print(f"[MCP] Tools list format: {type(tools)}")
            except Exception as e:
                print(f"[MCP WARNING] Could not list tools: {e}")
                
        except Exception as e:
            print(f"[MCP ERROR] Connection failed: {e}")
            self._connected = False
            raise
    
    def health_check(self) -> bool:
        """
        健康检查：验证 MCP 服务器是否可用

        Returns:
            True 如果服务器可用，False 否则
        """
        return self._connected

    def __bool__(self) -> bool:
        """
        支持布尔判断：if self.mcp_client:

        Returns:
            True 如果客户端已连接，False 否则
        """
        return self._connected

    def _run_async(self, coro, timeout: float = 30.0):
        """
        在事件循环中运行异步协程（带超时保护）

        Args:
            coro: 异步协程
            timeout: 超时时间（秒），默认30秒

        Returns:
            协程的返回值

        Raises:
            asyncio.TimeoutError: 如果操作超时
            Exception: 其他异常
        """
        if not self._event_loop:
            self._event_loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self._event_loop)

        try:
            # 使用 asyncio.wait_for 添加超时保护
            return self._event_loop.run_until_complete(
                asyncio.wait_for(coro, timeout=timeout)
            )
        except asyncio.TimeoutError:
            print(f"[MCP ERROR] Operation timed out after {timeout} seconds")
            print(f"[MCP HINT] This may indicate:")
            print(f"           1. MCP server is overloaded or unresponsive")
            print(f"           2. Network connection is slow")
            print(f"           3. The requested operation is taking too long")
            raise
        except Exception as e:
            print(f"[MCP ERROR] Async operation failed: {e}")
            import traceback
            traceback.print_exc()
            raise
    
    async def _ensure_client_connected(self):
        """
        确保 FastMCP Client 已连接；如果断开则尝试重连。

        说明：
        - FastMCP Client 在会话断开后，其 session 属性会变为 None，
          此时访问 client.session 或调用工具都会抛出 RuntimeError:
          "Client is not connected. Use the 'async with client:' context manager first."
        - 这里通过检测该异常并调用内部断开/重连逻辑，恢复可用连接。
        """

        # 如果还没有 client 实例，先创建
        if self.client is None:
            self.client = Client(self.server_url)

        # 检查当前 session 是否可用
        try:
            # 访问属性会在未连接时抛 RuntimeError
            _ = self.client.session
            return
        except RuntimeError as e:
            if "Client is not connected" not in str(e):
                # 其他 RuntimeError 直接向上抛出
                raise

        # 尝试强制断开并重新连接
        try:
            # 强制重置内部会话状态（即使 session 任务已经结束）
            try:
                await self.client._disconnect(force=True)  # type: ignore[attr-defined]
            except Exception:
                # 忽略内部断开错误，继续尝试重连
                pass

            await self.client.__aenter__()
            self._connected = True
            print(f"[MCP] Reconnected to MCP server: {self.server_url}")
        except Exception as e:
            self._connected = False
            print(f"[MCP ERROR] Reconnect failed: {e}")
            raise

    async def _call_tool_with_reconnect(self, name: str, arguments: Dict, max_retries: int = 3) -> Optional[object]:
        """
        调用 MCP 工具时自动处理断线重连。

        行为：
        - 如果当前 client/session 未连接，则尝试重连
        - 调用或重连过程中出现错误时，最多重试 max_retries 次
        - 如果所有重试仍失败，返回 None，由上层决定如何降级
        """

        # 确保有 Client 实例
        if self.client is None:
            self.client = Client(self.server_url)

        last_error: Optional[Exception] = None

        for attempt in range(1, max_retries + 1):
            try:
                await self._ensure_client_connected()
                return await self.client.call_tool(name, arguments)
            except RuntimeError as e:
                # 仅针对 "Client is not connected" 的 RuntimeError 进行重试
                if "Client is not connected" not in str(e):
                    raise
                print(f"[MCP WARNING] Client disconnected when calling {name} (attempt {attempt}/{max_retries}), attempting reconnect...")
                last_error = e
            except Exception as e:
                # 包括 HTTPStatusError、网络错误等
                print(f"[MCP ERROR] Error when calling {name} on attempt {attempt}/{max_retries}: {e}")
                last_error = e
                self._connected = False
                # 尝试强制断开，给下次重试一个干净的状态
                try:
                    await self.client._disconnect(force=True)  # type: ignore[attr-defined]
                except Exception:
                    pass

            # 如果还没到最后一次尝试，稍微等待后重试
            if attempt < max_retries:
                try:
                    await asyncio.sleep(1.0)
                except Exception:
                    pass

        print(f"[MCP ERROR] Failed to call {name} after {max_retries} attempts: {last_error}")
        return None
    
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
        
        # 运行异步方法（30秒超时 - 新闻获取通常较快）
        try:
            return self._run_async(self._async_get_crypto_news(coin, limit), timeout=30.0)
        except asyncio.TimeoutError:
            print(f"[MCP TIMEOUT] News fetch for {coin} timed out after 30s, skipping...")
            return []
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
        # 首选：尝试币种专属新闻工具 stock_news
        try:
            # 先调用全局财经快讯工具 stock_news_global
            print(f"[MCP DEBUG] Calling stock_news_global tool for {coin}")

            global_result = await self._call_tool_with_reconnect(
                "stock_news_global",
                {}
            )

            if global_result is None:
                raise RuntimeError("stock_news_global returned None result")

            print(f"[MCP DEBUG] Global news tool call successful, result type: {type(global_result)}")

            # 复用相同的解析逻辑，将全局新闻也映射到当前币种
            news_list = self._parse_news_result(global_result, coin)

            cache_key = f"{coin}_{limit}"
            self._news_cache[cache_key] = news_list
            self._news_cache_time[cache_key] = datetime.now()

            print(f"[MCP] Retrieved {len(news_list)} global news items for {coin}")
            return news_list

        except Exception as e:
            # 币种专属新闻失败时，记录错误并尝试全局新闻兜底
            print(f"[MCP ERROR] Failed to call stock_news_global tool for {coin}: {e}")
            import traceback
            traceback.print_exc()

        # 兜底：尝试全局财经快讯工具 stock_news_global
        try:
            print(f"[MCP DEBUG] Falling back to stock_news tool: symbol={coin}")

            # 使用带自动重连的封装调用币种专属新闻工具
            result = await self._call_tool_with_reconnect(
                "stock_news",
                {"keyword": coin, "news_count": limit}
            )

            if result is None:
                return []

            print(f"[MCP DEBUG] Tool call successful, result type: {type(result)}")

            # 解析结果
            news_list = self._parse_news_result(result, coin)

            cache_key = f"{coin}_{limit}"
            self._news_cache[cache_key] = news_list
            self._news_cache_time[cache_key] = datetime.now()

            print(f"[MCP] Retrieved {len(news_list)} news items for {coin}")
            return news_list

        except Exception as e:
            print(f"[MCP ERROR] Failed to call stock_news fallback for {coin}: {e}")
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
                            for i, item in enumerate(news_items, 1):
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
            return self._run_async(self._async_get_technical_indicators(coin, timeframe), timeout=30.0)
        except asyncio.TimeoutError:
            print(f"[MCP TIMEOUT] Indicators fetch for {coin} timed out after 30s, skipping...")
            return {}
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
        try:
            # 转换时间框架格式
            bar = timeframe.upper().replace('D', 'D').replace('H', 'H').replace('M', 'M')

            print(f"[MCP DEBUG] Calling okx_prices tool: instId={coin}-USDT, bar={bar}, limit=30")

            # 使用 FastMCP 客户端调用工具（带自动重连）
            result = await self._call_tool_with_reconnect(
                "okx_prices",
                {"instId": f"{coin}-USDT", "bar": bar, "limit": 30}
            )

            if result is None:
                return {}

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
        解析技术指标结果（支持 JSON 和 CSV 格式）

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
                            # 如果不是 JSON，尝试解析 CSV 格式
                            print(f"[MCP DEBUG] Result is not JSON, attempting CSV parse: {text[:100]}")
                            indicators = self._parse_csv_indicators(text)

            return indicators

        except Exception as e:
            print(f"[MCP ERROR] Failed to parse indicators result: {e}")
            return {}

    def _parse_csv_indicators(self, csv_text: str) -> Dict:
        """
        解析 CSV 格式的技术指标数据

        CSV 格式示例：
        时间,开盘,收盘,最高,最低,成交量,成交额,MACD,DIF,DEA,KDJ.K,KDJ.D,KDJ.J,RSI,BOLL.U,BOLL.M,BOLL.L
        2025-09-23 16:00:00,4180.57,4165.75,4207.30,4073.91,133328.80,554586458.62,-96.18,-17.67,30.42,24.65,31.86,10.23,38.86,4700.00,4100.00,3500.00

        Args:
            csv_text: CSV 格式的字符串

        Returns:
            解析后的技术指标字典
        """
        indicators = {}

        try:
            lines = csv_text.strip().split('\n')
            if len(lines) < 2:
                print(f"[MCP WARNING] CSV data has less than 2 lines")
                return {}

            # 解析表头
            headers = [h.strip() for h in lines[0].split(',')]

            # 解析最后一行数据（最新的 K 线）
            values = [v.strip() for v in lines[-1].split(',')]

            if len(headers) != len(values):
                print(f"[MCP WARNING] CSV header/value count mismatch: {len(headers)} vs {len(values)}")
                return {}

            # 构建指标字典
            for header, value in zip(headers, values):
                header = header.strip()
                try:
                    # 尝试转换为浮点数
                    if header not in ['时间']:  # 跳过时间字段
                        indicators[header] = float(value)
                except ValueError:
                    # 如果转换失败，保存为字符串
                    indicators[header] = value

            # 映射到标准指标名称
            indicators_mapped = {
                'rsi': indicators.get('RSI'),
                'macd': indicators.get('MACD'),
                'macd_signal': indicators.get('DEA'),  # DEA 是 MACD 信号线
                'macd_histogram': indicators.get('DIF'),  # DIF 是 MACD 直方图
                'bollinger_upper': indicators.get('BOLL.U'),
                'bollinger_middle': indicators.get('BOLL.M'),
                'bollinger_lower': indicators.get('BOLL.L'),
                'kdj_k': indicators.get('KDJ.K'),
                'kdj_d': indicators.get('KDJ.D'),
                'kdj_j': indicators.get('KDJ.J'),
                'open': indicators.get('开盘'),
                'close': indicators.get('收盘'),
                'high': indicators.get('最高'),
                'low': indicators.get('最低'),
                'volume': indicators.get('成交量'),
                'amount': indicators.get('成交额'),
            }

            # 过滤掉 None 值
            indicators_mapped = {k: v for k, v in indicators_mapped.items() if v is not None}

            print(f"[MCP] Successfully parsed CSV indicators: {list(indicators_mapped.keys())}")
            return indicators_mapped

        except Exception as e:
            print(f"[MCP ERROR] Failed to parse CSV indicators: {e}")
            import traceback
            traceback.print_exc()
            return {}

    def get_okx_loan_ratios(self, coin: str) -> Dict:
        """
        获取 OKX 加密货币借贷比率（同步接口）

        Args:
            coin: 币种符号（如 BTC, ETH）

        Returns:
            借贷比率数据字典
        """
        try:
            return self._run_async(self._async_get_okx_loan_ratios(coin), timeout=30.0)
        except asyncio.TimeoutError:
            print(f"[MCP TIMEOUT] Loan ratios fetch for {coin} timed out after 30s, skipping...")
            return {}
        except Exception as e:
            print(f"[MCP ERROR] Failed to get loan ratios for {coin}: {e}")
            return {}

    async def _async_get_okx_loan_ratios(self, coin: str) -> Dict:
        """
        异步获取 OKX 加密货币借贷比率

        Args:
            coin: 币种符号

        Returns:
            借贷比率数据字典
        """
        try:
            # 尝试不同的参数名称
            print(f"[MCP DEBUG] Calling okx_loan_ratios tool: symbol={coin}")

            result = await self._call_tool_with_reconnect(
                "okx_loan_ratios",
                {"symbol": coin}
            )

            if result is None:
                return {}

            print(f"[MCP DEBUG] Tool call successful, result type: {type(result)}")

            # 解析结果
            loan_data = self._parse_tool_result(result)

            print(f"[MCP] Retrieved loan ratios for {coin}")
            return loan_data

        except Exception as e:
            print(f"[MCP ERROR] Failed to call okx_loan_ratios tool: {e}")
            import traceback
            traceback.print_exc()
            return {}

    def get_okx_taker_volume(self, coin: str) -> Dict:
        """
        获取 OKX 加密货币主动买卖交易量（同步接口）

        Args:
            coin: 币种符号（如 BTC, ETH）

        Returns:
            交易量数据字典
        """
        try:
            return self._run_async(self._async_get_okx_taker_volume(coin), timeout=30.0)
        except asyncio.TimeoutError:
            print(f"[MCP TIMEOUT] Taker volume fetch for {coin} timed out after 30s, skipping...")
            return {}
        except Exception as e:
            print(f"[MCP ERROR] Failed to get taker volume for {coin}: {e}")
            return {}

    async def _async_get_okx_taker_volume(self, coin: str) -> Dict:
        """
        异步获取 OKX 加密货币主动买卖交易量

        Args:
            coin: 币种符号

        Returns:
            交易量数据字典
        """
        try:
            # 尝试不同的参数名称
            print(f"[MCP DEBUG] Calling okx_taker_volume tool: symbol={coin}")

            result = await self._call_tool_with_reconnect(
                "okx_taker_volume",
                {"symbol": coin}
            )

            if result is None:
                return {}

            print(f"[MCP DEBUG] Tool call successful, result type: {type(result)}")

            # 解析结果
            volume_data = self._parse_tool_result(result)

            print(f"[MCP] Retrieved taker volume for {coin}")
            return volume_data

        except Exception as e:
            print(f"[MCP ERROR] Failed to call okx_taker_volume tool: {e}")
            import traceback
            traceback.print_exc()
            return {}

    def get_binance_ai_report(self, coin: str) -> Dict:
        """
        获取币安对加密货币的 AI 分析报告（同步接口）

        Args:
            coin: 币种符号（如 BTC, ETH）

        Returns:
            AI 分析报告字典
        """
        try:
            return self._run_async(self._async_get_binance_ai_report(coin), timeout=30.0)
        except asyncio.TimeoutError:
            print(f"[MCP TIMEOUT] Binance AI report fetch for {coin} timed out after 30s, skipping...")
            return {}
        except Exception as e:
            print(f"[MCP ERROR] Failed to get Binance AI report for {coin}: {e}")
            return {}

    async def _async_get_binance_ai_report(self, coin: str) -> Dict:
        """
        异步获取币安对加密货币的 AI 分析报告

        Args:
            coin: 币种符号

        Returns:
            AI 分析报告字典
        """
        try:
            print(f"[MCP DEBUG] Calling binance_ai_report tool: symbol={coin}")

            result = await self._call_tool_with_reconnect(
                "binance_ai_report",
                {"symbol": coin}
            )

            if result is None:
                return {}

            print(f"[MCP DEBUG] Tool call successful, result type: {type(result)}")

            # 解析结果
            ai_report = self._parse_tool_result(result)

            print(f"[MCP] Retrieved Binance AI report for {coin}")
            return ai_report

        except Exception as e:
            print(f"[MCP ERROR] Failed to call binance_ai_report tool: {e}")
            import traceback
            traceback.print_exc()
            return {}

    def _parse_tool_result(self, result) -> Dict:
        """
        解析 MCP 工具调用结果（通用方法）

        Args:
            result: FastMCP 工具调用结果

        Returns:
            解析后的数据字典
        """
        data = {}

        try:
            # FastMCP 结果通常包含 content 列表
            if hasattr(result, 'content'):
                for content_item in result.content:
                    if hasattr(content_item, 'text'):
                        text = content_item.text
                        # 尝试解析 JSON
                        try:
                            data = json.loads(text)
                        except json.JSONDecodeError:
                            # 如果不是 JSON，返回原始文本
                            data = {'raw_text': text}

            return data

        except Exception as e:
            print(f"[MCP ERROR] Failed to parse tool result: {e}")
            return {}

    def __del__(self):
        """
        清理资源
        """
        try:
            # 检查属性是否存在（防止初始化失败时的错误）
            if hasattr(self, '_event_loop') and hasattr(self, 'client') and hasattr(self, '_connected'):
                if self._event_loop and self.client and self._connected:
                    try:
                        self._event_loop.run_until_complete(self.client.__aexit__(None, None, None))
                    except:
                        pass

                    try:
                        self._event_loop.close()
                    except:
                        pass
        except:
            pass

