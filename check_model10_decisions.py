"""检查Model 10的最新交易决策"""
from database import Database
import json

db = Database('trading_bot.db')

print("="*80)
print("Model 10 最新交易决策分析")
print("="*80)

# 获取最新对话
convs = db.get_conversations(10, limit=1)
if not convs:
    print("\n❌ 没有找到Model 10的对话记录")
    exit(1)

conv = convs[0]
print(f"\n📅 时间: {conv['timestamp']}")
print(f"📝 COT标记: {conv.get('cot_trace', 'N/A')}")

# 解析AI响应
try:
    ai_response = conv['ai_response']
    decisions = json.loads(ai_response)
    
    print(f"\n✅ 成功解析AI响应")
    print(f"📊 决策数量: {len(decisions)}")
    
    # 统计信号类型
    signal_counts = {}
    for coin, decision in decisions.items():
        signal = decision.get('signal', 'unknown')
        signal_counts[signal] = signal_counts.get(signal, 0) + 1
    
    print(f"\n📈 信号统计:")
    for signal, count in signal_counts.items():
        print(f"   {signal}: {count} 个")
    
    # 显示每个币种的决策
    print(f"\n💡 详细决策:")
    for coin, decision in decisions.items():
        signal = decision.get('signal', 'unknown')
        quantity = decision.get('quantity', 0)
        confidence = decision.get('confidence', 0)
        justification = decision.get('justification', 'N/A')[:80]
        
        print(f"\n   🪙 {coin}:")
        print(f"      信号: {signal}")
        print(f"      数量: {quantity}")
        print(f"      信心度: {confidence}")
        print(f"      理由: {justification}...")
        
except json.JSONDecodeError as e:
    print(f"\n❌ JSON解析失败: {e}")
    print(f"\nAI响应内容（前500字符）:")
    print(ai_response[:500])
except Exception as e:
    print(f"\n❌ 处理失败: {e}")
    print(f"\nAI响应内容（前500字符）:")
    print(conv['ai_response'][:500])

print("\n" + "="*80)

