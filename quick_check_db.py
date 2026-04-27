import sqlite3
from datetime import datetime

conn = sqlite3.connect('trading.db')
cursor = conn.cursor()

print("=" * 80)
print("最近15条AI对话记录")
print("=" * 80)

cursor.execute("""
    SELECT model_id, timestamp, LENGTH(ai_response) as len, 
           SUBSTR(ai_response, 1, 80) as preview
    FROM conversations 
    ORDER BY timestamp DESC 
    LIMIT 15
""")

rows = cursor.fetchall()

current_time = datetime.now()

for row in rows:
    model_id, timestamp_str, length, preview = row
    timestamp = datetime.strptime(timestamp_str, '%Y-%m-%d %H:%M:%S')
    time_diff = current_time - timestamp
    minutes_ago = int(time_diff.total_seconds() / 60)
    
    status = "🟢" if minutes_ago <= 5 else "🔴"
    
    print(f"\n{status} 模型{model_id} | {timestamp_str} ({minutes_ago}分钟前)")
    print(f"   长度: {length} 字符")
    print(f"   预览: {preview}...")

print("\n" + "=" * 80)

# 统计每个模型的最新记录
print("\n每个模型的最新记录时间:")
print("-" * 80)

cursor.execute("""
    SELECT model_id, MAX(timestamp) as latest
    FROM conversations
    GROUP BY model_id
    ORDER BY model_id
""")

for row in cursor.fetchall():
    model_id, latest_str = row
    latest = datetime.strptime(latest_str, '%Y-%m-%d %H:%M:%S')
    time_diff = current_time - latest
    minutes_ago = int(time_diff.total_seconds() / 60)
    
    status = "✅" if minutes_ago <= 5 else "❌"
    print(f"{status} 模型 {model_id}: {latest_str} ({minutes_ago}分钟前)")

conn.close()

