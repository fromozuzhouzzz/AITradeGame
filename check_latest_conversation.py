#!/usr/bin/env python3
"""检查最新的AI对话记录"""

from database import Database

db = Database()

# 检查所有模型的最新对话
models = db.get_all_models()

print("=" * 80)
print("最新AI对话记录检查")
print("=" * 80)

for model in models:
    model_id = model['id']
    model_name = model['name']
    
    print(f"\n模型 {model_id}: {model_name}")
    print("-" * 80)
    
    convs = db.get_conversations(model_id, limit=1)
    
    if not convs:
        print("  ❌ 没有对话记录")
        continue
    
    latest = convs[0]
    timestamp = latest['timestamp']
    ai_response = latest['ai_response']
    cot_trace = latest.get('cot_trace', '')
    
    print(f"  ⏰ 时间: {timestamp}")
    print(f"  📝 AI响应长度: {len(ai_response)} 字符")
    print(f"  🏷️  COT标记: {cot_trace if cot_trace else '(无)'}")
    print(f"\n  📄 AI响应内容（前800字符）:")
    print("  " + "-" * 76)
    
    # 显示前800字符，每行缩进
    response_preview = ai_response[:800]
    for line in response_preview.split('\n'):
        print(f"  {line}")
    
    if len(ai_response) > 800:
        print(f"  ... (还有 {len(ai_response) - 800} 字符)")

print("\n" + "=" * 80)

