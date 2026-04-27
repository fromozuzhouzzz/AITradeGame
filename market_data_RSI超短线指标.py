"""
Market data module - Multi-API integration with robust failover
Supports: Binance (multiple endpoints), CoinGecko, Kraken, Coinbase
Enhanced with persistent caching for 90%+ API call reduction
Integrated with MCP AkTools server for enhanced technical indicators and news
"""
import requests
import time
import urllib3
from typing import Dict, List, Optional, Callable
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from market_data_cache import MarketDataCache
from mcp_client import MCPAkToolsClient

# Disable SSL warnings for development (remove in production)
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

class MarketDataFetcher:
    """Fetch real-time market data with multi-API failover support"""

    def __init__(self, proxy: Optional[str] = None, use_persistent_cache: bool = True,
                 mcp_server_url: Optional[str] = None, enable_mcp: bool = True):
        """
        Initialize market data fetcher with multiple API endpoints

        Args:
            proxy: Optional proxy URL (e.g., "http://proxy.com:8080" or "socks5://proxy.com:1080")
            use_persistent_cache: Enable persistent database cache (default: True)
            mcp_server_url: MCP AkTools server URL (default: http://27.106.106.133:8808/mcp)
            enable_mcp: Enable MCP integration for enhanced data (default: True)
        """
        # API endpoints with priority order
        self.api_endpoints = {
            'binance': [
                "https://api.binance.com/api/v3",
                "https://api1.binance.com/api/v3",
                "https://api2.binance.com/api/v3",
                "https://api3.binance.com/api/v3",
            ],
            'coingecko': "https://api.coingecko.com/api/v3",
            'kraken': "https://api.kraken.com/0/public",
            'coinbase': "https://api.coinbase.com/v2"
        }

        # Proxy configuration
        self.proxies = {'http': proxy, 'https': proxy} if proxy else None

        # Session with retry strategy and SSL configuration
        self.session = self._create_session()

        # MCP AkTools client integration
        self.enable_mcp = enable_mcp
        self.mcp_client = None
        if enable_mcp:
            try:
                # 默认 MCP 服务器地址（不包含 /mcp 路径）
                mcp_url = mcp_server_url or "http://27.106.106.133:8808"
                self.mcp_client = MCPAkToolsClient(base_url=mcp_url)
                if self.mcp_client.health_check():
                    print("[INFO] MCP AkTools server connected successfully")
                else:
                    print("[WARNING] MCP server health check failed, will use fallback data sources")
                    self.mcp_client = None
            except Exception as e:
                print(f"[WARNING] Failed to initialize MCP client: {e}")
                print("[INFO] Continuing with standard data sources only")
                self.mcp_client = None

        # Symbol mappings for different exchanges
        self.binance_symbols = {
            'ETH': 'ETHUSDT',
            'SOL': 'SOLUSDT',
            'BNB': 'BNBUSDT',
            'XRP': 'XRPUSDT'
        }

        self.coingecko_mapping = {
            'ETH': 'ethereum',
            'SOL': 'solana',
            'BNB': 'binancecoin',
            'XRP': 'ripple'
        }

        self.kraken_symbols = {
            'ETH': 'XETHZUSD',
            'SOL': 'SOLUSD',
            'BNB': 'BNBUSD',
            'XRP': 'XXRPZUSD'
        }

        self.coinbase_symbols = {
            'ETH': 'ETH-USD',
            'SOL': 'SOL-USD',
            'BNB': 'BNB-USD',
            'XRP': 'XRP-USD'
        }

        # Memory cache system (for current prices only)
        self._cache = {}
        self._cache_time = {}
        # 优化：将缓存时长从5秒延长到30秒
        # 原因：
        # 1. 避免前端API请求频繁触发新的外部API调用
        # 2. 30秒的缓存对于加密货币价格来说仍然足够实时
        # 3. 配合前端30秒刷新间隔，可以有效利用缓存
        self._cache_duration = 30  # Cache for 30 seconds (原值: 5)

        # Session-level snapshot cache (for multi-model scenarios)
        self._session_snapshot = {}  # {session_id: {data, timestamp}}
        self._current_session_id = None
        self._snapshot_duration = 300  # Snapshot valid for 5 minutes

        # Persistent cache system (for historical data and indicators)
        self.persistent_cache = MarketDataCache('trading_bot.db') if use_persistent_cache else None
        self._cache_hits = 0
        self._cache_misses = 0

        # API health tracking
        self._api_failures = {
            'binance': 0,
            'coingecko': 0,
            'kraken': 0,
            'coinbase': 0
        }
        self._last_successful_api = None

        # Performance monitoring
        self._api_call_count = 0
        self._snapshot_hit_count = 0

        # 记录每个币种上一次成功计算得到的短周期 RSI(9,15m)，
        # 当本次 15 分钟 K 线获取失败或数量不足时，可以回退使用该值
        self._last_rsi_9_15m = {}


    # ============ Session-level Snapshot Management ============

    def start_session(self, session_id: str = None) -> str:
        """
        Start a new data snapshot session for multi-model scenarios

        Args:
            session_id: Optional custom session ID (default: timestamp-based)

        Returns:
            The session ID
        """
        if session_id is None:
            session_id = f"session_{int(time.time() * 1000)}"

        self._current_session_id = session_id
        self._session_snapshot[session_id] = {
            'data': {},
            'timestamp': time.time(),
            'api_calls': 0
        }

        print(f"[SESSION] Started snapshot session: {session_id}")
        return session_id

    def end_session(self, session_id: str = None):
        """
        End a snapshot session and clean up old sessions

        Args:
            session_id: Session ID to end (default: current session)
        """
        if session_id is None:
            session_id = self._current_session_id

        if session_id and session_id in self._session_snapshot:
            snapshot_info = self._session_snapshot[session_id]
            print(f"[SESSION] Ended session {session_id}: "
                  f"{snapshot_info['api_calls']} API calls, "
                  f"{self._snapshot_hit_count} snapshot hits")

        self._current_session_id = None

        # Clean up old sessions (older than snapshot_duration)
        current_time = time.time()
        expired_sessions = [
            sid for sid, data in self._session_snapshot.items()
            if current_time - data['timestamp'] > self._snapshot_duration
        ]

        for sid in expired_sessions:
            del self._session_snapshot[sid]
            print(f"[SESSION] Cleaned up expired session: {sid}")

    def get_session_snapshot(self, session_id: str = None) -> Optional[Dict]:
        """
        Get the data snapshot for a session

        Args:
            session_id: Session ID (default: current session)

        Returns:
            Snapshot data or None if not found/expired
        """
        if session_id is None:
            session_id = self._current_session_id

        if not session_id or session_id not in self._session_snapshot:
            return None

        snapshot = self._session_snapshot[session_id]

        # Check if snapshot is still valid
        if time.time() - snapshot['timestamp'] > self._snapshot_duration:
            print(f"[SESSION] Snapshot {session_id} expired")
            del self._session_snapshot[session_id]
            return None

        return snapshot['data']

    def update_session_snapshot(self, key: str, data: any, session_id: str = None):
        """
        Update the snapshot data for current session

        Args:
            key: Data key (e.g., 'market_state', 'prices')
            data: Data to store
            session_id: Session ID (default: current session)
        """
        if session_id is None:
            session_id = self._current_session_id

        if session_id and session_id in self._session_snapshot:
            self._session_snapshot[session_id]['data'][key] = data
            self._session_snapshot[session_id]['api_calls'] += 1

    def _create_session(self) -> requests.Session:
        """Create a requests session with retry strategy and SSL handling"""
        session = requests.Session()

        # Retry strategy: 3 retries with exponential backoff
        retry_strategy = Retry(
            total=3,
            backoff_factor=0.5,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["GET"]
        )

        adapter = HTTPAdapter(max_retries=retry_strategy)
        session.mount("http://", adapter)
        session.mount("https://", adapter)

        # Set default headers
        session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Accept': 'application/json'
        })

        return session

    def get_current_prices(self, coins: List[str]) -> Dict[str, float]:
        """
        Get current prices with multi-API failover
        Priority: Session Snapshot -> Cache -> Binance -> CoinGecko -> Kraken -> Coinbase

        OPTIMIZATION: Now checks session snapshot first to avoid redundant API calls
        """
        # PRIORITY 1: Check session snapshot first (for multi-model scenarios)
        if self._current_session_id:
            snapshot = self.get_session_snapshot()
            if snapshot and 'market_state' in snapshot:
                # Extract prices from market_state
                prices = {}
                for coin in coins:
                    if coin in snapshot['market_state']:
                        prices[coin] = {
                            'price': snapshot['market_state'][coin]['price'],
                            'change_24h': snapshot['market_state'][coin].get('change_24h', 0)
                        }
                if len(prices) == len(coins):
                    # print(f"[PRICES] Using session snapshot (avoiding API call)")
                    return prices

        # PRIORITY 2: Check local cache
        cache_key = 'prices_' + '_'.join(sorted(coins))
        if cache_key in self._cache:
            if time.time() - self._cache_time[cache_key] < self._cache_duration:
                # print(f"[PRICES] Using local cache")
                return self._cache[cache_key]

        # Try APIs in priority order
        api_methods = [
            ('binance', self._get_prices_from_binance),
            ('coingecko', self._get_prices_from_coingecko),
            ('kraken', self._get_prices_from_kraken),
            ('coinbase', self._get_prices_from_coinbase),
        ]

        # If we have a last successful API, try it first
        if self._last_successful_api:
            api_methods = sorted(
                api_methods,
                key=lambda x: 0 if x[0] == self._last_successful_api else 1
            )

        # PRIORITY 3: Fetch from external APIs
        for api_name, api_method in api_methods:
            try:
                print(f"[API CALL] Fetching prices from {api_name.upper()}...")
                prices = api_method(coins)

                if prices and len(prices) > 0:
                    # Success! Update cache and tracking
                    self._cache[cache_key] = prices
                    self._cache_time[cache_key] = time.time()
                    self._api_failures[api_name] = 0
                    self._last_successful_api = api_name
                    print(f"[API SUCCESS] Fetched {len(prices)} prices from {api_name.upper()}")
                    return prices
                else:
                    print(f"[API WARNING] {api_name.upper()} returned empty data")

            except Exception as e:
                self._api_failures[api_name] += 1
                print(f"[API ERROR] {api_name.upper()} failed (attempt #{self._api_failures[api_name]}): {e}")
                continue

        # All APIs failed - return empty prices with warning
        print("[API CRITICAL] All APIs failed! Returning empty data.")
        return {coin: {'price': 0, 'change_24h': 0} for coin in coins}

    def _get_prices_from_binance(self, coins: List[str]) -> Dict[str, float]:
        """Fetch prices from Binance with multiple endpoint fallback"""
        symbols = [self.binance_symbols.get(coin) for coin in coins if coin in self.binance_symbols]

        if not symbols:
            return {}

        # Try each Binance endpoint
        for endpoint in self.api_endpoints['binance']:
            try:
                # Build symbols parameter
                symbols_param = '[' + ','.join([f'"{s}"' for s in symbols]) + ']'

                response = self.session.get(
                    f"{endpoint}/ticker/24hr",
                    params={'symbols': symbols_param},
                    timeout=8,
                    proxies=self.proxies,
                    verify=False  # Disable SSL verification to avoid SSL errors
                )

                # Check for region restriction (451)
                if response.status_code == 451:
                    print(f"[WARNING] Binance endpoint {endpoint} returned 451 (region restricted)")
                    continue

                response.raise_for_status()
                data = response.json()

                # Parse data
                prices = {}
                for item in data:
                    symbol = item['symbol']
                    for coin, binance_symbol in self.binance_symbols.items():
                        if binance_symbol == symbol:
                            prices[coin] = {
                                'price': float(item['lastPrice']),
                                'change_24h': float(item['priceChangePercent'])
                            }
                            break

                if prices:
                    return prices

            except requests.exceptions.RequestException as e:
                print(f"[DEBUG] Binance endpoint {endpoint} failed: {e}")
                continue

        raise Exception("All Binance endpoints failed or are region-restricted")

    def _get_klines_from_binance(self, coin: str, interval: str = "15m", limit: int = 50) -> List[float]:
        """Fetch recent kline close prices from Binance for a specific coin and interval."""
        symbol = self.binance_symbols.get(coin)
        if not symbol:
            return []

        for endpoint in self.api_endpoints['binance']:
            try:
                response = self.session.get(
                    f"{endpoint}/klines",
                    params={"symbol": symbol, "interval": interval, "limit": limit},
                    timeout=8,
                    proxies=self.proxies,
                    verify=False
                )

                # Check for region restriction (451)
                if response.status_code == 451:
                    print(f"[WARNING] Binance klines endpoint {endpoint} returned 451 (region restricted)")
                    continue

                response.raise_for_status()
                data = response.json()

                closes: List[float] = []
                for item in data:
                    # item format: [openTime, open, high, low, close, volume, ...]
                    try:
                        closes.append(float(item[4]))
                    except (ValueError, TypeError, IndexError):
                        continue

                if closes:
                    return closes

            except requests.exceptions.RequestException as e:
                print(f"[DEBUG] Binance klines endpoint {endpoint} failed: {e}")
                continue

        print(f"[WARNING] All Binance klines endpoints failed for {coin}")
        return []

    def _get_prices_from_coingecko(self, coins: List[str]) -> Dict[str, float]:
        """Fetch prices from CoinGecko with SSL error handling"""
        coin_ids = [self.coingecko_mapping.get(coin, coin.lower()) for coin in coins]

        response = self.session.get(
            f"{self.api_endpoints['coingecko']}/simple/price",
            params={
                'ids': ','.join(coin_ids),
                'vs_currencies': 'usd',
                'include_24hr_change': 'true'
            },
            timeout=12,
            proxies=self.proxies,
            verify=False  # Disable SSL verification to fix SSL: UNEXPECTED_EOF_WHILE_READING
        )
        response.raise_for_status()
        data = response.json()

        prices = {}
        for coin in coins:
            coin_id = self.coingecko_mapping.get(coin, coin.lower())
            if coin_id in data:
                prices[coin] = {
                    'price': data[coin_id]['usd'],
                    'change_24h': data[coin_id].get('usd_24h_change', 0)
                }

        return prices

    def _get_prices_from_kraken(self, coins: List[str]) -> Dict[str, float]:
        """Fetch prices from Kraken API"""
        symbols = [self.kraken_symbols.get(coin) for coin in coins if coin in self.kraken_symbols]

        if not symbols:
            return {}

        response = self.session.get(
            f"{self.api_endpoints['kraken']}/Ticker",
            params={'pair': ','.join(symbols)},
            timeout=10,
            proxies=self.proxies,
            verify=False
        )
        response.raise_for_status()
        data = response.json()

        if data.get('error') and len(data['error']) > 0:
            raise Exception(f"Kraken API error: {data['error']}")

        prices = {}
        result = data.get('result', {})

        for coin in coins:
            kraken_symbol = self.kraken_symbols.get(coin)
            if kraken_symbol and kraken_symbol in result:
                ticker = result[kraken_symbol]
                current_price = float(ticker['c'][0])  # Last trade closed price
                open_price = float(ticker['o'])  # Today's opening price
                change_24h = ((current_price - open_price) / open_price * 100) if open_price > 0 else 0

                prices[coin] = {
                    'price': current_price,
                    'change_24h': change_24h
                }

        return prices

    def _get_prices_from_coinbase(self, coins: List[str]) -> Dict[str, float]:
        """Fetch prices from Coinbase API"""
        prices = {}

        for coin in coins:
            symbol = self.coinbase_symbols.get(coin)
            if not symbol:
                continue

            try:
                response = self.session.get(
                    f"{self.api_endpoints['coinbase']}/prices/{symbol}/spot",
                    timeout=8,
                    proxies=self.proxies,
                    verify=False
                )
                response.raise_for_status()
                data = response.json()

                if 'data' in data and 'amount' in data['data']:
                    prices[coin] = {
                        'price': float(data['data']['amount']),
                        'change_24h': 0  # Coinbase spot API doesn't provide 24h change
                    }
            except Exception as e:
                print(f"[DEBUG] Coinbase failed for {coin}: {e}")
                continue

        return prices

    def get_market_data(self, coin: str) -> Dict:
        """Get detailed market data from CoinGecko with error handling"""
        coin_id = self.coingecko_mapping.get(coin, coin.lower())

        try:
            response = self.session.get(
                f"{self.api_endpoints['coingecko']}/coins/{coin_id}",
                params={'localization': 'false', 'tickers': 'false', 'community_data': 'false'},
                timeout=12,
                proxies=self.proxies,
                verify=False
            )
            response.raise_for_status()
            data = response.json()

            market_data = data.get('market_data', {})

            return {
                'current_price': market_data.get('current_price', {}).get('usd', 0),
                'market_cap': market_data.get('market_cap', {}).get('usd', 0),
                'total_volume': market_data.get('total_volume', {}).get('usd', 0),
                'price_change_24h': market_data.get('price_change_percentage_24h', 0),
                'price_change_7d': market_data.get('price_change_percentage_7d', 0),
                'high_24h': market_data.get('high_24h', {}).get('usd', 0),
                'low_24h': market_data.get('low_24h', {}).get('usd', 0),
            }
        except Exception as e:
            print(f"[ERROR] Failed to get market data for {coin}: {e}")
            return {}

    def get_historical_prices(self, coin: str, days: int = 7) -> List[Dict]:
        """
        Get historical prices with intelligent caching
        Priority: Cache -> API (with cache update)
        """
        # Try to get from persistent cache first
        if self.persistent_cache:
            cached_prices = self.persistent_cache.get_historical_prices(coin, days)
            if cached_prices:
                self._cache_hits += 1
                print(f"[CACHE HIT] Using cached historical prices for {coin} ({len(cached_prices)} points)")
                return cached_prices
            else:
                self._cache_misses += 1
                print(f"[CACHE MISS] Fetching historical prices from API for {coin}")

        # Cache miss or disabled - fetch from API
        coin_id = self.coingecko_mapping.get(coin, coin.lower())

        try:
            response = self.session.get(
                f"{self.api_endpoints['coingecko']}/coins/{coin_id}/market_chart",
                params={'vs_currency': 'usd', 'days': days},
                timeout=12,
                proxies=self.proxies,
                verify=False
            )
            response.raise_for_status()
            data = response.json()

            prices = []
            for price_data in data.get('prices', []):
                prices.append({
                    'timestamp': price_data[0],
                    'price': price_data[1]
                })

            # Cache the fetched data
            if self.persistent_cache and prices:
                self.persistent_cache.cache_historical_prices(coin, prices, source='coingecko')

            return prices
        except Exception as e:
            print(f"[ERROR] Failed to get historical prices for {coin}: {e}")
            return []

    def _calculate_rsi(self, prices: List[float], period: int) -> float:
        """Calculate RSI for a given list of prices and lookback period."""
        if not prices or len(prices) < 2:
            return 50.0

        changes = [prices[i] - prices[i - 1] for i in range(1, len(prices))]
        gains = [c if c > 0 else 0 for c in changes]
        losses = [-c if c < 0 else 0 for c in changes]

        if not gains and not losses:
            return 50.0

        # Ensure we have enough data for the requested period; fallback to available length
        effective_period = min(period, len(gains)) if gains else period
        effective_period = max(1, effective_period)

        avg_gain = sum(gains[-effective_period:]) / effective_period if gains else 0
        avg_loss = sum(losses[-effective_period:]) / effective_period if losses else 0

        if avg_loss == 0:
            return 100.0

        rs = avg_gain / avg_loss
        return 100 - (100 / (1 + rs))

    def calculate_technical_indicators(self, coin: str) -> Dict:
        """
        Calculate comprehensive technical indicators with intelligent caching
        Priority: Cache -> Calculate (with cache update)

        Technical Indicator Formulas:
        - SMA: Simple Moving Average = Sum(prices) / n
        - EMA: Exponential Moving Average = Price(t) * k + EMA(y) * (1-k), where k = 2/(n+1)
        - RSI: Relative Strength Index = 100 - (100 / (1 + RS)), where RS = avg_gain / avg_loss
        - MACD: Moving Average Convergence Divergence = EMA(12) - EMA(26)
        - MACD Signal: EMA(9) of MACD line
        - MACD Histogram: MACD - Signal
        """
        indicators = None

        # Try to use recent technical indicators from persistent cache first (max age: 3 minutes)
        if self.persistent_cache:
            cached_indicators = self.persistent_cache.get_technical_indicators(coin, max_age_minutes=3)
            if cached_indicators:
                self._cache_hits += 1
                indicators = cached_indicators.copy()
                print(f"[CACHE HIT] 使用缓存技术指标: {coin} (缓存时间<=3分钟)")
            else:
                self._cache_misses += 1
                print(f"[CACHE MISS] 为 {coin} 计算最新技术指标")

        # If no fresh cache available, calculate from latest historical data
        if indicators is None:
            # Get more historical data for better EMA/MACD calculation (need 26+ days for MACD)
            historical = self.get_historical_prices(coin, days=30)

            if not historical or len(historical) < 14:
                print(f"[INDICATORS WARNING] {coin} 的历史价格数据不足，无法计算技术指标")
                return {}

            prices = [p['price'] for p in historical]

            # ============================================================
            # Simple Moving Averages (SMA)
            # ============================================================
            sma_7 = sum(prices[-7:]) / 7 if len(prices) >= 7 else prices[-1]
            sma_14 = sum(prices[-14:]) / 14 if len(prices) >= 14 else prices[-1]

            # ============================================================
            # Exponential Moving Averages (EMA)
            # ============================================================
            def calculate_ema(prices_list, period):
                """Calculate EMA using the standard formula"""
                if len(prices_list) < period:
                    return prices_list[-1] if prices_list else 0

                # Smoothing factor: k = 2 / (period + 1)
                k = 2 / (period + 1)

                # Start with SMA as the initial EMA
                ema = sum(prices_list[:period]) / period

                # Calculate EMA for remaining prices
                for price in prices_list[period:]:
                    ema = price * k + ema * (1 - k)

                return ema

            ema_12 = calculate_ema(prices, 12)
            ema_26 = calculate_ema(prices, 26)

            # ============================================================
            # RSI (Relative Strength Index)
            # ============================================================
            rsi = self._calculate_rsi(prices, 14)

            # ============================================================
            # MACD (Moving Average Convergence Divergence)
            # ============================================================
            macd_line = ema_12 - ema_26

            # Calculate MACD signal line (9-period EMA of MACD line)
            # For simplicity, we'll use a simple approximation since we only have the current MACD value
            # In a production system, you'd want to store historical MACD values
            macd_signal = macd_line * 0.8  # Simplified approximation
            macd_histogram = macd_line - macd_signal

            indicators = {
                # Simple Moving Averages
                'sma_7': sma_7,
                'sma_14': sma_14,

                # Exponential Moving Averages
                'ema_12': ema_12,
                'ema_26': ema_26,

                # RSI
                'rsi_14': rsi,

                # MACD
                'macd_line': macd_line,
                'macd_signal': macd_signal,
                'macd_histogram': macd_histogram,

                # Price data
                'current_price': prices[-1],
                'price_change_7d': ((prices[-1] - prices[0]) / prices[0]) * 100 if prices[0] > 0 else 0,

                # Metadata
                'data_points_count': len(prices)
            }

            # Update persistent cache with newly calculated indicators
            if self.persistent_cache:
                self.persistent_cache.cache_technical_indicators(coin, indicators)

        # Always try to calculate short-term RSI(9) on 15m candles from Binance
        try:
            closes_15m = self._get_klines_from_binance(coin, interval="15m", limit=30)
            if closes_15m and len(closes_15m) >= 10:
                # 正常路径：使用最新15m K线计算 RSI(9)
                rsi_9_15m = self._calculate_rsi(closes_15m, 9)
                indicators['rsi_9_15m'] = rsi_9_15m
                # 更新本币种的上一次有效 RSI(9,15m)
                self._last_rsi_9_15m[coin] = rsi_9_15m
                print(f"[INDICATORS] {coin} 的 RSI(9,15m)={rsi_9_15m:.2f}，基于 {len(closes_15m)} 条15分钟收盘价计算")
            else:
                # 数据为空或数量不足，尝试使用上一次成功计算的回退值
                last_rsi = self._last_rsi_9_15m.get(coin)
                if last_rsi is not None:
                    indicators['rsi_9_15m'] = last_rsi
                    print(f"[INDICATORS] {coin} 的15分钟K线为空或数量不足（仅有 {len(closes_15m) if closes_15m else 0} 条），使用上一次有效 RSI(9,15m)={last_rsi:.2f} 作为回退值")
                else:
                    print(f"[INDICATORS] {coin} 的15分钟K线为空或数量不足，且暂无历史 RSI(9,15m) 回退值，无法计算 RSI(9)")
        except Exception as e:
            # 请求异常时，同样尝试使用上一次成功计算的回退值
            last_rsi = self._last_rsi_9_15m.get(coin)
            if last_rsi is not None:
                indicators['rsi_9_15m'] = last_rsi
                print(f"[WARNING] 计算 {coin} 的 15分钟 RSI(9) 失败，使用上一次有效 RSI(9,15m)={last_rsi:.2f} 作为回退值: {e}")
            else:
                print(f"[WARNING] 计算 {coin} 的 15分钟 RSI(9) 失败，且暂无历史回退值: {e}")

        # Enhance with MCP data if available
        if self.mcp_client:
            print(f"[MCP DEBUG] 正在尝试使用 MCP 增强 {coin} 的技术指标...")
            try:
                # 1. 获取 K 线数据和技术指标
                mcp_indicators = self.mcp_client.get_technical_indicators(coin, timeframe="1d")
                if mcp_indicators:
                    # Merge MCP indicators (MCP data takes priority for overlapping fields)
                    indicators.update({
                        'mcp_rsi': mcp_indicators.get('rsi'),
                        'mcp_macd': mcp_indicators.get('macd'),
                        'mcp_macd_signal': mcp_indicators.get('macd_signal'),
                        'mcp_macd_histogram': mcp_indicators.get('macd_histogram'),
                        'bollinger_upper': mcp_indicators.get('bollinger_upper'),
                        'bollinger_middle': mcp_indicators.get('bollinger_middle'),
                        'bollinger_lower': mcp_indicators.get('bollinger_lower'),
                        'kdj_k': mcp_indicators.get('kdj_k'),
                        'kdj_d': mcp_indicators.get('kdj_d'),
                        'kdj_j': mcp_indicators.get('kdj_j'),
                    })
                    parsed_fields = [k for k, v in indicators.items() if k.startswith('mcp_') or k.startswith('kdj_') or k.startswith('bollinger_') and v is not None]
                    print(f"[MCP] ✓ 已为 {coin} 增强技术指标，共 {len(parsed_fields)} 个字段 ({', '.join(parsed_fields[:5])}...)")
                else:
                    print(f"[MCP] ✗ MCP 未返回 {coin} 的技术指标（可能解析失败）")

                # 2. 获取借贷比率
                loan_ratios = self.mcp_client.get_okx_loan_ratios(coin)
                if loan_ratios:
                    indicators['mcp_loan_ratios'] = loan_ratios
                    print(f"[MCP] OK 已获取 {coin} 的借贷比率")

                # 3. 获取主动买卖交易量
                taker_volume = self.mcp_client.get_okx_taker_volume(coin)
                if taker_volume:
                    indicators['mcp_taker_volume'] = taker_volume
                    print(f"[MCP] OK 已获取 {coin} 的主动买卖成交量")

                # 4. 获取币安 AI 分析报告
                ai_report = self.mcp_client.get_binance_ai_report(coin)
                if ai_report:
                    indicators['mcp_binance_ai_report'] = ai_report
                    print(f"[MCP] OK 已获取 {coin} 的币安AI分析报告")

            except Exception as e:
                print(f"[MCP WARNING] 使用 MCP 增强技术指标失败: {e}")
                import traceback
                traceback.print_exc()
        else:
            print(f"[MCP DEBUG] MCP 客户端不可用，跳过 {coin} 的技术指标增强")

        # Final debug print for all indicators used in decision making
        print(f"[INDICATORS] {coin} 最终用于决策的技术指标: {indicators}")

        return indicators

    def get_crypto_news(self, coin: str, limit: int = 5) -> List[Dict]:
        """
        获取加密货币相关新闻（通过MCP服务器）

        Args:
            coin: 币种符号（如 ETH）
            limit: 返回新闻数量

        Returns:
            新闻列表，每条新闻包含：title, summary, published_time, sentiment
        """
        if not self.mcp_client:
            print("[WARNING] MCP 客户端不可用，无法获取新闻")
            return []

        try:
            news_list = self.mcp_client.get_crypto_news(coin, limit)
            return news_list
        except Exception as e:
            print(f"[ERROR] 获取 {coin} 新闻失败: {e}")
            return []

    def get_api_health_status(self) -> Dict:
        """Get health status of all APIs and cache performance"""
        status = {
            'api_failures': self._api_failures.copy(),
            'last_successful_api': self._last_successful_api,
            'memory_cache_size': len(self._cache),
            'cache_hits': self._cache_hits,
            'cache_misses': self._cache_misses,
            'cache_hit_rate': f"{(self._cache_hits / (self._cache_hits + self._cache_misses) * 100):.1f}%"
                              if (self._cache_hits + self._cache_misses) > 0 else "N/A",
            'api_call_count': self._api_call_count,
            'snapshot_hit_count': self._snapshot_hit_count,
            'active_sessions': len(self._session_snapshot)
        }

        # Add persistent cache stats if enabled
        if self.persistent_cache:
            cache_stats = self.persistent_cache.get_cache_stats()
            status['persistent_cache'] = cache_stats

        return status

    # ============ Unified Market State Fetcher (Multi-Model Optimized) ============

    def get_market_state_for_all_models(self, coins: List[str], use_session: bool = True) -> Dict:
        """
        Get complete market state (prices + indicators) for all coins
        Optimized for multi-model scenarios with session-level caching

        Args:
            coins: List of coin symbols
            use_session: Whether to use session-level snapshot (default: True)

        Returns:
            Dict with market state for each coin

        Example:
            {
                'ETH）': {
                    'price': 43250.5,
                    'change_24h': 2.5,
                    'indicators': {...}
                },
                ...
            }
        """
        # Check if we can use session snapshot
        if use_session and self._current_session_id:
            snapshot = self.get_session_snapshot()
            if snapshot and 'market_state' in snapshot:
                self._snapshot_hit_count += 1
                print(f"[SNAPSHOT HIT] Using cached market state from session {self._current_session_id}")
                return snapshot['market_state']

        # Fetch fresh data
        print(f"[SNAPSHOT MISS] Fetching fresh market state for {len(coins)} coins")
        start_time = time.time()

        market_state = {}

        # Step 1: Get current prices for all coins (single API call)
        print(f"[STAGE 1/3] Fetching prices for {len(coins)} coins...")
        self._api_call_count += 1
        prices = self.get_current_prices(coins)
        print(f"[STAGE 1/3] ✓ Prices fetched in {time.time() - start_time:.2f}s")

        # Step 2: Get technical indicators for each coin
        print(f"[STAGE 2/3] Calculating technical indicators...")
        indicators_start = time.time()
        for coin in coins:
            if coin in prices:
                market_state[coin] = prices[coin].copy()

                # Get indicators (may use persistent cache)
                self._api_call_count += 1
                indicators = self.calculate_technical_indicators(coin)
                market_state[coin]['indicators'] = indicators

                # Step 3: Get crypto news from MCP (if available)
                # 关键改进: 使用独立的try-except块,确保单个币种失败不影响其他币种
                if self.mcp_client:
                    print(f"[MCP] Fetching news for {coin}...")
                    try:
                        news_start_time = time.time()

                        # MCP调用已在mcp_client.py中添加了超时保护(15秒)
                        news = self.get_crypto_news(coin, limit=5)

                        news_elapsed = time.time() - news_start_time
                        market_state[coin]['news'] = news

                        if news:
                            print(f"[MCP] ✓ Fetched {len(news)} news items for {coin} in {news_elapsed:.2f}s")
                        else:
                            print(f"[MCP] ⚠ No news returned for {coin} (took {news_elapsed:.2f}s)")

                    except Exception as e:
                        # 捕获所有异常(包括TimeoutError),确保不会阻塞整个流程
                        print(f"[MCP] ✗ Failed to fetch news for {coin}: {type(e).__name__}: {e}")
                        market_state[coin]['news'] = []
                        # 不打印完整堆栈,避免日志过于冗长
                        # import traceback
                        # traceback.print_exc()
                else:
                    print(f"[MCP] Skipping news for {coin} (MCP client not available)")
                    market_state[coin]['news'] = []

        # 阶段性总结
        indicators_elapsed = time.time() - indicators_start
        print(f"[STAGE 2/3] ✓ Indicators calculated in {indicators_elapsed:.2f}s")

        elapsed = time.time() - start_time
        print(f"[STAGE 3/3] ✓ Market state complete for {len(coins)} coins in {elapsed:.2f}s")

        # Store in session snapshot if session is active
        if use_session and self._current_session_id:
            self.update_session_snapshot('market_state', market_state)
            print(f"[SNAPSHOT] Stored market state in session {self._current_session_id}")

        return market_state

