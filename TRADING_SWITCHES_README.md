# 交易开关使用说明 (Trading Switches Guide)

## 简介

现在你可以通过简单的开关来控制做多和做空功能。这些开关位于 `trading_engine.py` 文件的顶部。

## 开关位置

打开 `trading_engine.py` 文件，在文件开头你会看到：

```python
# ============================================================
# 交易开关配置 - 在这里设置做多/做空功能
# ============================================================
# 1 = 启用该功能, 0 = 禁用该功能
ENABLE_LONG_TRADING = 1   # 做多开关 (buy_to_enter)
ENABLE_SHORT_TRADING = 1  # 做空开关 (sell_to_enter)
# ============================================================
```

## 使用方法

### 1. 只做空交易（你之前的设置）
```python
ENABLE_LONG_TRADING = 0   # 禁用做多
ENABLE_SHORT_TRADING = 1  # 启用做空
```

### 2. 只做多交易
```python
ENABLE_LONG_TRADING = 1   # 启用做多
ENABLE_SHORT_TRADING = 0  # 禁用做空
```

### 3. 同时做多和做空（默认设置）
```python
ENABLE_LONG_TRADING = 1   # 启用做多
ENABLE_SHORT_TRADING = 1  # 启用做空
```

### 4. 暂停所有交易
```python
ENABLE_LONG_TRADING = 0   # 禁用做多
ENABLE_SHORT_TRADING = 0  # 禁用做空
```

## 功能说明

- **ENABLE_LONG_TRADING**: 控制 `buy_to_enter` 信号（开多单）
- **ENABLE_SHORT_TRADING**: 控制 `sell_to_enter` 信号（开空单）

当某个功能被禁用时：
- AI 的交易信号会被自动转换为 `hold`（持有/观望）
- 系统会显示相应的提示信息，例如："Long trading disabled (ENABLE_LONG_TRADING=0)"
- 已有的持仓不受影响，可以正常平仓或减仓

## 注意事项

1. **修改后需要重启程序**：修改开关后，需要重新启动 Flask 应用才能生效
2. **不影响已有持仓**：开关只影响新开仓，不影响已有持仓的管理（减仓、平仓等）
3. **加仓功能**：如果禁用了某个方向的交易，也无法对该方向的持仓进行加仓

## 快速修改步骤

1. 打开 `trading_engine.py`
2. 找到文件顶部的开关配置（第 5-11 行）
3. 修改数值：`1` 表示启用，`0` 表示禁用
4. 保存文件
5. 重启程序（重新运行 `python app.py` 或 `run.bat`）

---

## English Version

### Quick Guide

Edit the switches at the top of `trading_engine.py`:

- `ENABLE_LONG_TRADING = 1` → Enable long positions (buy)
- `ENABLE_LONG_TRADING = 0` → Disable long positions

- `ENABLE_SHORT_TRADING = 1` → Enable short positions (sell)
- `ENABLE_SHORT_TRADING = 0` → Disable short positions

**Remember to restart the application after making changes!**
