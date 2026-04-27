from flask import Flask, render_template, request, jsonify
from flask_cors import CORS
import time
import threading
import os
from datetime import datetime

from trading_engine import TradingEngine
from market_data import MarketDataFetcher
from ai_trader import AITrader
from database import Database

app = Flask(__name__)
CORS(app)

# Initialize database
db = Database('trading_bot.db')

# Initialize market fetcher with optional proxy
# Set proxy via environment variable: CRYPTO_PROXY="http://proxy.com:8080"
proxy = os.environ.get('CRYPTO_PROXY', None)
market_fetcher = MarketDataFetcher(proxy=proxy)

if proxy:
    print(f"[INFO] Using proxy: {proxy}")

trading_engines = {}
auto_trading = True

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/conversations/<int:model_id>')
def conversations_page(model_id):
    """完整对话页面"""
    return render_template('conversations.html', model_id=model_id)

@app.route('/api/models', methods=['GET'])
def get_models():
    models = db.get_all_models()
    return jsonify(models)

@app.route('/api/models/<int:model_id>', methods=['GET'])
def get_model(model_id):
    model = db.get_model(model_id)
    if not model:
        return jsonify({'error': 'Model not found'}), 404
    return jsonify(model)

@app.route('/api/models', methods=['POST'])
def add_model():
    data = request.json
    model_id = db.add_model(
        name=data['name'],
        api_key=data['api_key'],
        api_url=data['api_url'],
        model_name=data['model_name'],
        initial_capital=float(data.get('initial_capital', 100000))
    )
    
    try:
        model = db.get_model(model_id)
        trading_engines[model_id] = TradingEngine(
            model_id=model_id,
            db=db,
            market_fetcher=market_fetcher,
            ai_trader=AITrader(
                api_key=model['api_key'],
                api_url=model['api_url'],
                model_name=model['model_name']
            )
        )
        print(f"[INFO] Model {model_id} ({data['name']}) initialized")
    except Exception as e:
        print(f"[ERROR] Model {model_id} initialization failed: {e}")
    
    return jsonify({'id': model_id, 'message': 'Model added successfully'})

@app.route('/api/models/<int:model_id>', methods=['PUT'])
def update_model(model_id):
    try:
        data = request.json
        model = db.get_model(model_id)

        if not model:
            return jsonify({'error': 'Model not found'}), 404

        # Update model configuration
        db.update_model(
            model_id=model_id,
            name=data.get('name'),
            api_key=data.get('api_key'),
            api_url=data.get('api_url'),
            model_name=data.get('model_name')
        )

        # Reload the trading engine if it exists
        if model_id in trading_engines:
            updated_model = db.get_model(model_id)
            trading_engines[model_id].ai_trader = AITrader(
                api_key=updated_model['api_key'],
                api_url=updated_model['api_url'],
                model_name=updated_model['model_name']
            )

        print(f"[INFO] Model {model_id} ({data.get('name', model['name'])}) updated")
        return jsonify({'message': 'Model updated successfully'})
    except Exception as e:
        print(f"[ERROR] Update model {model_id} failed: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/models/<int:model_id>', methods=['DELETE'])
def delete_model(model_id):
    try:
        model = db.get_model(model_id)
        model_name = model['name'] if model else f"ID-{model_id}"

        db.delete_model(model_id)
        if model_id in trading_engines:
            del trading_engines[model_id]

        print(f"[INFO] Model {model_id} ({model_name}) deleted")
        return jsonify({'message': 'Model deleted successfully'})
    except Exception as e:
        print(f"[ERROR] Delete model {model_id} failed: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/models/<int:model_id>/portfolio', methods=['GET'])
def get_portfolio(model_id):
    try:
        prices_data = market_fetcher.get_current_prices(['ETH', 'SOL', 'BNB', 'XRP'])
        current_prices = {coin: prices_data[coin]['price'] for coin in prices_data}

        portfolio = db.get_portfolio(model_id, current_prices)
        account_value = db.get_account_value_history(model_id, limit=100)

        return jsonify({
            'portfolio': portfolio,
            'account_value_history': account_value
        })
    except Exception as e:
        print(f"[API ERROR] get_portfolio: {e}")
        return jsonify({'error': 'Database temporarily unavailable, please retry'}), 503

@app.route('/api/models/<int:model_id>/account_history', methods=['GET'])
def get_account_history(model_id):
    """
    获取账户价值历史数据（支持不同时间周期）

    Query Parameters:
        timeframe: 时间周期 ('1m', '3m', '5m', '15m', '30m', '1h', '4h', '1d', '1w', '1M')
        limit: 数据点数量限制（默认100）
    """
    timeframe = request.args.get('timeframe', '1m')
    limit = request.args.get('limit', 100, type=int)

    # 验证timeframe参数
    valid_timeframes = ['1m', '3m', '5m', '15m', '30m', '1h', '4h', '1d', '1w', '1M']
    if timeframe not in valid_timeframes:
        return jsonify({'error': f'Invalid timeframe. Must be one of: {", ".join(valid_timeframes)}'}), 400

    try:
        account_history = db.get_account_value_history_by_timeframe(model_id, timeframe, limit)
        return jsonify({
            'timeframe': timeframe,
            'data': account_history
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/models/<int:model_id>/trades', methods=['GET'])
def get_trades(model_id):
    try:
        limit = request.args.get('limit', 50, type=int)
        trades = db.get_trades(model_id, limit=limit)
        return jsonify(trades)
    except Exception as e:
        print(f"[API ERROR] get_trades: {e}")
        return jsonify({'error': 'Database temporarily unavailable, please retry'}), 503

@app.route('/api/models/<int:model_id>/conversations', methods=['GET'])
def get_conversations(model_id):
    try:
        limit = request.args.get('limit', 20, type=int)
        conversations = db.get_conversations(model_id, limit=limit)
        return jsonify(conversations)
    except Exception as e:
        print(f"[API ERROR] get_conversations: {e}")
        return jsonify({'error': 'Database temporarily unavailable, please retry'}), 503

@app.route('/api/market/prices', methods=['GET'])
def get_market_prices():
    """
    获取市场价格（前端API）

    优化策略：
    1. 优先使用当前活跃的session快照（如果存在）
    2. 如果没有活跃session，则使用get_current_prices的内存缓存（5秒）
    3. 这样可以避免在模型决策期间触发额外的API调用
    """
    coins = ['ETH', 'SOL', 'BNB', 'XRP']

    # 尝试从活跃的session快照中获取价格
    if market_fetcher._current_session_id:
        snapshot = market_fetcher.get_session_snapshot()
        if snapshot and 'market_state' in snapshot:
            # 从market_state中提取价格数据
            prices = {}
            for coin in coins:
                if coin in snapshot['market_state']:
                    prices[coin] = {
                        'price': snapshot['market_state'][coin]['price'],
                        'change_24h': snapshot['market_state'][coin].get('change_24h', 0)
                    }

            if prices:
                print(f"[API] /api/market/prices using session snapshot {market_fetcher._current_session_id}")
                return jsonify(prices)

    # 如果没有活跃session，使用常规缓存机制
    prices = market_fetcher.get_current_prices(coins)
    return jsonify(prices)

@app.route('/api/market/health', methods=['GET'])
def get_market_health():
    """Get API health status"""
    health = market_fetcher.get_api_health_status()
    return jsonify(health)

@app.route('/api/models/<int:model_id>/execute', methods=['POST'])
def execute_trading(model_id):
    if model_id not in trading_engines:
        model = db.get_model(model_id)
        if not model:
            return jsonify({'error': 'Model not found'}), 404
        
        trading_engines[model_id] = TradingEngine(
            model_id=model_id,
            db=db,
            market_fetcher=market_fetcher,
            ai_trader=AITrader(
                api_key=model['api_key'],
                api_url=model['api_url'],
                model_name=model['model_name']
            )
        )
    
    try:
        result = trading_engines[model_id].execute_trading_cycle()
        return jsonify(result)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

def trading_loop():
    print("[INFO] Trading loop started with multi-model optimization")

    while auto_trading:
        try:
            # ============ Health Check: Verify all models are initialized ============
            all_models = db.get_all_models()
            active_model_ids = set(trading_engines.keys())
            db_model_ids = set(m['id'] for m in all_models)

            # Check for missing models
            missing_models = db_model_ids - active_model_ids
            if missing_models:
                print(f"\n[HEALTH CHECK] ⚠️  Detected {len(missing_models)} missing model(s): {missing_models}")
                print(f"[HEALTH CHECK] Attempting to re-initialize missing models...")

                for model_id in missing_models:
                    model = db.get_model(model_id)
                    if model:
                        print(f"\n[HEALTH CHECK] Re-initializing Model {model_id} ({model['name']})...")
                        try:
                            trading_engines[model_id] = TradingEngine(
                                model_id=model_id,
                                db=db,
                                market_fetcher=market_fetcher,
                                ai_trader=AITrader(
                                    api_key=model['api_key'],
                                    api_url=model['api_url'],
                                    model_name=model['model_name']
                                )
                            )
                            print(f"[HEALTH CHECK] ✅ Model {model_id} re-initialized successfully")
                        except Exception as e:
                            print(f"[HEALTH CHECK] ❌ Failed to re-initialize Model {model_id}: {e}")
                            import traceback
                            traceback.print_exc()

            if not trading_engines:
                print("[WARN] No active trading engines, waiting 30 seconds...")
                time.sleep(30)
                continue

            print(f"\n{'='*60}")
            print(f"[CYCLE] {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            print(f"[INFO] Active models: {len(trading_engines)} - IDs: {list(trading_engines.keys())}")
            print(f"{'='*60}")

            # ============ OPTIMIZATION: Session-level Data Snapshot ============
            # Start a new snapshot session for this trading cycle
            session_id = market_fetcher.start_session()
            print(f"[SESSION] Started new session: {session_id}")

            # Fetch market state ONCE for all models
            coins = ['ETH', 'SOL', 'BNB', 'XRP']
            print(f"[SESSION] Fetching unified market state for {len(coins)} coins (ONE-TIME API CALL)...")
            cycle_start_time = time.time()

            try:
                # This will be cached in the session snapshot
                shared_market_state = market_fetcher.get_market_state_for_all_models(coins)
                fetch_time = time.time() - cycle_start_time
                print(f"[SESSION] ✓ Market state cached in session snapshot ({fetch_time:.2f}s)")
                print(f"[SESSION] All {len(trading_engines)} models will now use this SHARED snapshot")
            except Exception as e:
                print(f"[SESSION ERROR] Failed to fetch market state: {e}")
                market_fetcher.end_session(session_id)
                time.sleep(60)
                continue

            # ============ Execute all models with shared data ============
            print(f"\n[EXECUTION] Starting {len(trading_engines)} models with SHARED data...")
            print(f"[EXECUTION] Models in this cycle: {list(trading_engines.keys())}")

            execution_summary = {
                'success': [],
                'failed': [],
                'trades': []
            }

            for model_id, engine in list(trading_engines.items()):
                try:
                    model_info = db.get_model(model_id)
                    model_name = model_info['name'] if model_info else 'Unknown'

                    print(f"\n[Model {model_id}] ({model_name}) Starting execution (using session {session_id})...")
                    model_start_time = time.time()

                    # Pass the shared market state to avoid redundant API calls
                    result = engine.execute_trading_cycle(market_state=shared_market_state)

                    model_elapsed = time.time() - model_start_time

                    if result.get('success'):
                        print(f"[Model {model_id}] ✓ Completed in {model_elapsed:.2f}s (used shared snapshot)")
                        execution_summary['success'].append(model_id)

                        if result.get('executions'):
                            # 统计交易信号
                            trade_count = 0
                            hold_count = 0
                            hold_details = []

                            # 环境变量控制是否显示详细hold信息 (默认true,显示详细)
                            show_hold_details = os.environ.get('SHOW_HOLD_DETAILS', 'true').lower() == 'true'

                            for exec_result in result['executions']:
                                signal = exec_result.get('signal', 'unknown')
                                coin = exec_result.get('coin', 'unknown')
                                msg = exec_result.get('message', '')

                                if signal != 'hold':
                                    print(f"  [TRADE] {coin}: {msg}")
                                    execution_summary['trades'].append(f"Model {model_id}: {coin} {signal}")
                                    trade_count += 1
                                else:
                                    hold_count += 1
                                    hold_details.append((coin, msg))

                            # 显示hold信息
                            if hold_count > 0:
                                if trade_count == 0:
                                    # 全部hold - 显示汇总
                                    print(f"  [HOLD] All {hold_count} positions held (no new trades)")
                                else:
                                    # 部分hold - 显示数量
                                    print(f"  [HOLD] {hold_count} positions held")

                                # 如果启用详细模式,显示每个hold的详情
                                if show_hold_details:
                                    for coin, msg in hold_details:
                                        print(f"    • {coin}: {msg}")
                    else:
                        error = result.get('error', 'Unknown error')
                        print(f"[Model {model_id}] ✗ Failed: {error}")
                        execution_summary['failed'].append(f"{model_id}: {error}")

                except Exception as e:
                    print(f"[Model {model_id}] ✗ Exception: {e}")
                    import traceback
                    print(traceback.format_exc())
                    continue

            # End the snapshot session
            market_fetcher.end_session(session_id)
            print(f"\n[SESSION] Ended session: {session_id}")

            # Print cycle summary with API call statistics and execution results
            cycle_elapsed = time.time() - cycle_start_time
            print(f"\n{'='*60}")
            print(f"[CYCLE SUMMARY]")
            print(f"  Session ID: {session_id}")
            print(f"  Total time: {cycle_elapsed:.2f}s")
            print(f"  Models executed: {len(trading_engines)}")
            print(f"  Avg time per model: {cycle_elapsed / len(trading_engines):.2f}s")
            print(f"  API optimization: ONE market data fetch shared by ALL models")

            # Execution results
            print(f"\n  Execution Results:")
            print(f"    ✅ Success: {len(execution_summary['success'])} models - {execution_summary['success']}")
            if execution_summary['failed']:
                print(f"    ❌ Failed: {len(execution_summary['failed'])} models")
                for failure in execution_summary['failed']:
                    print(f"       - {failure}")
            if execution_summary['trades']:
                print(f"    💰 Trades executed: {len(execution_summary['trades'])}")
                for trade in execution_summary['trades']:
                    print(f"       - {trade}")
            else:
                print(f"    💤 No trades executed (all HOLD)")

            # Get performance stats
            health = market_fetcher.get_api_health_status()
            print(f"\n  API Performance:")
            print(f"    API calls: {health.get('api_call_count', 0)}")
            print(f"    Snapshot hits: {health.get('snapshot_hit_count', 0)}")
            print(f"    Cache hit rate: {health.get('cache_hit_rate', 'N/A')}")
            print(f"{'='*60}")

            # 记录周期完成时间
            cycle_end_time = time.time()
            cycle_duration = cycle_end_time - cycle_start_time
            print(f"\n[CYCLE COMPLETE] Total duration: {cycle_duration:.2f}s")
            print(f"[SLEEP] Waiting 3 minutes for next cycle\n")
            time.sleep(180)

        except Exception as e:
            print(f"\n[CRITICAL] Trading loop error: {e}")
            import traceback
            print(traceback.format_exc())
            print("[RETRY] Retrying in 60 seconds\n")
            time.sleep(60)

    print("[INFO] Trading loop stopped")

@app.route('/api/leaderboard', methods=['GET'])
def get_leaderboard():
    models = db.get_all_models()
    leaderboard = []
    
    prices_data = market_fetcher.get_current_prices(['ETH', 'SOL', 'BNB', 'XRP'])
    current_prices = {coin: prices_data[coin]['price'] for coin in prices_data}
    
    for model in models:
        portfolio = db.get_portfolio(model['id'], current_prices)
        account_value = portfolio.get('total_value', model['initial_capital'])
        returns = ((account_value - model['initial_capital']) / model['initial_capital']) * 100
        
        leaderboard.append({
            'model_id': model['id'],
            'model_name': model['name'],
            'account_value': account_value,
            'returns': returns,
            'initial_capital': model['initial_capital']
        })
    
    leaderboard.sort(key=lambda x: x['returns'], reverse=True)
    return jsonify(leaderboard)

def init_trading_engines():
    """
    Initialize trading engines for all models in database

    This function will attempt to initialize each model with retry logic.
    If a model fails to initialize, it will be skipped but logged.
    """
    try:
        models = db.get_all_models()

        if not models:
            print("[WARN] No trading models found in database")
            return

        print(f"\n[INIT] Initializing {len(models)} trading engine(s)...")
        model_list = [f"{m['id']}({m['name']})" for m in models]
        print(f"[INIT] Models to initialize: {model_list}")

        for model in models:
            model_id = model['id']
            model_name = model['name']

            print(f"\n[INIT] Initializing Model {model_id} ({model_name})...")
            print(f"  API URL: {model['api_url']}")
            print(f"  Model Name: {model['model_name']}")

            # Retry logic: attempt initialization up to 3 times
            max_init_retries = 3
            init_success = False

            for attempt in range(1, max_init_retries + 1):
                try:
                    if attempt > 1:
                        print(f"  [RETRY] Attempt {attempt}/{max_init_retries}...")
                        time.sleep(2)  # Wait 2 seconds before retry

                    trading_engines[model_id] = TradingEngine(
                        model_id=model_id,
                        db=db,
                        market_fetcher=market_fetcher,
                        ai_trader=AITrader(
                            api_key=model['api_key'],
                            api_url=model['api_url'],
                            model_name=model['model_name']
                        )
                    )
                    print(f"  ✅ [OK] Model {model_id} ({model_name}) initialized successfully")
                    init_success = True
                    break  # Success, exit retry loop

                except Exception as e:
                    print(f"  ❌ [ERROR] Attempt {attempt}/{max_init_retries} failed!")
                    print(f"  Error type: {type(e).__name__}")
                    print(f"  Error message: {str(e)}")

                    if attempt == max_init_retries:
                        # Final attempt failed, show full traceback
                        print(f"  Detailed traceback:")
                        import traceback
                        traceback.print_exc()
                        print(f"  ⚠️  All {max_init_retries} initialization attempts failed!")
                        print(f"  ⚠️  This model will be SKIPPED in trading loop")
                    else:
                        print(f"  Will retry in 2 seconds...")

            if not init_success:
                continue  # Skip to next model

        print(f"\n[INIT] ✅ Successfully initialized {len(trading_engines)} engine(s)")
        print(f"[INIT] Active models: {list(trading_engines.keys())}\n")

        if len(trading_engines) < len(models):
            failed_count = len(models) - len(trading_engines)
            print(f"[WARN] ⚠️  {failed_count} model(s) failed to initialize!")
            print(f"[WARN] Check the error messages above for details\n")

    except Exception as e:
        print(f"[ERROR] ❌ Init engines failed with critical error: {e}")
        import traceback
        traceback.print_exc()
        print()

if __name__ == '__main__':
    db.init_db()
    
    print("\n" + "=" * 60)
    print("AI Trading Platform")
    print("=" * 60)
    
    init_trading_engines()
    
    if auto_trading:
        trading_thread = threading.Thread(target=trading_loop, daemon=True)
        trading_thread.start()
        print("[INFO] Auto-trading enabled")
    
    print("\n" + "=" * 60)
    print("Server: http://localhost:5000")
    print("Press Ctrl+C to stop")
    print("=" * 60 + "\n")
    
    app.run(debug=False, host='0.0.0.0', port=5000, use_reloader=False)
