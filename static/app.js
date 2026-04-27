class TradingApp {
    constructor() {
        this.currentModelId = null;
        this.editingModelId = null;
        this.chart = null;
        this.currentTimeframe = '1m'; // 默认时间周期
        this.refreshIntervals = {
            market: null,
            portfolio: null,
            trades: null
        };
        this.init();
    }

    init() {
        this.initEventListeners();
        this.loadModels();
        this.loadMarketPrices();
        this.startRefreshCycles();
    }

    initEventListeners() {
        document.getElementById('addModelBtn').addEventListener('click', () => this.showModal());
        document.getElementById('closeModalBtn').addEventListener('click', () => this.hideModal());
        document.getElementById('cancelBtn').addEventListener('click', () => this.hideModal());
        document.getElementById('submitBtn').addEventListener('click', () => this.submitModel());
        document.getElementById('refreshBtn').addEventListener('click', () => this.refresh());
        document.getElementById('expandConversationBtn').addEventListener('click', () => this.openFullConversation());

        document.querySelectorAll('.tab-btn').forEach(btn => {
            btn.addEventListener('click', (e) => this.switchTab(e.target.dataset.tab));
        });

        // 时间周期切换按钮事件监听
        document.querySelectorAll('.timeframe-btn').forEach(btn => {
            btn.addEventListener('click', (e) => this.switchTimeframe(e.target.dataset.timeframe));
        });
    }

    async switchTimeframe(timeframe) {
        if (!this.currentModelId || timeframe === this.currentTimeframe) return;

        this.currentTimeframe = timeframe;

        // 更新按钮状态
        document.querySelectorAll('.timeframe-btn').forEach(btn => {
            btn.classList.toggle('active', btn.dataset.timeframe === timeframe);
        });

        // 加载新时间周期的数据
        await this.loadChartData(timeframe);
    }

    async loadChartData(timeframe) {
        if (!this.currentModelId) return;

        try {
            const response = await fetch(`/api/models/${this.currentModelId}/account_history?timeframe=${timeframe}&limit=100`);
            const result = await response.json();

            if (result.error) {
                console.error('Failed to load chart data:', result.error);
                return;
            }

            // 获取当前账户总值（用于添加最新数据点）
            const portfolioResponse = await fetch(`/api/models/${this.currentModelId}/portfolio`);
            const portfolioData = await portfolioResponse.json();
            const currentValue = portfolioData.portfolio.total_value;

            this.updateChart(result.data, currentValue, timeframe);
        } catch (error) {
            console.error('Failed to load chart data:', error);
        }
    }

    async loadModels() {
        try {
            const response = await fetch('/api/models');
            const models = await response.json();
            this.renderModels(models);

            if (models.length > 0 && !this.currentModelId) {
                this.selectModel(models[0].id);
            }
        } catch (error) {
            console.error('Failed to load models:', error);
        }
    }

    renderModels(models) {
        const container = document.getElementById('modelList');

        if (models.length === 0) {
            container.innerHTML = '<div class="empty-state">暂无模型</div>';
            return;
        }

        container.innerHTML = models.map(model => `
            <div class="model-item ${model.id === this.currentModelId ? 'active' : ''}"
                 onclick="app.selectModel(${model.id})">
                <div class="model-name">${model.name}</div>
                <div class="model-info">
                    <span>${model.model_name}</span>
                    <div class="model-actions">
                        <span class="model-edit" onclick="event.stopPropagation(); app.editModel(${model.id})" title="编辑模型">
                            <i class="bi bi-pencil"></i>
                        </span>
                        <span class="model-delete" onclick="event.stopPropagation(); app.deleteModel(${model.id})" title="删除模型">
                            <i class="bi bi-trash"></i>
                        </span>
                    </div>
                </div>
            </div>
        `).join('');
    }

    async selectModel(modelId) {
        this.currentModelId = modelId;
        this.loadModels();
        await this.loadModelData();
    }

    async loadModelData() {
        if (!this.currentModelId) return;

        try {
            const [portfolio, trades, conversations] = await Promise.all([
                fetch(`/api/models/${this.currentModelId}/portfolio`).then(r => r.json()),
                fetch(`/api/models/${this.currentModelId}/trades?limit=50`).then(r => r.json()),
                fetch(`/api/models/${this.currentModelId}/conversations?limit=20`).then(r => r.json())
            ]);

            this.updateStats(portfolio.portfolio);
            // 使用当前选择的时间周期加载图表数据
            await this.loadChartData(this.currentTimeframe);
            this.updatePositions(portfolio.portfolio.positions);
            this.updateTrades(trades);
            this.updateConversations(conversations);
        } catch (error) {
            console.error('Failed to load model data:', error);
        }
    }

    updateStats(portfolio) {
        // 计算收益率
        const initialCapital = portfolio.initial_capital || 100000;
        const totalValue = portfolio.total_value || 0;
        const returnRate = ((totalValue - initialCapital) / initialCapital) * 100;

        const stats = [
            { value: totalValue, class: totalValue > initialCapital ? 'positive' : totalValue < initialCapital ? 'negative' : '', format: 'currency' },
            { value: portfolio.cash || 0, class: '', format: 'currency' },
            { value: returnRate, class: returnRate > 0 ? 'positive' : returnRate < 0 ? 'negative' : '', format: 'percent' },
            { value: portfolio.realized_pnl || 0, class: portfolio.realized_pnl > 0 ? 'positive' : portfolio.realized_pnl < 0 ? 'negative' : '', format: 'currency' },
            { value: portfolio.unrealized_pnl || 0, class: portfolio.unrealized_pnl > 0 ? 'positive' : portfolio.unrealized_pnl < 0 ? 'negative' : '', format: 'currency' }
        ];

        document.querySelectorAll('.stat-value').forEach((el, index) => {
            if (stats[index]) {
                if (stats[index].format === 'percent') {
                    // 收益率显示为百分比，带正负号
                    const sign = stats[index].value > 0 ? '+' : '';
                    el.textContent = `${sign}${stats[index].value.toFixed(2)}%`;
                } else {
                    // 货币显示为美元
                    el.textContent = `$${Math.abs(stats[index].value).toFixed(2)}`;
                }
                el.className = `stat-value ${stats[index].class}`;
            }
        });
    }

    updateChart(history, currentValue, timeframe = '1m') {
        const chartDom = document.getElementById('accountChart');

        if (!this.chart) {
            this.chart = echarts.init(chartDom);
            window.addEventListener('resize', () => {
                if (this.chart) {
                    this.chart.resize();
                }
            });
        }

        // 根据时间周期选择合适的时间格式
        const getTimeFormat = (timestamp, tf) => {
            const date = new Date(timestamp.replace(' ', 'T') + 'Z');
            const options = { timeZone: 'Asia/Shanghai' };

            if (tf.endsWith('m') || tf === '1h') {
                // 分钟级和1小时：显示 HH:MM
                return date.toLocaleTimeString('zh-CN', {
                    ...options,
                    hour: '2-digit',
                    minute: '2-digit'
                });
            } else if (tf === '4h') {
                // 4小时：显示 MM-DD HH:MM
                return date.toLocaleString('zh-CN', {
                    ...options,
                    month: '2-digit',
                    day: '2-digit',
                    hour: '2-digit',
                    minute: '2-digit'
                });
            } else if (tf === '1d') {
                // 日级：显示 MM-DD
                return date.toLocaleDateString('zh-CN', {
                    ...options,
                    month: '2-digit',
                    day: '2-digit'
                });
            } else if (tf === '1w') {
                // 周级：显示 YYYY-MM-DD
                return date.toLocaleDateString('zh-CN', {
                    ...options,
                    year: 'numeric',
                    month: '2-digit',
                    day: '2-digit'
                });
            } else if (tf === '1M') {
                // 月级：显示 YYYY-MM
                return date.toLocaleDateString('zh-CN', {
                    ...options,
                    year: 'numeric',
                    month: '2-digit'
                });
            }
            return date.toLocaleTimeString('zh-CN', {
                ...options,
                hour: '2-digit',
                minute: '2-digit'
            });
        };

        const data = history.reverse().map(h => ({
            time: getTimeFormat(h.timestamp, timeframe),
            value: h.total_value
        }));

        if (currentValue !== undefined && currentValue !== null && timeframe.endsWith('m')) {
            // 只在分钟级时间周期添加当前值
            const now = new Date();
            const currentTime = getTimeFormat(now.toISOString().replace('T', ' ').substring(0, 19), timeframe);
            data.push({
                time: currentTime,
                value: currentValue
            });
        }

        const option = {
            grid: {
                left: '60',
                right: '20',
                bottom: '30',
                top: '20',
                containLabel: false
            },
            xAxis: {
                type: 'category',
                boundaryGap: false,
                data: data.map(d => d.time),
                axisLine: { lineStyle: { color: '#e5e6eb' } },
                axisLabel: { color: '#86909c', fontSize: 11 }
            },
            yAxis: {
                type: 'value',
                scale: true,
                axisLine: { lineStyle: { color: '#e5e6eb' } },
                axisLabel: { 
                    color: '#86909c', 
                    fontSize: 11,
                    formatter: (value) => `$${value.toLocaleString()}`
                },
                splitLine: { lineStyle: { color: '#f2f3f5' } }
            },
            series: [{
                type: 'line',
                data: data.map(d => d.value),
                smooth: true,
                symbol: 'none',
                lineStyle: { color: '#3370ff', width: 2 },
                areaStyle: {
                    color: {
                        type: 'linear',
                        x: 0, y: 0, x2: 0, y2: 1,
                        colorStops: [
                            { offset: 0, color: 'rgba(51, 112, 255, 0.2)' },
                            { offset: 1, color: 'rgba(51, 112, 255, 0)' }
                        ]
                    }
                }
            }],
            tooltip: {
                trigger: 'axis',
                backgroundColor: 'rgba(255, 255, 255, 0.95)',
                borderColor: '#e5e6eb',
                borderWidth: 1,
                textStyle: { color: '#1d2129' },
                formatter: (params) => {
                    const value = params[0].value;
                    return `${params[0].axisValue}<br/>$${value.toFixed(2)}`;
                }
            }
        };

        this.chart.setOption(option);
        
        setTimeout(() => {
            if (this.chart) {
                this.chart.resize();
            }
        }, 100);
    }

    updatePositions(positions) {
        const tbody = document.getElementById('positionsBody');
        
        if (positions.length === 0) {
            tbody.innerHTML = '<tr><td colspan="7" class="empty-state">暂无持仓</td></tr>';
            return;
        }

        tbody.innerHTML = positions.map(pos => {
            const sideClass = pos.side === 'long' ? 'badge-long' : 'badge-short';
            const sideText = pos.side === 'long' ? '做多' : '做空';
            
            const currentPrice = pos.current_price !== null && pos.current_price !== undefined 
                ? `$${pos.current_price.toFixed(2)}` 
                : '-';
            
            let pnlDisplay = '-';
            let pnlClass = '';
            if (pos.pnl !== undefined && pos.pnl !== 0) {
                // 中国股市习惯：盈利红色，亏损绿色
                pnlClass = pos.pnl > 0 ? 'text-profit' : 'text-loss';
                pnlDisplay = `${pos.pnl > 0 ? '+' : ''}$${pos.pnl.toFixed(2)}`;
            }
            
            return `
                <tr>
                    <td><strong>${pos.coin}</strong></td>
                    <td><span class="badge ${sideClass}">${sideText}</span></td>
                    <td>${pos.quantity.toFixed(4)}</td>
                    <td>$${pos.avg_price.toFixed(2)}</td>
                    <td>${currentPrice}</td>
                    <td>${pos.leverage}x</td>
                    <td class="${pnlClass}"><strong>${pnlDisplay}</strong></td>
                </tr>
            `;
        }).join('');
    }

    updateTrades(trades) {
        const tbody = document.getElementById('tradesBody');
        
        if (trades.length === 0) {
            tbody.innerHTML = '<tr><td colspan="6" class="empty-state">暂无交易记录</td></tr>';
            return;
        }

        tbody.innerHTML = trades.map(trade => {
            const signalMap = {
                'buy_to_enter': { badge: 'badge-buy', text: '开多' },
                'sell_to_enter': { badge: 'badge-sell', text: '开空' },
                'add_position': { badge: 'badge-add', text: '加仓' },
                'reduce_position': { badge: 'badge-reduce', text: '减仓' },
                'close_position': { badge: 'badge-close', text: '平仓' }
            };
            const signal = signalMap[trade.signal] || { badge: '', text: trade.signal };
            // 中国股市习惯：盈利红色，亏损绿色
            const pnlClass = trade.pnl > 0 ? 'text-profit' : trade.pnl < 0 ? 'text-loss' : '';

            return `
                <tr>
                    <td>${new Date(trade.timestamp.replace(' ', 'T') + 'Z').toLocaleString('zh-CN', { timeZone: 'Asia/Shanghai' })}</td>
                    <td><strong>${trade.coin}</strong></td>
                    <td><span class="badge ${signal.badge}">${signal.text}</span></td>
                    <td>${trade.quantity.toFixed(4)}</td>
                    <td>$${trade.price.toFixed(2)}</td>
                    <td class="${pnlClass}">$${trade.pnl.toFixed(2)}</td>
                </tr>
            `;
        }).join('');
    }

    updateConversations(conversations) {
        const container = document.getElementById('conversationsBody');

        if (conversations.length === 0) {
            container.innerHTML = '<div class="empty-state">暂无对话记录</div>';
            return;
        }

        // 检查最新记录的时间，如果超过10分钟则显示警告
        if (conversations.length > 0) {
            const latestConv = conversations[0];
            const latestTime = new Date(latestConv.timestamp.replace(' ', 'T') + 'Z');
            const now = new Date();
            const minutesAgo = Math.floor((now - latestTime) / 1000 / 60);

            if (minutesAgo > 10) {
                const warningHtml = `
                    <div class="data-warning">
                        <div class="warning-icon">⚠️</div>
                        <div class="warning-content">
                            <div class="warning-title">数据未更新</div>
                            <div class="warning-message">
                                最新记录来自 <strong>${minutesAgo}</strong> 分钟前。
                                AI交易循环可能已停止，请检查后端服务器状态。
                            </div>
                        </div>
                    </div>
                `;
                container.innerHTML = warningHtml + conversations.map(conv => this.renderConversation(conv)).join('');
                return;
            }
        }

        container.innerHTML = conversations.map(conv => this.renderConversation(conv)).join('');
    }

    renderConversation(conv) {
        const timestamp = new Date(conv.timestamp.replace(' ', 'T') + 'Z').toLocaleString('zh-CN', { timeZone: 'Asia/Shanghai' });

        // 尝试解析AI响应为JSON
        let decisions = null;
        try {
            // 清理响应文本：移除markdown代码块标记
            let cleanedResponse = conv.ai_response.trim();

            // 移除 ```json 和 ``` 标记
            if (cleanedResponse.startsWith('```json')) {
                cleanedResponse = cleanedResponse.replace(/^```json\s*/, '').replace(/```\s*$/, '');
            } else if (cleanedResponse.startsWith('```')) {
                cleanedResponse = cleanedResponse.replace(/^```\s*/, '').replace(/```\s*$/, '');
            }

            decisions = JSON.parse(cleanedResponse);
            // 验证是否为交易决策格式
            if (typeof decisions === 'object' && decisions !== null) {
                return this.renderTradingDecision(timestamp, decisions);
            }
        } catch (e) {
            // 不是JSON或解析失败，使用原始格式
            console.warn('Failed to parse conversation as JSON:', e);
        }

        // 降级到原始文本显示
        return `
            <div class="conversation-item">
                <div class="conversation-time">${timestamp}</div>
                <div class="conversation-content">${this.escapeHtml(conv.ai_response)}</div>
            </div>
        `;
    }

    renderTradingDecision(timestamp, decisions) {
        // 统计信息
        const coins = Object.keys(decisions);
        const totalCoins = coins.length;
        const actionCount = coins.filter(coin => {
            const signal = decisions[coin]?.signal;
            return signal && signal !== 'hold';
        }).length;
        const holdCount = totalCoins - actionCount;

        // 生成币种列表行
        const coinRows = coins.map(coin => {
            const decision = decisions[coin];
            return this.renderCoinRow(coin, decision);
        }).join('');

        return `
            <div class="trading-decision-entry">
                <div class="decision-timestamp">
                    <span class="timestamp-icon">📅</span>
                    <span class="timestamp-text">${timestamp}</span>
                </div>

                <div class="decision-overview">
                    <h3 class="overview-title">📊 决策概览</h3>
                    <div class="overview-stats">
                        <span class="overview-stat">• 分析币种: <strong>${totalCoins} 个</strong></span>
                        <span class="overview-stat">• 执行操作: <strong>${actionCount} 个</strong></span>
                        <span class="overview-stat">• 持有观望: <strong>${holdCount} 个</strong></span>
                    </div>
                </div>

                <div class="coin-list">
                    ${coinRows}
                </div>
            </div>
        `;
    }

    renderCoinRow(coin, decision) {
        const signal = decision?.signal || 'unknown';
        const quantity = decision?.quantity || 0;
        const leverage = decision?.leverage || 0;
        const profitTarget = decision?.profit_target || 0;
        const stopLoss = decision?.stop_loss || 0;
        const confidence = decision?.confidence || 0;
        const justification = decision?.justification || 'N/A';

        // 信号映射（中国股市习惯：红涨绿跌）
        const signalMap = {
            'buy_to_enter': { emoji: '🔴', text: '买入开多', class: 'buy' },
            'sell_to_enter': { emoji: '🟢', text: '卖出开空', class: 'sell' },
            'add_position': { emoji: '🟠', text: '加仓', class: 'add' },
            'reduce_position': { emoji: '🟣', text: '减仓', class: 'reduce' },
            'close_position': { emoji: '🟡', text: '平仓', class: 'close' },
            'hold': { emoji: '⚪', text: '持有', class: 'hold' }
        };

        const signalInfo = signalMap[signal] || { emoji: '❓', text: signal, class: 'unknown' };

        // 币种名称映射
        const coinNames = {
            'BTC': '比特币', 'ETH': '以太坊', 'SOL': 'Solana',
            'XRP': '瑞波币', 'DOGE': '狗狗币', 'BNB': '币安币'
        };
        const coinName = coinNames[coin] || coin;

        // 币种图标
        const coinIcons = {
            'BTC': '₿', 'ETH': 'Ξ', 'SOL': '◎',
            'XRP': '✕', 'DOGE': 'Ð', 'BNB': '🔶'
        };
        const coinIcon = coinIcons[coin] || '🪙';

        // 信心度格式化
        const confidencePercent = Math.round(confidence * 100);
        let confidenceClass = 'low';
        let confidenceIcon = '⚠️';
        let confidenceLevel = '低';

        if (confidencePercent >= 80) {
            confidenceClass = 'high';
            confidenceIcon = '🔥';
            confidenceLevel = '高';
        } else if (confidencePercent >= 60) {
            confidenceClass = 'medium';
            confidenceIcon = '✅';
            confidenceLevel = '中';
        }

        // 是否为执行操作
        const isAction = signal !== 'hold';
        const rowClass = isAction ? 'coin-row action-row' : 'coin-row';

        // 构建交易参数（仅在有操作时显示）
        let paramsHtml = '';
        if (isAction) {
            paramsHtml = `
                <span class="row-param">📊 ${quantity.toFixed(4)}</span>
                <span class="row-param">⚡ ${leverage}x</span>
                ${profitTarget > 0 ? `<span class="row-param">🎯 $${profitTarget.toFixed(2)}</span>` : '<span class="row-param">-</span>'}
                ${stopLoss > 0 ? `<span class="row-param">🛑 $${stopLoss.toFixed(2)}</span>` : '<span class="row-param">-</span>'}
            `;
        } else {
            paramsHtml = `
                <span class="row-param">-</span>
                <span class="row-param">-</span>
                <span class="row-param">-</span>
                <span class="row-param">-</span>
            `;
        }

        return `
            <div class="${rowClass}">
                <div class="row-main">
                    <div class="row-coin">
                        <span class="row-coin-icon">${coinIcon}</span>
                        <span class="row-coin-name">${coin}</span>
                        <span class="row-coin-fullname">${coinName}</span>
                    </div>
                    <div class="row-signal">
                        <span class="signal-badge signal-${signalInfo.class}">
                            ${signalInfo.emoji} ${signalInfo.text}
                        </span>
                    </div>
                    <div class="row-params">
                        ${paramsHtml}
                    </div>
                    <div class="row-confidence">
                        <span class="confidence-${confidenceClass}">
                            ${confidenceIcon} ${confidencePercent}%
                        </span>
                    </div>
                </div>
                <div class="row-justification">
                    📝 ${this.escapeHtml(justification)}
                </div>
            </div>
        `;
    }

    escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }

    async loadMarketPrices() {
        try {
            const response = await fetch('/api/market/prices');
            const prices = await response.json();
            this.renderMarketPrices(prices);
        } catch (error) {
            console.error('Failed to load market prices:', error);
        }
    }

    renderMarketPrices(prices) {
        const container = document.getElementById('marketPrices');

        container.innerHTML = Object.entries(prices).map(([coin, data]) => {
            // 中国股市习惯：上涨红色，下跌绿色
            const changeClass = data.change_24h >= 0 ? 'positive' : 'negative';
            const changeIcon = data.change_24h >= 0 ? '▲' : '▼';

            return `
                <div class="price-item">
                    <div>
                        <div class="price-symbol">${coin}</div>
                        <div class="price-change ${changeClass}">${changeIcon} ${Math.abs(data.change_24h).toFixed(2)}%</div>
                    </div>
                    <div class="price-value">$${data.price.toFixed(2)}</div>
                </div>
            `;
        }).join('');
    }

    switchTab(tabName) {
        document.querySelectorAll('.tab-btn').forEach(btn => btn.classList.remove('active'));
        document.querySelectorAll('.tab-content').forEach(content => content.classList.remove('active'));
        
        document.querySelector(`[data-tab="${tabName}"]`).classList.add('active');
        document.getElementById(`${tabName}Tab`).classList.add('active');
    }

    showModal() {
        // 如果不是编辑模式，重置为添加模式
        if (!this.editingModelId) {
            document.getElementById('modalTitle').textContent = '添加交易模型';
            document.getElementById('submitBtn').textContent = '确认添加';
            document.getElementById('initialCapitalGroup').style.display = 'block';
        }
        document.getElementById('addModelModal').classList.add('show');
    }

    hideModal() {
        document.getElementById('addModelModal').classList.remove('show');
    }

    async editModel(modelId) {
        try {
            const response = await fetch(`/api/models/${modelId}`);
            if (!response.ok) {
                alert('无法加载模型信息');
                return;
            }

            // 获取模型数据 - 需要从模型列表中获取
            const modelsResponse = await fetch('/api/models');
            const models = await modelsResponse.json();
            const model = models.find(m => m.id === modelId);

            if (!model) {
                alert('模型不存在');
                return;
            }

            // 设置编辑模式
            this.editingModelId = modelId;
            document.getElementById('modalTitle').textContent = '编辑交易模型';
            document.getElementById('submitBtn').textContent = '确认修改';
            document.getElementById('initialCapitalGroup').style.display = 'none';

            // 填充表单
            document.getElementById('modelName').value = model.name;
            document.getElementById('apiKey').value = model.api_key;
            document.getElementById('apiUrl').value = model.api_url;
            document.getElementById('modelIdentifier').value = model.model_name;

            this.showModal();
        } catch (error) {
            console.error('Failed to load model for editing:', error);
            alert('加载模型失败');
        }
    }

    async submitModel() {
        const data = {
            name: document.getElementById('modelName').value,
            api_key: document.getElementById('apiKey').value,
            api_url: document.getElementById('apiUrl').value,
            model_name: document.getElementById('modelIdentifier').value
        };

        if (!data.name || !data.api_key || !data.api_url || !data.model_name) {
            alert('请填写所有必填字段');
            return;
        }

        try {
            let response;

            if (this.editingModelId) {
                // 编辑模式 - 使用 PUT 请求
                response = await fetch(`/api/models/${this.editingModelId}`, {
                    method: 'PUT',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(data)
                });
            } else {
                // 添加模式 - 使用 POST 请求
                data.initial_capital = parseFloat(document.getElementById('initialCapital').value);
                response = await fetch('/api/models', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(data)
                });
            }

            if (response.ok) {
                this.hideModal();
                this.loadModels();
                this.clearForm();
                this.editingModelId = null;
            } else {
                alert('操作失败，请重试');
            }
        } catch (error) {
            console.error('Failed to submit model:', error);
            alert('操作失败');
        }
    }

    async deleteModel(modelId) {
        if (!confirm('确定要删除这个模型吗？')) return;

        try {
            const response = await fetch(`/api/models/${modelId}`, {
                method: 'DELETE'
            });

            if (response.ok) {
                if (this.currentModelId === modelId) {
                    this.currentModelId = null;
                }
                this.loadModels();
            }
        } catch (error) {
            console.error('Failed to delete model:', error);
        }
    }

    clearForm() {
        document.getElementById('modelName').value = '';
        document.getElementById('apiKey').value = '';
        document.getElementById('apiUrl').value = '';
        document.getElementById('modelIdentifier').value = '';
        document.getElementById('initialCapital').value = '100000';
        this.editingModelId = null;
    }

    async refresh() {
        await Promise.all([
            this.loadModels(),
            this.loadMarketPrices(),
            this.loadModelData()
        ]);
    }

    startRefreshCycles() {
        // 优化：将市场价格刷新间隔从5秒延长到30秒
        // 原因：避免在模型决策期间频繁触发API调用，减少与后端session机制的冲突
        // 30秒的间隔足够显示实时价格，同时不会干扰交易周期（通常60-120秒）
        this.refreshIntervals.market = setInterval(() => {
            this.loadMarketPrices();
        }, 30000);  // 从5000ms改为30000ms

        this.refreshIntervals.portfolio = setInterval(() => {
            if (this.currentModelId) {
                this.loadModelData();
            }
        }, 10000);
    }

    stopRefreshCycles() {
        Object.values(this.refreshIntervals).forEach(interval => {
            if (interval) clearInterval(interval);
        });
    }

    openFullConversation() {
        if (!this.currentModelId) {
            alert('请先选择一个交易模型');
            return;
        }

        // 在新窗口中打开完整对话页面
        const url = `/conversations/${this.currentModelId}`;
        window.open(url, '_blank', 'width=1200,height=800,scrollbars=yes,resizable=yes');
    }
}

const app = new TradingApp();
