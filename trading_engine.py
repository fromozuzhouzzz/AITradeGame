from datetime import datetime
from typing import Dict
import json

# ============================================================
# 交易开关配置 - 在这里设置做多/做空功能和置信度阈值
# ============================================================
# 1 = 启用该功能, 0 = 禁用该功能
ENABLE_LONG_TRADING = 1   # 做多开关 (buy_to_enter)
ENABLE_SHORT_TRADING = 1  # 做空开关 (sell_to_enter)

# 最低置信度阈值 - 只有 confidence 严格大于此值才会执行交易操作
# 适用于所有交易操作: buy_to_enter, sell_to_enter, add_position, reduce_position, close_position
MIN_CONFIDENCE_THRESHOLD = 0.7  # 默认0.7，可调整为0.5-0.8之间
MIN_CASH_RESERVE_RATIO = 0.2  # 最低现金储备比例，确保至少保留20%的总资产作为现金储备
# ============================================================
MAX_LEVERAGE = 1
ENABLE_TRADING_FEES = 1
TRADING_FEE_RATE = 0.001

# ============================================================
# 盈利保护配置（执行层分级止盈/回撤减仓）
# ============================================================
# 是否启用盈利保护功能
PROFIT_PROTECTION_ENABLED = True

# 每一级盈利回撤的步长（例如 0.10 = 从历史最高浮盈回撤 10%）
PROFIT_PROTECTION_STEP = 0.10

# 启动盈利保护所需的最低持仓盈利百分比
# 基于名义仓位金额 quantity * price（已经包含杠杆），例如 0.10 = 先赚到 10% 再开始保护
MIN_PROTECTION_PROFIT_PCT = 0.10

# 启动盈利保护所需的最低浮盈金额（单位：账户货币，例如 5000 表示单笔盈利达到 5000 即可）
# 启动条件为：满足「收益率 >= MIN_PROTECTION_PROFIT_PCT」或「浮盈金额 >= MIN_PROTECTION_PROFIT_AMOUNT」其一即可
MIN_PROTECTION_PROFIT_AMOUNT = 5000.0

# 最小可保护仓位数量（小于 2×该数量时，直接一次性全部平掉）
MIN_PROTECTION_POSITION_QUANTITY = 0.0001

class TradingEngine:
    def __init__(self, model_id: int, db, market_fetcher, ai_trader):
        self.model_id = model_id
        self.db = db
        self.market_fetcher = market_fetcher
        self.ai_trader = ai_trader
        self.coins = ['ETH', 'SOL', 'BNB', 'XRP']
        self.profit_protection_state = {}
    
    def execute_trading_cycle(self, market_state: Dict = None) -> Dict:
        """
        Execute one trading cycle for this model

        Args:
            market_state: Optional pre-fetched market state (for multi-model optimization)
                         If None, will fetch fresh data

        Returns:
            Dict with execution results
        """
        # 初始化变量，确保在异常情况下也能记录对话
        user_prompt = ""
        ai_response = ""
        cot_trace = ""

        try:
            # Use provided market state or fetch fresh data
            if market_state is None:
                print(f"[Model {self.model_id}] Fetching fresh market state")
                market_state = self._get_market_state()
            else:
                print(f"[Model {self.model_id}] Using shared market snapshot")

            current_prices = {coin: market_state[coin]['price'] for coin in market_state}

            portfolio = self.db.get_portfolio(self.model_id, current_prices)

            account_info = self._build_account_info(portfolio)

            # 构建prompt（用于记录）
            user_prompt = self._format_prompt(market_state, portfolio, account_info)

            # AI决策返回包含原始响应和解析后的决策
            ai_result = self.ai_trader.make_decision(
                market_state, portfolio, account_info
            )

            # 提取决策和原始响应
            decisions = ai_result.get('decisions', {})
            raw_response = ai_result.get('raw_response', '')
            is_fallback = ai_result.get('is_fallback', False)

            # 准备要保存的AI响应
            # 始终保存纯JSON格式，以便前端能够正确解析和显示为卡片式布局
            ai_response = json.dumps(decisions, ensure_ascii=False, indent=2)
            cot_trace = f"[FALLBACK]" if is_fallback else ""

            # 保存完整的对话记录（包含AI的思考过程）
            self.db.add_conversation(
                self.model_id,
                user_prompt=user_prompt,
                ai_response=ai_response,
                cot_trace=cot_trace
            )
            print(f"[DB] Saved conversation for Model {self.model_id}")

            execution_results = self._execute_decisions(decisions, market_state, portfolio)

            updated_portfolio = self.db.get_portfolio(self.model_id, current_prices)

            if PROFIT_PROTECTION_ENABLED:
                protection_results = self._apply_profit_protection(updated_portfolio, market_state)
                if protection_results:
                    execution_results.extend(protection_results)
                    updated_portfolio = self.db.get_portfolio(self.model_id, current_prices)

            self.db.record_account_value(
                self.model_id,
                updated_portfolio['total_value'],
                updated_portfolio['cash'],
                updated_portfolio['positions_value']
            )

            return {
                'success': True,
                'decisions': decisions,
                'executions': execution_results,
                'portfolio': updated_portfolio
            }

        except Exception as e:
            print(f"[ERROR] Trading cycle failed (Model {self.model_id}): {e}")
            import traceback
            print(traceback.format_exc())

            # 即使发生异常，也要记录错误信息到对话记录
            error_message = f"[ERROR] 交易周期执行失败:\n\n{str(e)}\n\n{traceback.format_exc()}"

            try:
                # 如果user_prompt还没有构建，使用简化版本
                if not user_prompt:
                    user_prompt = f"[ERROR] 无法构建完整的市场状态提示"

                self.db.add_conversation(
                    self.model_id,
                    user_prompt=user_prompt,
                    ai_response=error_message,
                    cot_trace="[ERROR]"
                )
                print(f"[DB] Saved error conversation for Model {self.model_id}")
            except Exception as db_error:
                print(f"[ERROR] Failed to save error conversation: {db_error}")

            return {
                'success': False,
                'error': str(e)
            }
    
    def _get_market_state(self) -> Dict:
        """
        Get market state with session snapshot optimization

        This method now prioritizes using the session snapshot to avoid
        redundant API calls when multiple models are running in the same cycle.
        """
        # OPTIMIZATION: Try to use session snapshot first
        if self.market_fetcher._current_session_id:
            snapshot = self.market_fetcher.get_session_snapshot()
            if snapshot and 'market_state' in snapshot:
                print(f"[Model {self.model_id}] Using session snapshot (avoiding API calls)")
                return snapshot['market_state']

        # Fallback: Fetch fresh data if no session snapshot available
        print(f"[Model {self.model_id}] No session snapshot, fetching fresh data")
        return self.market_fetcher.get_market_state_for_all_models(self.coins, use_session=True)
    
    def _build_account_info(self, portfolio: Dict) -> Dict:
        model = self.db.get_model(self.model_id)
        initial_capital = model['initial_capital']
        total_value = portfolio['total_value']
        total_return = ((total_value - initial_capital) / initial_capital) * 100
        
        return {
            'current_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'total_return': total_return,
            'initial_capital': initial_capital
        }
    
    def _format_prompt(self, market_state: Dict, portfolio: Dict, 
                      account_info: Dict) -> str:
        return f"Market State: {len(market_state)} coins, Portfolio: {len(portfolio['positions'])} positions"
    
    def _apply_profit_protection(self, portfolio: Dict, market_state: Dict) -> list:
        results = []
        positions = portfolio.get('positions', [])
        if not positions:
            return results

        current_prices = {}
        for coin, data in market_state.items():
            price = data.get('price')
            if price is not None and price > 0:
                current_prices[coin] = price

        if not current_prices:
            return results

        active_keys = set()
        for pos in positions:
            if pos['quantity'] > 0:
                active_keys.add((pos['coin'], pos['side']))

        stale_keys = [k for k in self.profit_protection_state.keys() if k not in active_keys]
        for k in stale_keys:
            del self.profit_protection_state[k]

        for pos in positions:
            coin = pos['coin']
            side = pos['side']
            quantity = pos['quantity']
            if quantity <= 0:
                key = (coin, side)
                if key in self.profit_protection_state:
                    del self.profit_protection_state[key]
                continue

            if coin not in current_prices:
                continue

            current_pnl = float(pos.get('pnl', 0.0))
            entry_value = pos['quantity'] * pos['avg_price']
            if entry_value <= 0:
                continue

            key = (coin, side)
            state = self.profit_protection_state.get(key)

            # 首次达到“足够大的盈利”才开始跟踪回撤
            if state is None:
                if current_pnl <= 0:
                    # 还没有真正盈利，不启动保护
                    continue

                # 持仓收益率（基于名义仓位金额 quantity * price，例如 0.10 = 10%）
                profit_pct = current_pnl / entry_value
                meets_pct = profit_pct >= MIN_PROTECTION_PROFIT_PCT

                # 浮盈金额是否超过绝对门槛（例如 5000）
                meets_amount = MIN_PROTECTION_PROFIT_AMOUNT > 0 and current_pnl >= MIN_PROTECTION_PROFIT_AMOUNT

                # 启动条件：收益率 或 绝对金额 满足其一即可
                if not (meets_pct or meets_amount):
                    continue

                self.profit_protection_state[key] = {
                    'peak_unrealized_pnl': current_pnl
                }
                continue

            peak_unrealized_pnl = state.get('peak_unrealized_pnl', 0.0)

            if current_pnl > peak_unrealized_pnl:
                peak_unrealized_pnl = current_pnl
                state['peak_unrealized_pnl'] = peak_unrealized_pnl

            if peak_unrealized_pnl <= 0:
                continue
            drawdown_amount = peak_unrealized_pnl - current_pnl
            if drawdown_amount <= 0:
                continue

            drawdown_fraction = drawdown_amount / peak_unrealized_pnl
            if drawdown_fraction < PROFIT_PROTECTION_STEP:
                continue

            latest_portfolio = self.db.get_portfolio(self.model_id, current_prices)
            latest_position = None
            for p in latest_portfolio['positions']:
                if p['coin'] == coin and p['side'] == side:
                    latest_position = p
                    break

            if not latest_position:
                if key in self.profit_protection_state:
                    del self.profit_protection_state[key]
                continue

            latest_quantity = latest_position['quantity']
            if latest_quantity <= 0:
                if key in self.profit_protection_state:
                    del self.profit_protection_state[key]
                continue

            if latest_quantity <= MIN_PROTECTION_POSITION_QUANTITY * 2:
                reduce_quantity = latest_quantity
            else:
                reduce_quantity = latest_quantity / 2.0

            decision = {
                'quantity': reduce_quantity,
                '__source': 'profit_protection'
            }
            result = self._execute_reduce_position(coin, decision, market_state, latest_portfolio)
            results.append(result)

            refreshed_portfolio = self.db.get_portfolio(self.model_id, current_prices)
            new_position = None
            for p in refreshed_portfolio['positions']:
                if p['coin'] == coin and p['side'] == side:
                    new_position = p
                    break

            if new_position and new_position['quantity'] > 0:
                new_pnl = float(new_position.get('pnl', 0.0))
                self.profit_protection_state[key]['peak_unrealized_pnl'] = new_pnl if new_pnl > 0 else 0.0
            else:
                if key in self.profit_protection_state:
                    del self.profit_protection_state[key]

        return results
    
    def _execute_decisions(self, decisions: Dict, market_state: Dict,
                          portfolio: Dict) -> list:
        results = []
        total_value = portfolio.get('total_value', 0)
        if total_value > 0:
            portfolio['_min_cash_reserve'] = total_value * MIN_CASH_RESERVE_RATIO
        else:
            portfolio['_min_cash_reserve'] = 0.0
        portfolio['_dynamic_cash'] = portfolio.get('cash', 0.0)

        for coin, decision in decisions.items():
            if coin not in self.coins:
                continue

            signal = decision.get('signal', '').lower()
            confidence = float(decision.get('confidence', 0))

            try:
                # 检查所有交易操作的置信度，必须严格大于阈值才能执行
                if signal in ('buy_to_enter', 'sell_to_enter', 'add_position', 'reduce_position', 'close_position') and confidence < MIN_CONFIDENCE_THRESHOLD:
                    message = f'Low confidence {confidence:.2f} (threshold: {MIN_CONFIDENCE_THRESHOLD}) for {signal}, forcing HOLD'
                    result = {'coin': coin, 'signal': 'hold', 'message': message}
                elif signal == 'buy_to_enter':
                    if ENABLE_LONG_TRADING == 1:
                        result = self._execute_buy(coin, decision, market_state, portfolio)
                    else:
                        result = {
                            'coin': coin,
                            'signal': 'hold',
                            'message': 'Long trading disabled (ENABLE_LONG_TRADING=0)'
                        }
                elif signal == 'sell_to_enter':
                    if ENABLE_SHORT_TRADING == 1:
                        result = self._execute_sell(coin, decision, market_state, portfolio)
                    else:
                        result = {
                            'coin': coin,
                            'signal': 'hold',
                            'message': 'Short trading disabled (ENABLE_SHORT_TRADING=0)'
                        }
                elif signal == 'add_position':
                    # Check position side before allowing add_position
                    position = None
                    for pos in portfolio['positions']:
                        if pos['coin'] == coin:
                            position = pos
                            break
                    
                    if position:
                        if position['side'] == 'long' and ENABLE_LONG_TRADING == 0:
                            result = {
                                'coin': coin,
                                'signal': 'hold',
                                'message': 'Cannot add to long position (ENABLE_LONG_TRADING=0)'
                            }
                        elif position['side'] == 'short' and ENABLE_SHORT_TRADING == 0:
                            result = {
                                'coin': coin,
                                'signal': 'hold',
                                'message': 'Cannot add to short position (ENABLE_SHORT_TRADING=0)'
                            }
                        else:
                            result = self._execute_add_position(coin, decision, market_state, portfolio)
                    else:
                        result = {'coin': coin, 'error': 'No existing position to add to'}
                elif signal == 'reduce_position':
                    result = self._execute_reduce_position(coin, decision, market_state, portfolio)
                elif signal == 'close_position':
                    result = self._execute_close(coin, decision, market_state, portfolio)
                elif signal == 'hold':
                    # 增强hold信号的消息,包含持仓信息
                    position = None
                    for pos in portfolio['positions']:
                        if pos['coin'] == coin:
                            position = pos
                            break

                    if position:
                        # 有持仓 - 显示持仓信息
                        unrealized_pnl = position.get('unrealized_pnl', 0)
                        pnl_pct = (unrealized_pnl / (position['quantity'] * position['avg_price'])) * 100 if position['quantity'] > 0 else 0
                        side = position['side']
                        message = f"Hold {side} position ({position['quantity']:.4f} @ ${position['avg_price']:.2f}, P&L: ${unrealized_pnl:.2f} / {pnl_pct:+.2f}%)"
                    else:
                        # 无持仓 - 观望
                        message = 'Hold (no position, waiting for better entry)'

                    result = {'coin': coin, 'signal': 'hold', 'message': message}
                else:
                    result = {'coin': coin, 'error': f'Unknown signal: {signal}'}

                results.append(result)

            except Exception as e:
                results.append({'coin': coin, 'error': str(e)})

        return results
    
    def _execute_buy(self, coin: str, decision: Dict, market_state: Dict, 
                    portfolio: Dict) -> Dict:
        quantity = float(decision.get('quantity', 0))
        leverage = int(decision.get('leverage', 1))
        if leverage < 1:
            leverage = 1
        if leverage > MAX_LEVERAGE:
            leverage = MAX_LEVERAGE
        price = market_state[coin]['price']
        if price is None or price <= 0:
            return {
                'coin': coin,
                'signal': 'hold',
                'message': f'Invalid market price {price} for buy_to_enter, skipping execution'
            }

        if quantity <= 0:
            return {'coin': coin, 'error': 'Invalid quantity'}
        
        required_margin = (quantity * price) / leverage
        dynamic_cash = portfolio.get('_dynamic_cash', portfolio.get('cash', 0.0))
        min_cash_reserve = portfolio.get('_min_cash_reserve', 0.0)
        max_spendable = dynamic_cash - min_cash_reserve
        if max_spendable < 0:
            max_spendable = 0.0
        if required_margin > max_spendable:
            return {'coin': coin, 'error': 'Insufficient cash'}
        portfolio['_dynamic_cash'] = dynamic_cash - required_margin

        self.db.update_position(
            self.model_id, coin, quantity, price, leverage, 'long'
        )
        
        fee = 0.0
        if ENABLE_TRADING_FEES == 1 and TRADING_FEE_RATE > 0:
            fee = quantity * price * TRADING_FEE_RATE

        trade_pnl = -fee

        self.db.add_trade(
            self.model_id, coin, 'buy_to_enter', quantity, 
            price, leverage, 'long', pnl=trade_pnl
        )
        
        return {
            'coin': coin,
            'signal': 'buy_to_enter',
            'quantity': quantity,
            'price': price,
            'leverage': leverage,
            'message': f'Long {quantity:.4f} {coin} @ ${price:.2f}'
        }
    
    def _execute_sell(self, coin: str, decision: Dict, market_state: Dict, 
                     portfolio: Dict) -> Dict:
        quantity = float(decision.get('quantity', 0))
        leverage = int(decision.get('leverage', 1))
        if leverage < 1:
            leverage = 1
        if leverage > MAX_LEVERAGE:
            leverage = MAX_LEVERAGE
        price = market_state[coin]['price']
        if price is None or price <= 0:
            return {
                'coin': coin,
                'signal': 'hold',
                'message': f'Invalid market price {price} for sell_to_enter, skipping execution'
            }

        if quantity <= 0:
            return {'coin': coin, 'error': 'Invalid quantity'}
        
        required_margin = (quantity * price) / leverage
        dynamic_cash = portfolio.get('_dynamic_cash', portfolio.get('cash', 0.0))
        min_cash_reserve = portfolio.get('_min_cash_reserve', 0.0)
        max_spendable = dynamic_cash - min_cash_reserve
        if max_spendable < 0:
            max_spendable = 0.0
        if required_margin > max_spendable:
            return {'coin': coin, 'error': 'Insufficient cash'}
        portfolio['_dynamic_cash'] = dynamic_cash - required_margin

        self.db.update_position(
            self.model_id, coin, quantity, price, leverage, 'short'
        )
        
        fee = 0.0
        if ENABLE_TRADING_FEES == 1 and TRADING_FEE_RATE > 0:
            fee = quantity * price * TRADING_FEE_RATE

        trade_pnl = -fee

        self.db.add_trade(
            self.model_id, coin, 'sell_to_enter', quantity, 
            price, leverage, 'short', pnl=trade_pnl
        )
        
        return {
            'coin': coin,
            'signal': 'sell_to_enter',
            'quantity': quantity,
            'price': price,
            'leverage': leverage,
            'message': f'Short {quantity:.4f} {coin} @ ${price:.2f}'
        }
    
    def _execute_add_position(self, coin: str, decision: Dict, market_state: Dict,
                             portfolio: Dict) -> Dict:
        """加仓：增加现有持仓的数量"""
        # 查找现有持仓
        position = None
        for pos in portfolio['positions']:
            if pos['coin'] == coin:
                position = pos
                break

        if not position:
            return {'coin': coin, 'error': 'No existing position to add to'}

        quantity = float(decision.get('quantity', 0))
        leverage = int(decision.get('leverage', position['leverage']))  # 使用现有杠杆或新杠杆
        if leverage < 1:
            leverage = 1
        if leverage > MAX_LEVERAGE:
            leverage = MAX_LEVERAGE
        price = market_state[coin]['price']
        side = position['side']

        if price is None or price <= 0:
            return {
                'coin': coin,
                'signal': 'hold',
                'message': f'Invalid market price {price} for add_position, skipping execution'
            }

        if quantity <= 0:
            return {'coin': coin, 'error': 'Invalid quantity'}

        required_margin = (quantity * price) / leverage
        dynamic_cash = portfolio.get('_dynamic_cash', portfolio.get('cash', 0.0))
        min_cash_reserve = portfolio.get('_min_cash_reserve', 0.0)
        max_spendable = dynamic_cash - min_cash_reserve
        if max_spendable < 0:
            max_spendable = 0.0
        if required_margin > max_spendable:
            return {'coin': coin, 'error': 'Insufficient cash'}
        portfolio['_dynamic_cash'] = dynamic_cash - required_margin

        # 更新持仓（增加数量）
        self.db.update_position(
            self.model_id, coin, quantity, price, leverage, side
        )

        fee = 0.0
        if ENABLE_TRADING_FEES == 1 and TRADING_FEE_RATE > 0:
            fee = quantity * price * TRADING_FEE_RATE

        trade_pnl = -fee

        # 记录交易
        self.db.add_trade(
            self.model_id, coin, 'add_position', quantity,
            price, leverage, side, pnl=trade_pnl
        )

        return {
            'coin': coin,
            'signal': 'add_position',
            'quantity': quantity,
            'price': price,
            'leverage': leverage,
            'side': side,
            'message': f'Add {side} position: {quantity:.4f} {coin} @ ${price:.2f}'
        }

    def _execute_reduce_position(self, coin: str, decision: Dict, market_state: Dict,
                                 portfolio: Dict) -> Dict:
        """减仓：减少现有持仓的数量"""
        # 查找现有持仓
        position = None
        for pos in portfolio['positions']:
            if pos['coin'] == coin:
                position = pos
                break

        if not position:
            return {'coin': coin, 'error': 'No existing position to reduce'}

        quantity = float(decision.get('quantity', 0))
        source = decision.get('__source')
        current_price = market_state[coin]['price']
        entry_price = position['avg_price']
        current_quantity = position['quantity']
        side = position['side']

        if current_price is None or current_price <= 0:
            return {
                'coin': coin,
                'signal': 'hold',
                'message': f'Invalid market price {current_price} for reduce_position, skipping execution'
            }

        if quantity <= 0:
            return {'coin': coin, 'error': 'Invalid quantity'}

        if quantity > current_quantity:
            return {'coin': coin, 'error': f'Cannot reduce {quantity}, only have {current_quantity}'}

        # 计算部分平仓的盈亏
        if side == 'long':
            raw_pnl = (current_price - entry_price) * quantity
        else:
            raw_pnl = (entry_price - current_price) * quantity

        fee = 0.0
        if ENABLE_TRADING_FEES == 1 and TRADING_FEE_RATE > 0:
            fee = quantity * current_price * TRADING_FEE_RATE

        pnl = raw_pnl - fee

        # 如果减仓数量等于持仓数量，则完全平仓
        if abs(quantity - current_quantity) < 0.0001:
            self.db.close_position(self.model_id, coin, side)
        else:
            # 部分减仓：更新持仓数量（使用负数表示减少）
            self.db.update_position(
                self.model_id, coin, -quantity, current_price,
                position['leverage'], side
            )

        # 记录交易
        self.db.add_trade(
            self.model_id, coin, 'reduce_position', quantity,
            current_price, position['leverage'], side, pnl=pnl
        )

        if source == 'profit_protection':
            message = (
                f"【盈利保护】自动减仓：{side} 仓位减仓 {quantity:.4f} {coin} "
                f"@ ${current_price:.2f}，本次实现盈亏 ${pnl:.2f}"
            )
        else:
            message = (
                f"Reduce {side} position: {quantity:.4f} {coin} "
                f"@ ${current_price:.2f}, P&L: ${pnl:.2f}"
            )

        result = {
            'coin': coin,
            'signal': 'reduce_position',
            'quantity': quantity,
            'price': current_price,
            'pnl': pnl,
            'side': side,
            'message': message
        }

        if source:
            result['source'] = source

        return result

    def _execute_close(self, coin: str, decision: Dict, market_state: Dict,
                      portfolio: Dict) -> Dict:
        position = None
        for pos in portfolio['positions']:
            if pos['coin'] == coin:
                position = pos
                break

        if not position:
            return {'coin': coin, 'error': 'Position not found'}

        current_price = market_state[coin]['price']
        entry_price = position['avg_price']
        quantity = position['quantity']
        side = position['side']

        if current_price is None or current_price <= 0:
            return {
                'coin': coin,
                'signal': 'hold',
                'message': f'Invalid market price {current_price} for close_position, skipping execution'
            }

        if side == 'long':
            raw_pnl = (current_price - entry_price) * quantity
        else:
            raw_pnl = (entry_price - current_price) * quantity

        fee = 0.0
        if ENABLE_TRADING_FEES == 1 and TRADING_FEE_RATE > 0:
            fee = quantity * current_price * TRADING_FEE_RATE

        pnl = raw_pnl - fee

        self.db.close_position(self.model_id, coin, side)

        self.db.add_trade(
            self.model_id, coin, 'close_position', quantity,
            current_price, position['leverage'], side, pnl=pnl
        )

        return {
            'coin': coin,
            'signal': 'close_position',
            'quantity': quantity,
            'price': current_price,
            'pnl': pnl,
            'message': f'Close {coin}, P&L: ${pnl:.2f}'
        }
