from database import Database

db = Database('trading_bot.db')
models = db.get_all_models()

print(f"数据库中的模型数量: {len(models)}")

if models:
    for model in models:
        print(f"\n模型 ID: {model['id']}")
        print(f"  名称: {model['name']}")
        print(f"  初始资金: ${model['initial_capital']:.2f}")
        print(f"  API URL: {model['api_url']}")
        print(f"  模型名: {model['model_name']}")
else:
    print("\n❌ 数据库中没有模型！")
    print("请先通过Web界面 (http://localhost:5000) 添加AI交易模型。")

