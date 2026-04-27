import json
import time
from typing import Dict, Optional
from openai import OpenAI, APIConnectionError, APIError

class AITrader:
    def __init__(self, api_key: str, api_url: str, model_name: str, max_retries: int = 3):
        self.api_key = api_key
        self.api_url = api_url
        self.model_name = model_name
        self.max_retries = max_retries
        self._last_successful_decision = None  # Cache last successful decision
        self._consecutive_failures = 0
    
    def make_decision(self, market_state: Dict, portfolio: Dict,
                     account_info: Dict) -> Dict:
        """
        Make trading decision with retry mechanism and fallback

        Returns:
            Dict with keys:
                - 'decisions': Parsed trading decisions (dict)
                - 'raw_response': AI's original response text (str)
                - 'is_fallback': Whether fallback strategy was used (bool)
        """
        prompt = self._build_prompt(market_state, portfolio, account_info)

        # Try to get decision from AI with retries
        for attempt in range(self.max_retries):
            try:
                response = self._call_llm(prompt)
                decisions = self._parse_response(response)

                if decisions:
                    # Success! Cache the decision and reset failure counter
                    self._last_successful_decision = {
                        'decisions': decisions,
                        'raw_response': response,
                        'is_fallback': False
                    }
                    self._consecutive_failures = 0
                    return self._last_successful_decision
                else:
                    print(f"[WARNING] AI returned empty decision (attempt {attempt + 1}/{self.max_retries})")

            except Exception as e:
                self._consecutive_failures += 1
                print(f"[ERROR] AI decision failed (attempt {attempt + 1}/{self.max_retries}): {e}")

                if attempt < self.max_retries - 1:
                    # Wait before retry (exponential backoff)
                    wait_time = 10 ** attempt  # 1s, 2s, 4s
                    print(f"[RETRY] Waiting {wait_time}s before retry...")
                    time.sleep(wait_time)
                    continue

        # All retries failed - use fallback strategy
        print(f"[WARNING] All AI decision attempts failed ({self._consecutive_failures} consecutive failures)")
        return self._get_fallback_decision(market_state, portfolio)

    def _get_fallback_decision(self, market_state: Dict, portfolio: Dict) -> Dict:
        """
        Fallback decision strategy when AI is unavailable

        Returns:
            Dict with keys:
                - 'decisions': Fallback trading decisions (dict)
                - 'raw_response': Explanation of fallback (str)
                - 'is_fallback': True
        """
        print("[FALLBACK] Using conservative fallback strategy")

        # If we have a cached decision and it's not too old, use it
        if self._last_successful_decision and self._consecutive_failures < 5:
            print("[FALLBACK] Using last successful AI decision")
            cached = self._last_successful_decision.copy()
            cached['is_fallback'] = True
            cached['raw_response'] = f"[FALLBACK] 使用缓存的AI决策（连续失败{self._consecutive_failures}次）\n\n" + cached.get('raw_response', '')
            return cached

        # Otherwise, use conservative "hold" strategy
        print("[FALLBACK] Using conservative 'hold all' strategy")
        decisions = {}
        fallback_explanation = f"[FALLBACK] AI服务暂时不可用（连续失败{self._consecutive_failures}次），采用保守策略：\n\n"

        for coin in market_state.keys():
            decisions[coin] = {
                'signal': 'hold',
                'justification': 'AI服务暂时不可用，保持当前仓位以确保安全',
                'leverage': 1,
                'confidence': 0.5
            }
            fallback_explanation += f"- {coin}: HOLD（保持当前仓位，等待AI服务恢复）\n"

        return {
            'decisions': decisions,
            'raw_response': fallback_explanation,
            'is_fallback': True
        }
    
    def _build_prompt(self, market_state: Dict, portfolio: Dict,
                     account_info: Dict) -> str:
        """
        Build comprehensive trading prompt with enhanced technical analysis frameworks
        """
        # Calculate total return percentage
        total_return = account_info.get('total_return', 0.0)
        available_cash = portfolio.get('cash', 0.0)
        total_account_value = portfolio.get('total_value', 0.0)

        # Build market data sections for each coin
        market_sections = []
        for coin, data in market_state.items():
            price = data.get('price', 0)
            change_24h = data.get('change_24h', 0)
            indicators = data.get('indicators', {})
            news_items = data.get('news', [])

            # Get all available indicators (including MCP-enhanced ones)
            sma_7 = indicators.get('sma_7', price)
            sma_14 = indicators.get('sma_14', price)
            ema_12 = indicators.get('ema_12', price)
            ema_26 = indicators.get('ema_26', price)
            rsi_14 = indicators.get('rsi_14', 50)
            macd_line = indicators.get('macd_line', 0)
            macd_signal = indicators.get('macd_signal', 0)
            macd_histogram = indicators.get('macd_histogram', 0)

            # MCP-enhanced indicators
            mcp_rsi = indicators.get('mcp_rsi')
            bollinger_upper = indicators.get('bollinger_upper')
            bollinger_middle = indicators.get('bollinger_middle')
            bollinger_lower = indicators.get('bollinger_lower')
            kdj_k = indicators.get('kdj_k')
            kdj_d = indicators.get('kdj_d')
            kdj_j = indicators.get('kdj_j')

            # MCP market data (from OKX and Binance)
            mcp_loan_ratios = indicators.get('mcp_loan_ratios', {})
            mcp_taker_volume = indicators.get('mcp_taker_volume', {})
            mcp_binance_ai_report = indicators.get('mcp_binance_ai_report', {})

            # Determine MACD trend and momentum strength
            macd_trend = "bullish" if macd_histogram > 0 else "bearish"
            macd_strength = "strengthening" if abs(macd_histogram) > abs(macd_line - macd_signal) * 0.5 else "weakening"

            # Multi-timeframe analysis
            trend_alignment = "ALIGNED" if (price > sma_14 and ema_12 > ema_26) or (price < sma_14 and ema_12 < ema_26) else "CONFLICTING"
            
            # Build Bollinger Bands section with advanced analysis
            bollinger_section = ""
            if bollinger_upper and bollinger_middle and bollinger_lower:
                bb_width = ((bollinger_upper - bollinger_lower) / bollinger_middle) * 100
                bb_position_percent = (price - bollinger_lower) / (bollinger_upper - bollinger_lower) * 100
                
                if bb_position_percent > 80:
                    bb_position = f"UPPER BAND (overbought) - {bb_position_percent:.1f}%"
                    bb_signal = "Bearish reversal potential"
                elif bb_position_percent < 20:
                    bb_position = f"LOWER BAND (oversold) - {bb_position_percent:.1f}%"
                    bb_signal = "Bullish reversal potential"
                else:
                    bb_position = f"MIDDLE RANGE - {bb_position_percent:.1f}%"
                    bb_signal = "Neutral - watch for breakout"
                
                bollinger_section = f"""
Bollinger Bands Analysis (OKX Real-time):
  • Upper: ${bollinger_upper:.2f} | Middle: ${bollinger_middle:.2f} | Lower: ${bollinger_lower:.2f}
  • Position: {bb_position}
  • Band Width: {bb_width:.2f}% ({'High Volatility' if bb_width > 5 else 'Low Volatility'})
  • Signal: {bb_signal}
"""

            # Build KDJ section with advanced signals
            kdj_section = ""
            if kdj_k and kdj_d and kdj_j:
                kdj_cross = "Bullish (K > D)" if kdj_k > kdj_d else "Bearish (K < D)"
                if kdj_k < 20 and kdj_d < 20:
                    kdj_status = "STRONG OVERSOLD - High bounce probability"
                elif kdj_k > 80 and kdj_d > 80:
                    kdj_status = "STRONG OVERBOUGHT - High correction risk"
                elif (kdj_k > kdj_d) and (kdj_k < 50):
                    kdj_status = "Bullish momentum building"
                elif (kdj_k < kdj_d) and (kdj_k > 50):
                    kdj_status = "Bearish momentum building"
                else:
                    kdj_status = "Neutral - waiting for direction"
                    
                kdj_section = f"""
KDJ Momentum Oscillator (OKX Real-time):
  • K: {kdj_k:.1f} | D: {kdj_d:.1f} | J: {kdj_j:.1f}
  • Cross: {kdj_cross}
  • Status: {kdj_status}
"""

            # Enhanced OKX Loan Ratios analysis
            loan_ratios_section = ""
            if mcp_loan_ratios and isinstance(mcp_loan_ratios, dict):
                loan_text = mcp_loan_ratios.get('raw_text', '')
                if loan_text:
                    # Analyze loan ratio sentiment
                    if "high" in loan_text.lower() or "increase" in loan_text.lower():
                        loan_sentiment = "CAUTION - High leverage risk detected"
                    elif "low" in loan_text.lower() or "decrease" in loan_text.lower():
                        loan_sentiment = "SAFE - Low leverage environment"
                    else:
                        loan_sentiment = "NEUTRAL - Moderate leverage levels"
                        
                    loan_ratios_section = f"""
OKX Loan Ratios (Market Leverage Sentiment):
  • Data: {loan_text[:150]}...
  • Sentiment: {loan_sentiment}
  • Trading Implication: High ratios = liquidation cascade risk
"""

            # Enhanced OKX Taker Volume analysis
            taker_volume_section = ""
            if mcp_taker_volume and isinstance(mcp_taker_volume, dict):
                volume_text = mcp_taker_volume.get('raw_text', '')
                if volume_text:
                    # Analyze volume sentiment
                    if "buy" in volume_text.lower() and "sell" not in volume_text.lower():
                        volume_sentiment = "STRONG BULLISH - Dominant buying pressure"
                    elif "sell" in volume_text.lower() and "buy" not in volume_text.lower():
                        volume_sentiment = "STRONG BEARISH - Dominant selling pressure" 
                    elif "buy" in volume_text.lower() and "sell" in volume_text.lower():
                        volume_sentiment = "MIXED - Balanced buying/selling"
                    else:
                        volume_sentiment = "NEUTRAL - No clear pressure"
                        
                    taker_volume_section = f"""
OKX Taker Volume (Smart Money Flow):
  • Data: {volume_text[:150]}...
  • Sentiment: {volume_sentiment}
  • Interpretation: Shows institutional order flow direction
"""

            # Enhanced Binance AI Report analysis
            binance_ai_section = ""
            if mcp_binance_ai_report and isinstance(mcp_binance_ai_report, dict):
                ai_text = mcp_binance_ai_report.get('raw_text', '')
                if ai_text:
                    # Extract AI sentiment
                    ai_lower = ai_text.lower()
                    if any(word in ai_lower for word in ['bullish', 'buy', 'accumulate', 'positive']):
                        ai_sentiment = "BULLISH - AI recommends long bias"
                    elif any(word in ai_lower for word in ['bearish', 'sell', 'distribute', 'negative']):
                        ai_sentiment = "BEARISH - AI recommends short bias"
                    else:
                        ai_sentiment = "NEUTRAL - AI sees balanced market"
                        
                    binance_ai_section = f"""
Binance AI Analysis Report (Institutional Grade):
  • Summary: {ai_text[:200]}...
  • AI Sentiment: {ai_sentiment}
  • Weight: Consider as professional second opinion
"""

            # Enhanced news analysis with sentiment scoring
            news_section = ""
            if news_items:
                news_lines = []
                sentiment_scores = []
                
                for idx, news in enumerate(news_items[:4], 1):
                    sentiment = news.get('sentiment', 'neutral')
                    title = news.get('title', 'N/A')[:70]
                    summary = news.get('summary', 'N/A')[:100]
                    
                    # Score sentiments
                    if sentiment == 'positive':
                        score = 1
                        emoji = "🟢"
                    elif sentiment == 'negative':
                        score = -1
                        emoji = "🔴"
                    else:
                        score = 0
                        emoji = "⚪"
                    
                    sentiment_scores.append(score)
                    news_lines.append(
                        f"  {idx}. {emoji} {title}\n"
                        f"     {summary}..."
                    )

                # Calculate overall sentiment score
                total_score = sum(sentiment_scores)
                if total_score >= 2:
                    overall_sentiment = "STRONGLY BULLISH 🟢🟢"
                    confidence_boost = "+0.15"
                elif total_score >= 1:
                    overall_sentiment = "BULLISH 🟢"
                    confidence_boost = "+0.10"
                elif total_score <= -2:
                    overall_sentiment = "STRONGLY BEARISH 🔴🔴"
                    confidence_boost = "-0.15"
                elif total_score <= -1:
                    overall_sentiment = "BEARISH 🔴"
                    confidence_boost = "-0.10"
                else:
                    overall_sentiment = "NEUTRAL ⚪"
                    confidence_boost = "±0.00"

                news_section = f"""
Market News & Sentiment Analysis:
  Overall: {overall_sentiment} (Confidence Impact: {confidence_boost})
  Score: {total_score}/4 (Positive: {sentiment_scores.count(1)}, Negative: {sentiment_scores.count(-1)}, Neutral: {sentiment_scores.count(0)})

{chr(10).join(news_lines)}
"""

            # Build comprehensive technical analysis section
            section = f"""
═══════════════════════════════════════════════════════════════
{coin} COMPREHENSIVE TECHNICAL ANALYSIS
═══════════════════════════════════════════════════════════════

PRICE & TREND:
  • Current: ${price:.2f} (24h: {change_24h:+.2f}%)
  • Trend Alignment: {trend_alignment}
  • vs SMA14: {'ABOVE (Bullish)' if price > sma_14 else 'BELOW (Bearish)'}
  • EMA Cross: {'GOLDEN CROSS (Bullish)' if ema_12 > ema_26 else 'DEATH CROSS (Bearish)'}

MOMENTUM INDICATORS:
  • RSI(14): {rsi_14:.1f} {'- OVERSOLD' if rsi_14 < 30 else '- OVERBOUGHT' if rsi_14 > 70 else '- Neutral'}
  • MACD: Line={macd_line:.3f}, Signal={macd_signal:.3f}
  • Histogram: {macd_histogram:.3f} ({macd_trend.upper()}, {macd_strength})

MOVING AVERAGES:
  • SMA(7):  ${sma_7:.2f} | Distance: {(price/sma_7-1)*100:+.2f}%
  • SMA(14): ${sma_14:.2f} | Distance: {(price/sma_14-1)*100:+.2f}%
  • EMA(12): ${ema_12:.2f} | EMA(26): ${ema_26:.2f}
{bollinger_section}{kdj_section}
EXCHANGE DATA & MARKET MICROSTRUCTURE:
{loan_ratios_section}{taker_volume_section}{binance_ai_section}{news_section}"""
            market_sections.append(section)

        # Build positions section (unchanged from original)
        positions_data = []
        if portfolio.get('positions'):
            for pos in portfolio['positions']:
                current_price = market_state.get(pos['coin'], {}).get('price', pos['avg_price'])
                if pos['side'] == 'long':
                    unrealized_pnl = (current_price - pos['avg_price']) * pos['quantity']
                else:
                    unrealized_pnl = (pos['avg_price'] - current_price) * pos['quantity']

                leverage = pos['leverage']
                entry_price = pos['avg_price']
                if pos['side'] == 'long':
                    liquidation_price = entry_price * (1 - 0.9 / leverage)
                else:
                    liquidation_price = entry_price * (1 + 0.9 / leverage)

                pnl_percent = (unrealized_pnl / (pos['quantity'] * entry_price)) * 100 * leverage

                pos_data = {
                    'symbol': pos['coin'],
                    'quantity': pos['quantity'],
                    'entry_price': entry_price,
                    'current_price': current_price,
                    'liquidation_price': liquidation_price,
                    'unrealized_pnl': unrealized_pnl,
                    'pnl_percent': pnl_percent,
                    'leverage': leverage,
                    'side': pos['side'],
                    'notional_usd': pos['quantity'] * current_price
                }
                positions_data.append(pos_data)

        # Format positions for display
        if not positions_data:
            positions_str = "No open positions"
        else:
            position_lines = []
            for p in positions_data:
                pnl_sign = "+" if p['unrealized_pnl'] >= 0 else ""
                position_lines.append(
                    f"  • {p['symbol']}: {p['side'].upper()} {p['quantity']:.4f} @ ${p['entry_price']:.2f} ({p['leverage']}x)\n"
                    f"    Current: ${p['current_price']:.2f} | P&L: {pnl_sign}${p['unrealized_pnl']:.2f} ({pnl_sign}{p['pnl_percent']:.2f}%)\n"
                    f"    Liquidation: ${p['liquidation_price']:.2f} | Notional: ${p['notional_usd']:.2f}"
                )
            positions_str = "\n".join(position_lines)

        # Build the enhanced comprehensive prompt
        prompt = f"""It has been several minutes since you started trading. Below is the current market state and your account information.

ALL OF THE PRICE OR SIGNAL DATA BELOW IS ORDERED: OLDEST → NEWEST

CURRENT MARKET STATE FOR ALL COINS
{''.join(market_sections)}

═══════════════════════════════════════════════════════════════
ACCOUNT INFORMATION & PERFORMANCE
═══════════════════════════════════════════════════════════════
Total Return: {total_return:.2f}%
Available Cash: ${available_cash:.2f}
Account Value: ${total_account_value:.2f}

Open Positions:
{positions_str}

═══════════════════════════════════════════════════════════════
ENHANCED TRADING FRAMEWORK - MULTI-STRATEGY APPROACH
═══════════════════════════════════════════════════════════════

GLOBAL TECHNICAL ANALYSIS FRAMEWORKS INTEGRATED:

1. **DOW THEORY (Trend Following)**
   - Primary Trend: Price vs SMA14 alignment
   - Secondary Trend: EMA12 vs EMA26 crossovers
   - Confirmation: Volume (OKX taker) should confirm trend

2. **ELLIOTT WAVE (Market Psychology)**
   - Impulse Waves: Strong MACD + RSI momentum + volume confirmation
   - Corrective Waves: RSI 30-70 retracements + reduced volume
   - Wave 3 Opportunities: Strongest trends (look for EMA alignment)

3. **WYCKOFF METHOD (Smart Money Analysis)**
   - Accumulation Phase: RSI oversold + sideways action + reducing volume
   - Markup Phase: Breaking resistance + increasing volume + MACD turn
   - Distribution: RSI overbought + price divergence + high volume
   - Markdown: Breaking support + panic selling

4. **FIBONACCI & SUPPORT/RESISTANCE**
   - Key Levels: Use recent swing highs/lows as natural S/R
   - Retracement Entries: 38.2%, 50%, 61.8% of recent moves
   - Extension Targets: 127.2%, 161.8% for profit taking

CONFIRMATION MATRIX - WEIGHTED DECISION SYSTEM:

Score trades using this confirmation system (need 3+ for high confidence):

PRICE & TREND (40% weight):
✓ Price > SMA14 AND EMA12 > EMA26 (bullish) = +1
✓ Price < SMA14 AND EMA12 < EMA26 (bearish) = +1  
✓ Trend alignment across timeframes = +1

MOMENTUM (30% weight):
✓ RSI < 40 (bullish) OR RSI > 60 (bearish) = +1
✓ MACD histogram positive & strengthening (bullish) = +1
✓ MACD histogram negative & strengthening (bearish) = +1
✓ KDJ in oversold/overbought territory = +1

MARKET STRUCTURE (20% weight):
✓ Bollinger Band position confirms thesis = +1
✓ OKX loan ratios at safe levels = +1
✓ OKX taker volume confirms direction = +1
✓ News sentiment aligns with trade = +1

EXPERT CONFIRMATION (10% weight):
✓ Binance AI report supports thesis = +1

CONFIDENCE SCORING GUIDE:
- 4+ confirmations = High confidence (0.8-0.9)
- 3 confirmations = Medium confidence (0.6-0.7)
- 2 confirmations = Low confidence (0.4-0.5) - reduce size
- 0-1 confirmations = Avoid trade

MARKET REGIME DETECTION & STRATEGY SELECTION:

1. **TRENDING MARKET** (Clear directional moves)
   - Signs: Strong EMA alignment, sustained MACD momentum
   - Strategy: Trend following, 10-15x leverage
   - Entries: Pullbacks to EMA12 or SMA14
   - Stops: Below EMA26 (long) or above EMA26 (short)

2. **RANGING MARKET** (Consolidation phase)
   - Signs: EMA convergence, weak MACD, price oscillating
   - Strategy: Mean reversion, 5-8x leverage
   - Entries: RSI extremes + Bollinger Band touches
   - Stops: Beyond recent highs/lows

3. **VOLATILE/BREAKOUT MARKET** 
   - Signs: Expanding Bollinger Bands, high loan ratios
   - Strategy: Wait for confirmation, 3-5x leverage
   - Entries: Retest of breakout levels
   - Stops: Wide stops for volatility

ADVANCED PRICE-MOMENTUM DIVERGENCE DETECTION:

BULLISH DIVERGENCE (Strong Reversal Signal):
- Price makes LOWER low, RSI makes HIGHER low = +2 confirmations
- Price makes LOWER low, MACD makes HIGHER low = +2 confirmations
- Add 0.15 to confidence when divergence detected

BEARISH DIVERGENCE (Strong Reversal Signal):
- Price makes HIGHER high, RSI makes LOWER high = +2 confirmations  
- Price makes HIGHER high, MACD makes LOWER high = +2 confirmations
- Add 0.15 to confidence when divergence detected

ENHANCED RISK MANAGEMENT:

POSITION SIZING (账户$100,000为例):
- High Confidence (0.8+):
  * 风险: 7-10% ($7,000-$10,000)
  * 杠杆: 15-20x
  * 目标保证金: $8,000-$12,000
  * 示例: BNB $100K, 用15x杠杆, 目标保证金$10K → quantity = 1.5 BNB

- Medium Confidence (0.6-0.7):
  * 风险: 5-7% ($5,000-$7,000)
  * 杠杆: 12-15x
  * 目标保证金: $5,000-$8,000
  * 示例: ETH $3.6K, 用12x杠杆, 目标保证金$7K → quantity = 23.3 ETH

- Low Confidence (0.4-0.5):
  * 风险: 3-5% ($3,000-$5,000)
  * 杠杆: 8-12x
  * 目标保证金: $3,000-$5,000
  * 示例: SOL $200, 用10x杠杆, 目标保证金$5K → quantity = 250 SOL

重要: 每笔交易的保证金应该在$5,000-$12,000之间，不要太小！

DYNAMIC STOP LOSSES:
- Trending Markets: Below EMA26 (long) or above EMA26 (short)
- Ranging Markets: Beyond Bollinger Bands
- Volatile Markets: 1.5x Bollinger Band width

PROFIT TAKING STRATEGY:
- Scale out: 50% at 1:1 R/R, 25% at 2:1, 25% at 3:1
- Trail stops: Use EMA12 for strong trends
- Resistance targets: Bollinger Upper (short), Recent highs (long)

SPECIFIC TRADING SETUPS:

HIGH-PROBABILITY LONG SETUPS:
1. RSI < 35 + Price > SMA14 + EMA12 > EMA26 + MACD turning up
2. Bollinger Lower Band touch + RSI oversold + Bullish divergence
3. Accumulation pattern (sideways) + Breakout + Volume confirmation

HIGH-PROBABILITY SHORT SETUPS:  
1. RSI > 65 + Price < SMA14 + EMA12 < EMA26 + MACD turning down
2. Bollinger Upper Band touch + RSI overbought + Bearish divergence
3. Distribution pattern + Breakdown + Volume confirmation

POSITION MANAGEMENT:
- Maximum 4-6 positions across different coins
- Each position should use $5,000-$12,000 margin
- Total margin usage target: 30-50% of account ($30,000-$50,000)
- Maintain 10-15% cash for opportunities
- Close positions showing divergence against you
- Take partial profits at technical targets

═══════════════════════════════════════════════════════════════
OUTPUT FORMAT REQUIREMENTS
═══════════════════════════════════════════════════════════════

You MUST respond with ONLY a valid JSON object. No explanations, no markdown, just JSON.

For each coin you want to trade (or hold), provide this structure:

{{
  "COIN_SYMBOL": {{
    "signal": "buy_to_enter|sell_to_enter|add_position|reduce_position|close_position|hold",
    "quantity": 0.5,
    "leverage": 10,
    "profit_target": 45000.0,
    "stop_loss": 42000.0,
    "invalidation_condition": "Price closes below EMA26 or MACD turns negative",
    "confidence": 0.75,
    "risk_usd": 500.0,
    "justification": "3 confirmations: RSI oversold (35), EMA golden cross, OKX buy volume dominance. News sentiment neutral. Confidence boosted by Bollinger lower band bounce setup."
  }}
}}

CRITICAL OUTPUT RULES:
1. You MUST analyze ALL coins and output decisions for each where you see opportunities
2. Do NOT return empty object {{}} - at minimum output "hold" for existing positions
3. Confidence must reflect confirmation matrix scoring (0.4-0.9 range)
4. Justification must reference specific confirmations from the matrix in Chinese
5. Quantity calculation (重要 - 账户$100,000为例):
   - 目标: 每笔交易保证金$5,000-$12,000
   - 公式: quantity = (目标保证金 × leverage) / price
   - 例1: ETH $3.6K, 杠杆12x, 目标$7K → quantity = ($7K × 12) / $3.6K = 23.3 ETH
   - 例2: SOL $200, 杠杆10x, 目标$5K → quantity = ($5K × 10) / $200 = 250 SOL
   - 验证: 保证金 = (quantity × price) / leverage 应该在$5K-$12K之间
6. Output ONLY raw JSON - no other text
7. **JSON格式要求（关键！）**: 在justification等字符串字段中，如需引用文字，请使用单引号(')而非双引号(")
   - ✅ 正确: "justification": "新闻情绪'积极'，Binance AI报告看涨"
   - ❌ 错误: "justification": "新闻情绪"积极"，Binance AI报告看涨"  (会导致JSON解析失败)

EXAMPLE ENHANCED OUTPUT (账户$100,000示例):
{{
  "ETH": {{
    "signal": "buy_to_enter",
    "quantity": 23.3,
    "leverage": 12,
    "profit_target": 4200,
    "stop_loss": 3500,
    "invalidation_condition": "Price breaks below SMA14 with volume",
    "confidence": 0.70,
    "risk_usd": 5000,
    "justification": "3个确认: MACD正向, RSI中性, 布林带中轨支撑. OKX成交量混合. 中等信心. 保证金$7,000 (7%账户)."
  }},
  "SOL": {{
    "signal": "buy_to_enter",
    "quantity": 250,
    "leverage": 10,
    "profit_target": 220,
    "stop_loss": 180,
    "invalidation_condition": "RSI drops below 30 or breaks EMA26",
    "confidence": 0.65,
    "risk_usd": 4000,
    "justification": "3个确认: 布林带下轨反弹, RSI超卖恢复, OKX正向成交量. 保证金$5,000 (5%账户)."
  }},
  "XRP": {{
    "signal": "hold",
    "quantity": 0,
    "leverage": 1,
    "profit_target": 0,
    "stop_loss": 0,
    "invalidation_condition": "N/A",
    "confidence": 0.5,
    "risk_usd": 0,
    "justification": "仅1个确认: 布林带中轨. 信号冲突 - EMA死叉但RSI中性. 等待明确方向."
  }}
}}

NOW analyze the market data using the enhanced framework and output your trading decisions.

═══════════════════════════════════════════════════════════════
BEGIN ENHANCED ANALYSIS  
═══════════════════════════════════════════════════════════════
"""  

        return prompt
    
    def _call_llm(self, prompt: str) -> str:
        """
        Call LLM API with detailed error handling
        """
        try:
            base_url = self.api_url.rstrip('/')
            if not base_url.endswith('/v1'):
                if '/v1' in base_url:
                    base_url = base_url.split('/v1')[0] + '/v1'
                else:
                    base_url = base_url + '/v1'

            client = OpenAI(
                api_key=self.api_key,
                base_url=base_url,
                timeout=60.0  # 60 second timeout (increased from 30s to handle slow API responses)
            )

            response = client.chat.completions.create(
                model=self.model_name,
                messages=[
                    {
                        "role": "system",
                        "content": """# Role: 加密货币量化交易员
## Profile
- language: 中文/英文
- description: 专业的加密货币量化交易专家，专注于永续合约高频交易，整合多流派技术分析框架
- background: 拥有多年加密货币市场交易经验，精通技术指标分析和量化交易策略
- personality: 理性、严谨、果断、风险规避
- expertise: 多流派技术分析、动态风险管理、量化策略优化、高频交易执行
- target_audience: 加密货币交易平台、量化基金、专业交易者

## Core Technical Frameworks

### 多流派技术分析集成
- **道氏理论**: 趋势识别与确认
- **艾略特波浪**: 市场心理与波浪结构
- **威科夫方法**: 聪明钱行为分析
- **斐波那契**: 支撑阻力与目标位计算
- **动量分析**: RSI、MACD、KDJ指标组合

### 量化决策矩阵
- **确认系统**: 需要3+个技术指标确认信号
- **置信度评分**: 基于指标一致性(0.4-0.9)
- **市场状态识别**: 趋势市、震荡市、突破市
- **背离检测**: 价格-动量背离分析

## Skills

### 技术分析技能
- 多时间框架分析: 整合EMA、MACD、RSI、Bollinger Bands
- 趋势强度评估: 趋势方向、动量持续性、反转概率
- 价格行为识别: 支撑阻力、突破确认、形态识别
- 量价关系分析: OKX实时成交量、资金流向

### 风险管理技能
- 动态头寸管理: 基于置信度和波动率调整仓位
- 智能止损设置: 技术位止损 + 波动率止损
- 风险分散策略: 4-6个低相关性币种组合
- 资金管理优化: 凯利公式变体 + 最大回撤控制

### 交易执行技能
- 多因子信号识别: 技术指标 + 市场微观结构 + 新闻情绪
- 量化决策制定: 确认矩阵评分 + 置信度驱动
- 纪律执行: 严格执行交易计划和风控规则
- 实时绩效监控: 持仓风险 + 策略有效性评估

## Rules

### 交易原则
- 风险优先: 单笔交易风险控制在5-10%，高信心度交易可达10% ($5,000-$10,000)
- 分散投资: 同时持有4-6个不同币种的头寸
- 现金储备: 保持10-15%的可用现金用于加仓和新机会
- 杠杆控制: 基于置信度调整杠杆倍数(8-20倍)

### 行为准则
- 纪律执行: 严格遵守技术止损和止盈规则
- 客观分析: 基于多因子确认矩阵做出决策
- 及时调整: 根据市场状态动态切换策略
- 持续优化: 基于绩效数据改进交易模型

### 限制条件
- 头寸限制: 单个币种名义价值不超过总资金的40%，保证金建议$5,000-$15,000
- 杠杆上限: 最大杠杆倍数不超过20倍
- 风险回报: 目标风险回报比不低于2:1
- 确认要求: 至少3个技术指标确认交易信号

## Workflows

### 量化决策流程
1. **市场分析阶段**
   - 多时间框架趋势分析
   - 技术指标一致性评估
   - 市场状态识别(趋势/震荡/突破)
   - 背离检测和反转信号识别

2. **风险评估阶段**
   - 现有持仓风险分析
   - liquidation风险检查
   - 相关性分析和分散度评估
   - 现金储备和仓位容量计算

3. **机会识别阶段**
   - 多因子信号筛选
   - 确认矩阵评分(0-5分)
   - 置信度计算(0.4-0.9)
   - 风险回报比优化

4. **决策输出阶段**
   - 头寸参数精确计算（仅空头）
   - 止损止盈技术位设定（仅空头）
   - 交易指令结构化输出（仅空头）
   - 组合再平衡检查（仅空头头寸）

### 技术指标优先级
1. **核心趋势指标**: EMA12/26, SMA14, 价格位置
2. **动量确认指标**: MACD, RSI, KDJ, 成交量
3. **市场结构指标**: Bollinger Bands, 支撑阻力
4. **情绪辅助指标**: 新闻情绪, OKX数据, Binance AI

## Output Specifications

### JSON格式要求（重要！）
1. **必须输出纯JSON**: 不要包含任何markdown标记、注释或其他文本
2. **字符串值中的引号**:
   - ❌ 错误: "justification": "新闻情绪"积极""  (未转义的双引号会导致解析失败)
   - ✅ 正确: "justification": "新闻情绪'积极'"  (使用单引号)
   - ✅ 正确: "justification": "新闻情绪\\"积极\\""  (转义双引号)
3. **推荐做法**: 在justification等文本字段中，如需引用，请使用单引号(')而非双引号(")
4. **示例**:
   - ✅ "justification": "3个确认：EMA死叉（看跌）、MACD柱状图减弱（看跌）、KDJ死叉（看跌）。新闻情绪'消极'。"
   - ❌ "justification": "3个确认：EMA死叉（看跌）、MACD柱状图减弱（看跌）、KDJ死叉（看跌）。新闻情绪"消极"。"

Output JSON format only."""
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                temperature=0.7,
                max_tokens=2000
            )

            return response.choices[0].message.content

        except APIConnectionError as e:
            error_msg = f"API connection failed (check network/URL): {str(e)}"
            print(f"[ERROR] {error_msg}")
            print(f"[DEBUG] API URL: {self.api_url}")
            print(f"[DEBUG] Model: {self.model_name}")

            # Check if it's a timeout error
            if "timed out" in str(e).lower() or "timeout" in str(e).lower():
                print(f"[HINT] API request timed out after 60 seconds")
                print(f"[HINT] This may indicate:")
                print(f"       1. Slow network connection")
                print(f"       2. API server is overloaded")
                print(f"       3. Large prompt causing slow processing")
                print(f"[HINT] The system will retry automatically")

            raise Exception(error_msg)
        except APIError as e:
            # Detailed error message for different status codes
            if e.status_code == 503:
                error_msg = f"API service unavailable (503): {e.message}"
                print(f"[ERROR] {error_msg}")
                print(f"[HINT] The AI API service may be down or overloaded.")
                print(f"[HINT] Please check your API service status or try a different API.")
            elif e.status_code == 401:
                error_msg = f"API authentication failed (401): Invalid API key"
                print(f"[ERROR] {error_msg}")
                print(f"[HINT] Please check your API key in the model configuration.")
            elif e.status_code == 429:
                error_msg = f"API rate limit exceeded (429): {e.message}"
                print(f"[ERROR] {error_msg}")
                print(f"[HINT] You've hit the API rate limit. Wait before retrying.")
            else:
                error_msg = f"API error ({e.status_code}): {e.message}"
                print(f"[ERROR] {error_msg}")

            print(f"[DEBUG] API URL: {self.api_url}")
            print(f"[DEBUG] Model: {self.model_name}")
            raise Exception(error_msg)
        except Exception as e:
            error_msg = f"LLM call failed: {str(e)}"
            print(f"[ERROR] {error_msg}")
            print(f"[DEBUG] API URL: {self.api_url}")
            print(f"[DEBUG] Model: {self.model_name}")
            raise Exception(error_msg)
    
    def _parse_response(self, response: str) -> Dict:
        """
        Parse AI response with intelligent handling of <think> tags and various formats

        Supports:
        - Responses with <think>...</think> tags (extracts content after </think>)
        - Markdown code blocks (```json or ```)
        - Plain JSON responses
        - Automatic fixing of Chinese quotes in JSON strings

        Returns:
            Dict: Parsed trading decisions, or empty dict if parsing fails
        """
        import re

        original_response = response
        response = response.strip()

        # Step 1: Check for <think> tags (case-insensitive)
        # Pattern matches: <think>...</think> or <THINK>...</THINK>
        think_pattern = r'<think>.*?</think>'
        think_match = re.search(think_pattern, response, re.IGNORECASE | re.DOTALL)

        if think_match:
            # Extract content after </think> tag
            think_end_pos = think_match.end()
            response = response[think_end_pos:].strip()
            print(f"[DEBUG] Detected <think> tag, extracted {len(response)} chars after </think>")
            print(f"[DEBUG] Extracted content preview: {response[:200]}...")

        # Step 2: Handle markdown code blocks
        if '```json' in response:
            # Extract content between ```json and ```
            parts = response.split('```json')
            if len(parts) > 1:
                response = parts[1].split('```')[0]
                print(f"[DEBUG] Extracted JSON from ```json code block")
        elif '```' in response:
            # Extract content between ``` and ```
            parts = response.split('```')
            if len(parts) >= 3:
                response = parts[1]
                print(f"[DEBUG] Extracted content from ``` code block")

        # Step 3: Clean up whitespace and fix common JSON issues
        response = response.strip()

        # Step 3.1: Fix quotes that break JSON parsing
        # This is THE CRITICAL FIX for AI models that use quotes incorrectly in their responses
        #
        # Problem 1: Chinese quotes like "text" break JSON parsing
        # Problem 2: Unescaped ASCII quotes like "value with "quotes" inside" also break parsing
        #
        # Solution: Replace problematic quotes with English single quotes

        # Use Unicode code points to avoid encoding issues
        left_dq = '\u201c'  # " (left Chinese double quotation mark)
        right_dq = '\u201d'  # " (right Chinese double quotation mark)
        left_sq = '\u2018'  # ' (left Chinese single quotation mark)
        right_sq = '\u2019'  # ' (right Chinese single quotation mark)

        # Fix Chinese quotes
        if left_dq in response or right_dq in response or left_sq in response or right_sq in response:
            print(f"[DEBUG] Detected Chinese quotes, fixing...")
            response = response.replace(left_dq, "'").replace(right_dq, "'")
            response = response.replace(left_sq, "'").replace(right_sq, "'")
            print(f"[DEBUG] Fixed Chinese quotes")

        # Fix unescaped ASCII quotes inside JSON string values
        # This is a CRITICAL fix for AI models that don't properly escape quotes in JSON strings
        # Example problem: "text": "value with "quotes" inside"
        # Solution: Replace inner quotes with single quotes: "value with 'quotes' inside"

        def fix_unescaped_quotes_in_values(json_str):
            """
            Fix unescaped double quotes inside JSON string values
            Uses regex to match ": "value" patterns and replace quotes within values
            """
            import re

            def fix_value(match):
                prefix = match.group(1)  # ": "
                value = match.group(2)    # value content
                suffix = match.group(3)   # closing " followed by , } or ]

                # In value, replace unescaped quotes with single quotes
                # First protect already escaped quotes
                fixed = value.replace('\\"', '<<<ESCAPED_QUOTE>>>')
                # Replace remaining quotes with single quotes
                fixed = fixed.replace('"', "'")
                # Restore escaped quotes
                fixed = fixed.replace('<<<ESCAPED_QUOTE>>>', '\\"')

                return f'{prefix}{fixed}"{suffix}'

            # Match: ": "value content" where value content ends at a quote followed by comma/brace/bracket
            # Pattern explanation:
            # (:\s*")  - Capture group 1: colon, optional whitespace, opening quote
            # (.+?)    - Capture group 2: value content (non-greedy)
            # "\s*     - Closing quote, optional whitespace
            # ([,\}\]]) - Capture group 3: comma, closing brace, or closing bracket
            pattern = r'(:\s*")(.+?)"\s*([,\}\]])'

            fixed = re.sub(pattern, fix_value, json_str, flags=re.DOTALL)

            return fixed

        # Apply the fix
        try:
            original_response = response
            response = fix_unescaped_quotes_in_values(response)
            if response != original_response:
                print(f"[DEBUG] Applied unescaped quote fix")
        except Exception as e:
            print(f"[WARNING] Failed to apply unescaped quote fix: {e}")
            # Continue with original response if fix fails

        # Step 4: Try to parse JSON
        try:
            decisions = json.loads(response)

            # Validate that we got a dictionary
            if not isinstance(decisions, dict):
                print(f"[WARNING] Parsed JSON is not a dict: {type(decisions)}")
                return {}

            # Validate that it's not empty
            if not decisions:
                print(f"[WARNING] Parsed JSON is empty dict")
                return {}

            print(f"[SUCCESS] Successfully parsed {len(decisions)} trading decisions")
            return decisions

        except json.JSONDecodeError as e:
            print(f"[ERROR] JSON parse failed: {e}")
            print(f"[ERROR] Parse error at position {e.pos}: {e.msg}")

            # Show context around error position
            if hasattr(e, 'pos') and e.pos:
                start = max(0, e.pos - 50)
                end = min(len(response), e.pos + 50)
                context = response[start:end]
                print(f"[ERROR] Context around error: ...{context}...")

            # Show first 500 chars of what we tried to parse
            print(f"[DATA] Attempted to parse (first 500 chars):\n{response[:500]}")

            # If original response had <think> tags, show that info
            if think_match:
                print(f"[INFO] Original response contained <think> tags")
                print(f"[INFO] Original response length: {len(original_response)} chars")

            return {}