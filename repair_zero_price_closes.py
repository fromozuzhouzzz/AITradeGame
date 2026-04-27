import os
from typing import Dict, List, Tuple

from database import Database
from market_data import MarketDataFetcher

# 需要修复的模型 ID
TARGET_MODELS = [45, 55, 56, 57]


def get_db() -> Database:
    # 与 app.py 中保持一致
    return Database('trading_bot.db')


def fetch_bad_close_trades(db: Database) -> List[Dict]:
    """找到所有需要修复的平仓记录：close_position 且 price=0"""
    with db.get_connection_context() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT id, model_id, coin, signal, quantity, price, leverage, side, pnl, timestamp
            FROM trades
            WHERE model_id IN ({ids})
              AND signal = 'close_position'
              AND price = 0
            ORDER BY model_id, id ASC
            """.format(ids=','.join('?' * len(TARGET_MODELS))),
            TARGET_MODELS,
        )
        rows = cursor.fetchall()
        return [dict(row) for row in rows]


def get_current_prices_for_coins(coins: List[str]) -> Dict[str, float]:
    """使用现有的 MarketDataFetcher 获取当前价格"""
    if not coins:
        return {}

    proxy = os.environ.get('CRYPTO_PROXY')
    fetcher = MarketDataFetcher(proxy=proxy)

    prices_data = fetcher.get_current_prices(coins)
    prices: Dict[str, float] = {}
    for coin in coins:
        data = prices_data.get(coin)
        if not data:
            continue
        price = data.get('price')
        if price is None or price <= 0:
            print(f"[WARN] Current market price for {coin} is invalid: {price}, skip this coin")
            continue
        prices[coin] = float(price)

    return prices


def compute_entry_price_before_close(
    db: Database, model_id: int, coin: str, side: str, close_trade_id: int
) -> Tuple[float, float]:
    """基于 trades 表重放该币种持仓，得到平仓前的均价和数量

    返回 (entry_price, quantity_before_close)
    如果无法计算，返回 (None, 0)
    """
    with db.get_connection_context() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT id, signal, quantity, price
            FROM trades
            WHERE model_id = ? AND coin = ? AND side = ?
              AND id <= ?
            ORDER BY id ASC
            """,
            (model_id, coin, side, close_trade_id),
        )
        rows = cursor.fetchall()

    qty = 0.0
    avg_price = 0.0

    for row in rows:
        trade_id = row['id']
        signal = row['signal']
        q = float(row['quantity'])
        price = float(row['price'])

        if signal in ('buy_to_enter', 'sell_to_enter', 'add_position'):
            # 开仓或加仓：更新均价
            if qty <= 0:
                qty = q
                avg_price = price
            else:
                new_qty = qty + q
                if new_qty <= 0:
                    # 理论上不会出现，但防御性处理
                    qty = 0.0
                    avg_price = 0.0
                else:
                    avg_price = (qty * avg_price + q * price) / new_qty
                    qty = new_qty

        elif signal == 'reduce_position':
            # 减仓：数量减少，均价保持不变
            qty -= q
            if qty < 1e-8:
                qty = 0.0

        elif signal == 'close_position':
            # 遇到目标平仓记录：当前 avg_price 就是平仓前的建仓均价
            if trade_id == close_trade_id:
                return (avg_price if qty > 0 else None, qty)
            # 早先的平仓：该方向持仓归零
            qty = 0.0
            avg_price = 0.0

    return (None, 0.0)


def repair_zero_price_closes():
    db = get_db()

    print("[STEP 1] 查找需要修复的平仓记录...")
    bad_trades = fetch_bad_close_trades(db)

    if not bad_trades:
        print("[INFO] 未找到任何 price=0 的 close_position 记录，无需修复。")
        return

    print(f"[INFO] 发现 {len(bad_trades)} 条需要修复的记录：")
    for t in bad_trades:
        print(
            f"  - id={t['id']}, model={t['model_id']}, coin={t['coin']}, side={t['side']}, "
            f"qty={t['quantity']}, price={t['price']}, pnl={t['pnl']}, ts={t['timestamp']}"
        )

    # 收集所有涉及到的币种，获取当前价格
    coins = sorted({t['coin'] for t in bad_trades})
    print(f"\n[STEP 2] 获取当前市场价格, 涉及币种: {coins}")
    current_prices = get_current_prices_for_coins(coins)

    if not current_prices:
        print("[ERROR] 无法获取任何币种的当前价格，终止修复。")
        return

    print("[INFO] 当前价格:")
    for c, p in current_prices.items():
        print(f"  - {c}: {p}")

    updates: List[Tuple[float, float, int]] = []  # (new_price, new_pnl, trade_id)

    print("\n[STEP 3] 为每条记录计算修复后的 price 和 pnl...")
    for t in bad_trades:
        trade_id = t['id']
        model_id = t['model_id']
        coin = t['coin']
        side = t['side']
        qty = float(t['quantity'])

        curr_price = current_prices.get(coin)
        if curr_price is None:
            print(f"  [SKIP] trade id={trade_id}: 当前价格缺失，跳过 {coin}")
            continue

        entry_price, qty_before_close = compute_entry_price_before_close(
            db, model_id, coin, side, trade_id
        )

        if entry_price is None or qty_before_close <= 0:
            print(
                f"  [SKIP] trade id={trade_id}: 无法可靠计算平仓前建仓均价，"
                f"entry_price={entry_price}, qty_before_close={qty_before_close}"
            )
            continue

        if abs(qty_before_close - qty) > 1e-6:
            print(
                f"  [WARN] trade id={trade_id}: 计算得到的持仓数量({qty_before_close}) "
                f"与平仓记录数量({qty}) 不一致，将仍使用记录中的数量计算 PnL。"
            )

        if side == 'long':
            new_pnl = (curr_price - entry_price) * qty
        else:
            new_pnl = (entry_price - curr_price) * qty

        print(
            f"  [PLAN] trade id={trade_id}: coin={coin}, side={side}, "
            f"qty={qty}, entry={entry_price:.6f}, new_price={curr_price:.6f}, new_pnl={new_pnl:.6f}"
        )

        updates.append((curr_price, new_pnl, trade_id))

    if not updates:
        print("\n[INFO] 没有任何记录可以安全修复（可能缺少当前价格或历史不完整），数据库未做修改。")
        return

    # 真正写入数据库
    print("\n[STEP 4] 写入数据库，仅更新 price=0 的 close_position 记录的 price 和 pnl...")
    with db.get_connection_context() as conn:
        cursor = conn.cursor()
        for new_price, new_pnl, trade_id in updates:
            cursor.execute(
                "UPDATE trades SET price = ?, pnl = ? WHERE id = ?",
                (new_price, new_pnl, trade_id),
            )
        conn.commit()

    print(f"[DONE] 已成功更新 {len(updates)} 条记录。其他记录保持不变。")


if __name__ == '__main__':
    repair_zero_price_closes()
