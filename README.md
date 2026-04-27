# AITradeGame 大模型的交易能力测试项目

[![Python 3.9+](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/downloads/)
[![Flask](https://img.shields.io/badge/flask-3.0+-green.svg)](https://flask.palletsprojects.com/)

基于 Web 的加密货币交易模拟平台，采用 AI 驱动的决策系统。

在线版（加了排行榜功能）：https://aitradegame.com/ 

## 功能特性

- 🌐 **多API轮询机制** - 支持Binance、CoinGecko、Kraken、Coinbase等多个数据源
- 🔄 **智能失败转移** - 自动切换到可用的API，确保数据获取稳定性
- 🚀 **实时加密货币市场数据** - 支持BTC、ETH、SOL、BNB、XRP、DOGE
- 🤖 **基于大语言模型的 AI 交易策略** - 支持OpenAI、DeepSeek、Claude等
- 📊 **支持杠杆的投资组合管理** - 灵活的仓位管理
- 📈 **实时图表的交互式仪表板** - 使用ECharts可视化
- 📜 **交易历史与性能跟踪** - 完整的交易记录
- 🔧 **代理支持** - 可配置HTTP/SOCKS5代理绕过地区限制

## 技术栈

- 后端：Python/Flask
- 前端：原生 JavaScript、ECharts
- 数据库：SQLite
- AI 接口：OpenAI 兼容格式（支持 OpenAI、DeepSeek、Claude 等）

## 快速开始

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

### 2. 测试API连接（推荐）

```bash
python test_api_connection.py
```

这将测试所有加密货币API的连接状态。

### 3. 启动应用

```bash
python app.py
```

访问地址：`http://localhost:5000`

### 4. 配置代理（可选）

如果你所在地区无法访问某些API，可以配置代理：

**Windows (PowerShell):**
```powershell
$env:CRYPTO_PROXY="http://your-proxy.com:8080"
python app.py
```

**Linux/Mac:**
```bash
export CRYPTO_PROXY="http://your-proxy.com:8080"
python app.py
```

详细配置请参考 [API_CONFIGURATION.md](API_CONFIGURATION.md)

## 配置

通过 Web 界面添加交易模型：
- 模型名称
- API 密钥
- API 地址
- 模型标识符
- 初始资金

## 项目结构

```
AITradeGame/
├── app.py                      # Flask 应用主程序
├── trading_engine.py           # 交易逻辑引擎
├── ai_trader.py                # AI 集成模块
├── database.py                 # 数据层
├── market_data.py              # 市场数据接口（多API支持）
├── test_api_connection.py      # API连接测试工具
├── API_CONFIGURATION.md        # API配置详细文档
├── static/                     # CSS/JS 资源
├── templates/                  # HTML 模板
└── requirements.txt            # Python 依赖
```

## 支持的 AI 模型

兼容 OpenAI 格式的 API：
- OpenAI (gpt-4, gpt-3.5-turbo)
- DeepSeek (deepseek-chat)
- Claude (通过 OpenRouter)

## 使用方法

1. 启动服务器
2. 添加 AI 模型配置
3. 系统自动开始交易
4. 实时监控投资组合

## API数据源

本项目支持多个加密货币数据API，按优先级自动轮询：

1. **Binance** - 主要数据源（4个备用端点）
2. **CoinGecko** - 免费API，无需密钥
3. **Kraken** - 公共API
4. **Coinbase** - 公共API

当一个API失败时，系统会自动切换到下一个可用的API。详细配置请参考 [API_CONFIGURATION.md](API_CONFIGURATION.md)

### 监控API健康状态

访问 `http://localhost:5000/api/market/health` 查看API健康状态。

## 故障排除

### Binance 451错误（地区限制）
✅ **已解决** - 系统会自动尝试多个Binance端点，或切换到其他API

### CoinGecko SSL错误
✅ **已解决** - 已实现SSL错误处理和重试机制

### 所有API都失败
- 检查网络连接
- 配置代理（参考 [API_CONFIGURATION.md](API_CONFIGURATION.md)）
- 运行 `python test_api_connection.py` 诊断问题

## 注意事项

- 这是一个模拟交易平台（仅限纸面交易）
- 需要有效的 AI 模型 API 密钥
- 需要互联网连接以获取市场数据
- 开发环境已禁用SSL验证，生产环境请启用

## 贡献

欢迎贡献代码！

**免责声明**：本平台仅用于教育和模拟目的，不构成任何投资建议。
