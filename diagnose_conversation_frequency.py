#!/usr/bin/env python3
"""诊断AI对话记录的更新频率问题"""

from database import Database
from datetime import datetime, timedelta
import json

db = Database()

print("=" * 80)
print("AI对话记录更新频率诊断")
print("=" * 80)

# 获取所有模型
models = db.get_all_models()
current_time = datetime.now()

print(f"\n当前时间: {current_time.strftime('%Y-%m-%d %H:%M:%S')}")
print("\n" + "=" * 80)

for model in models:
    model_id = model['id']
    model_name = model['name']
    
    print(f"\n模型 {model_id}: {model_name}")
    print("-" * 80)
    
    # 获取最近10条记录
    convs = db.get_conversations(model_id, limit=10)
    
    if not convs:
        print("  ❌ 没有任何对话记录")
        continue
    
    print(f"  📊 总共找到 {len(convs)} 条最近记录\n")
    
    # 分析时间间隔
    for i, conv in enumerate(convs):
        timestamp_str = conv['timestamp']
        timestamp = datetime.strptime(timestamp_str, '%Y-%m-%d %H:%M:%S')
        time_diff = current_time - timestamp
        
        minutes_ago = int(time_diff.total_seconds() / 60)
        
        # 检查是否是降级决策
        cot_trace = conv.get('cot_trace', '')
        is_fallback = '[FALLBACK]' in cot_trace
        
        # 检查响应内容
        ai_response = conv['ai_response']
        response_preview = ai_response[:100] if len(ai_response) > 100 else ai_response
        
        status_icon = "🔴" if minutes_ago > 5 else "🟢"
        fallback_icon = " [降级]" if is_fallback else ""
        
        print(f"  {status_icon} 记录 #{i+1}: {timestamp_str} ({minutes_ago}分钟前){fallback_icon}")
        print(f"     响应长度: {len(ai_response)} 字符")
        print(f"     响应预览: {response_preview}...")
        
        # 计算与上一条记录的时间间隔
        if i < len(convs) - 1:
            prev_timestamp = datetime.strptime(convs[i+1]['timestamp'], '%Y-%m-%d %H:%M:%S')
            interval = timestamp - prev_timestamp
            interval_minutes = int(interval.total_seconds() / 60)
            
            interval_icon = "✅" if 2 <= interval_minutes <= 4 else "⚠️"
            print(f"     {interval_icon} 与上一条间隔: {interval_minutes} 分钟")
        
        print()

print("=" * 80)
print("\n诊断建议:")
print("-" * 80)

# 检查是否有模型长时间未更新
for model in models:
    model_id = model['id']
    model_name = model['name']
    convs = db.get_conversations(model_id, limit=1)
    
    if not convs:
        print(f"⚠️  模型 {model_id} ({model_name}): 没有任何记录")
        continue
    
    latest = convs[0]
    timestamp = datetime.strptime(latest['timestamp'], '%Y-%m-%d %H:%M:%S')
    time_diff = current_time - timestamp
    minutes_ago = int(time_diff.total_seconds() / 60)
    
    if minutes_ago > 5:
        print(f"🔴 模型 {model_id} ({model_name}): 最后更新于 {minutes_ago} 分钟前 - 异常！")
        print(f"   建议检查该模型的AI决策是否正常执行，以及add_conversation()是否被调用")
    else:
        print(f"✅ 模型 {model_id} ({model_name}): 最后更新于 {minutes_ago} 分钟前 - 正常")

print("\n" + "=" * 80)

