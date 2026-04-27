"""
AI交易日志格式化工具
解析并美化显示AI交易决策日志
"""
import json
from datetime import datetime
from typing import Dict, List

# 示例日志数据（从截图中提取）
SAMPLE_LOGS = [
    {
        "timestamp": "2025/10/21 19:31:54",
        "decisions": {
            "BTC": {
                "signal": "hold",
                "quantity": 0,
                "leverage": 0,
                "profit_target": 0,
                "stop_loss": 0,
                "confidence": 0.5,
                "justification": "RSI is very low (29.2) indicating oversold, but price below SMA14 suggests bearish pressure. No clear entry signal yet."
            },
            "ETH": {
                "signal": "hold",
                "quantity": 0,
                "leverage": 0,
                "profit_target": 0,
                "stop_loss": 0,
                "confidence": 0.5,
                "justification": "RSI near oversold but price just below SMA14. Current long facing 0.5 = $863.65, should be held for now."
            },
            "SOL": {
                "signal": "hold",
                "quantity": 0,
                "leverage": 0,
                "profit_target": 0,
                "stop_loss": 0,
                "confidence": 0.5,
                "justification": "RSI at 33.0 close to oversold, price at SMA7 and below SMA14. Current long facing, close to limit further losses."
            },
            "DOGE": {
                "signal": "close_position",
                "quantity": 5000,
                "leverage": 10,
                "profit_target": 0,
                "stop_loss": 0,
                "confidence": 0.8,
                "justification": "RSI very low (29.1) indicating oversold at SMA7 but below SMA14. Current short facing close to prevent further downside."
            }
        }
    },
    {
        "timestamp": "2025/10/21 19:31:15",
        "decisions": {
            "BTC": {
                "signal": "hold",
                "quantity": 0,
                "leverage": 0,
                "profit_target": 0,
                "stop_loss": 0,
                "confidence": 0.6,
                "justification": "Price down 0.2% no strong reversal signal yet wait for clearer signal."
            },
            "ETH": {
                "signal": "buy_to_enter",
                "quantity": 0.5,
                "leverage": 5,
                "profit_target": 4100,
                "stop_loss": 3700,
                "confidence": 0.7,
                "justification": "Price down nearly 2%, no strong reversal signal yet. Wait for clearer entry."
            },
            "SOL": {
                "signal": "hold",
                "quantity": 0,
                "leverage": 0,
                "profit_target": 0,
                "stop_loss": 0,
                "confidence": 0.6,
                "justification": "Currently holding long 0.5 at $186.63 with 2x leverage. Price down 2.63% no strong reversal signal. Hold and monitor."
            },
            "XRP": {
                "signal": "sell_to_enter",
                "quantity": 300,
                "leverage": 10,
                "profit_target": 2.0,
                "stop_loss": 2.6,
                "confidence": 0.65,
                "justification": "Strong bearish momentum, shorting XRP with high stop loss to manage risk."
            },
            "DOGE": {
                "signal": "hold",
                "quantity": 0,
                "leverage": 0,
                "profit_target": 0,
                "stop_loss": 0,
                "confidence": 0.4,
                "justification": "Downtrend continues, lack of strong buy signals, better to wait."
            }
        }
    },
    {
        "timestamp": "2025/10/21 19:31:15",
        "decisions": {
            "BTC": {
                "signal": "hold",
                "quantity": 0,
                "leverage": 0,
                "profit_target": 0,
                "stop_loss": 0,
                "confidence": 0.5,
                "justification": "Price down 0.2%, no current position, no strong technical signals to enter."
            },
            "ETH": {
                "signal": "hold",
                "quantity": 0,
                "leverage": 0,
                "profit_target": 0,
                "stop_loss": 0,
                "confidence": 0.6,
                "justification": "Currently holding long 0.5 at $3986.63 with 2x leverage. Price down 2.63%, no strong reversal signal. Hold and monitor."
            },
            "SOL": {
                "signal": "hold",
                "quantity": 0,
                "leverage": 0,
                "profit_target": 0,
                "stop_loss": 0,
                "confidence": 0.8,
                "justification": "RSI at 33.0 close to oversold, price at SMA7 and below SMA14. Current long facing, close to limit further losses."
            },
            "XRP": {
                "signal": "sell_to_enter",
                "quantity": 300,
                "leverage": 10,
                "profit_target": 2.0,
                "stop_loss": 2.6,
                "confidence": 0.65,
                "justification": "Strong bearish momentum, shorting XRP with high stop loss to manage risk."
            },
            "DOGE": {
                "signal": "hold",
                "quantity": 0,
                "leverage": 0,
                "profit_target": 0,
                "stop_loss": 0,
                "confidence": 0.4,
                "justification": "Weak bearish momentum but no clear entry better to stay out."
            }
        }
    }
]

# 信号映射
SIGNAL_MAP = {
    "buy_to_enter": {"emoji": "🟢", "text": "买入开多", "color": "\033[92m"},
    "sell_to_enter": {"emoji": "🔴", "text": "卖出开空", "color": "\033[91m"},
    "close_position": {"emoji": "🟡", "text": "平仓", "color": "\033[93m"},
    "hold": {"emoji": "⚪", "text": "持有", "color": "\033[90m"}
}

# 币种信息
COIN_INFO = {
    "BTC": "比特币",
    "ETH": "以太坊",
    "SOL": "Solana",
    "XRP": "瑞波币",
    "DOGE": "狗狗币",
    "BNB": "币安币"
}

# 颜色代码
RESET = "\033[0m"
BOLD = "\033[1m"
CYAN = "\033[96m"
YELLOW = "\033[93m"
MAGENTA = "\033[95m"


def format_confidence(confidence: float) -> str:
    """格式化信心度"""
    percentage = int(confidence * 100)
    if percentage >= 80:
        return f"🔥 {percentage}% (高)"
    elif percentage >= 60:
        return f"✅ {percentage}% (中)"
    else:
        return f"⚠️ {percentage}% (低)"


def format_price(price: float) -> str:
    """格式化价格"""
    if price == 0:
        return "未设置"
    return f"${price:,.2f}"


def format_decision(coin: str, decision: Dict) -> str:
    """格式化单个币种的决策"""
    signal = decision.get("signal", "unknown")
    signal_info = SIGNAL_MAP.get(signal, {"emoji": "❓", "text": signal, "color": RESET})
    
    coin_name = COIN_INFO.get(coin, coin)
    
    output = f"\n{BOLD}{CYAN}🪙 {coin} ({coin_name}){RESET}\n"
    output += f"{'─' * 60}\n"
    
    # 交易信号
    output += f"{signal_info['color']}{signal_info['emoji']} 交易信号: {signal_info['text']}{RESET}\n"
    
    # 如果不是持有，显示详细信息
    if signal != "hold":
        quantity = decision.get("quantity", 0)
        leverage = decision.get("leverage", 0)
        profit_target = decision.get("profit_target", 0)
        stop_loss = decision.get("stop_loss", 0)
        
        if quantity > 0:
            output += f"   📊 数量: {quantity:,.4f}\n"
        if leverage > 0:
            output += f"   ⚡ 杠杆: {leverage}x\n"
        if profit_target > 0:
            output += f"   🎯 目标价: {format_price(profit_target)}\n"
        if stop_loss > 0:
            output += f"   🛑 止损价: {format_price(stop_loss)}\n"
    
    # 信心度
    confidence = decision.get("confidence", 0)
    output += f"   💪 信心度: {format_confidence(confidence)}\n"
    
    # 决策理由
    justification = decision.get("justification", "无")
    output += f"   📝 决策理由: {justification}\n"
    
    return output


def format_log_entry(log_entry: Dict) -> str:
    """格式化单条日志"""
    timestamp = log_entry.get("timestamp", "未知时间")
    decisions = log_entry.get("decisions", {})
    
    output = f"\n{BOLD}{YELLOW}{'═' * 70}{RESET}\n"
    output += f"{BOLD}{MAGENTA}📅 时间: {timestamp}{RESET}\n"
    output += f"{BOLD}{YELLOW}{'═' * 70}{RESET}\n"
    
    # 统计信息
    total_coins = len(decisions)
    action_count = sum(1 for d in decisions.values() if d.get("signal") != "hold")
    
    output += f"\n{BOLD}📊 决策概览:{RESET}\n"
    output += f"   • 分析币种: {total_coins} 个\n"
    output += f"   • 执行操作: {action_count} 个\n"
    output += f"   • 持有观望: {total_coins - action_count} 个\n"
    
    # 显示每个币种的决策
    for coin, decision in decisions.items():
        output += format_decision(coin, decision)
    
    return output


def format_all_logs(logs: List[Dict]) -> str:
    """格式化所有日志"""
    output = f"\n{BOLD}{CYAN}{'*' * 70}{RESET}\n"
    output += f"{BOLD}{CYAN}{'*' * 20} AI交易决策日志报告 {'*' * 20}{RESET}\n"
    output += f"{BOLD}{CYAN}{'*' * 70}{RESET}\n"
    
    output += f"\n{BOLD}📈 报告信息:{RESET}\n"
    output += f"   • 日志条数: {len(logs)}\n"
    output += f"   • 时间范围: {logs[-1]['timestamp']} ~ {logs[0]['timestamp']}\n"
    
    # 按时间倒序显示（最新的在前）
    for log_entry in logs:
        output += format_log_entry(log_entry)
    
    output += f"\n{BOLD}{CYAN}{'*' * 70}{RESET}\n"
    output += f"{BOLD}{CYAN}{'*' * 25} 报告结束 {'*' * 26}{RESET}\n"
    output += f"{BOLD}{CYAN}{'*' * 70}{RESET}\n\n"
    
    return output


def save_to_file(content: str, filename: str = "trading_log_report.txt"):
    """保存到文件（去除颜色代码）"""
    # 移除ANSI颜色代码
    import re
    clean_content = re.sub(r'\033\[[0-9;]+m', '', content)
    
    with open(filename, 'w', encoding='utf-8') as f:
        f.write(clean_content)
    
    print(f"\n✅ 报告已保存到: {filename}")


if __name__ == "__main__":
    print("\n🚀 开始格式化AI交易日志...\n")
    
    # 格式化日志
    formatted_output = format_all_logs(SAMPLE_LOGS)
    
    # 打印到控制台
    print(formatted_output)
    
    # 保存到文件
    save_to_file(formatted_output)
    
    print("✅ 格式化完成！")

