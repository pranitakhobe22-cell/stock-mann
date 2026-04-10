/* ═══════════════════════════════════════════════════════════
   StockMann — Professional Terminal Frontend
   Features: Charts, Heat Map, Scanner, Backtest, Portfolio,
             Compare, Export CSV, Keyboard Shortcuts,
             Fear & Greed Gauge, Price Alerts, Ticker Bar
   ═══════════════════════════════════════════════════════════ */

// ── State ──
let currentSymbol = 'RELIANCE.NS';
let currentTimeframe = '1d';
let currentView = 'chart';
let scannerCache = null;
let priceAlerts = [];
let tradeModalType = 'BUY';
let autoRefreshTimer = null;
let compareMode = false;
let currentChartData = null;

// ── Chart Theme ──
const BG = '#0B0E11';
const GRID = '#1C2030';
const TXT = '#6B7280';
const GRN = '#22C55E';
const RED = '#EF4444';
const BLU = '#3B82F6';
const AMB = '#F59E0B';
const PUR = '#8B5CF6';
const CFG = { responsive: true, displayModeBar: false, scrollZoom: false };

// ═══ INIT ═══
document.addEventListener('DOMContentLoaded', () => {
    initEvents();
    initClock();
    loadWatchlistPrices();
    loadStock(currentSymbol, currentTimeframe);
    startAutoRefresh();
});

function initEvents() {
    // Search
    const searchEl = document.getElementById('symbol-search');
    const searchWrapper = searchEl.closest('.search-wrapper');
    const dropdown = document.createElement('div');
    dropdown.className = 'search-dropdown';
    searchWrapper.appendChild(dropdown);

    let searchTimeout = null;
    searchEl.addEventListener('input', e => {
        clearTimeout(searchTimeout);
        const query = e.target.value.trim();
        if (!query) { dropdown.style.display = 'none'; return; }
        
        searchTimeout = setTimeout(async () => {
            const data = await api(`/api/search?q=${encodeURIComponent(query)}`);
            if (data && data.results && data.results.length > 0) {
                dropdown.innerHTML = data.results.map(r => `
                    <div class="search-item">
                        <span class="si-main" onclick="selectSearchSymbol('${r.symbol}')">
                            <span class="si-sym">${r.symbol}</span>
                            <span class="si-name">${r.name || ''} &bull; ${r.exchange || ''}</span>
                        </span>
                        <span class="si-add" onclick="event.stopPropagation();addSymbolToWatchlist('${r.symbol}')" title="Add to watchlist">+</span>
                    </div>
                `).join('');
                dropdown.style.display = 'block';
            } else {
                dropdown.style.display = 'none';
            }
        }, 300);
    });

    searchEl.addEventListener('keydown', e => {
        if (e.key === 'Enter') {
            let sym = searchEl.value.trim().toUpperCase();
            if (sym && !sym.includes('.')) sym += '.NS';
            if (sym) { currentSymbol = sym; loadStock(sym, currentTimeframe); searchEl.blur(); dropdown.style.display = 'none'; }
        }
    });

    document.addEventListener('click', e => {
        if (!searchWrapper.contains(e.target)) dropdown.style.display = 'none';
    });

    window.selectSearchSymbol = function(sym) {
        currentSymbol = sym;
        loadStock(sym, currentTimeframe);
        dropdown.style.display = 'none';
        searchEl.value = sym;
        searchEl.blur();
    };

    // Timeframes
    document.querySelectorAll('.tf-btn').forEach(btn => {
        btn.addEventListener('click', () => {
            document.querySelectorAll('.tf-btn').forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
            currentTimeframe = btn.dataset.tf;
            loadStock(currentSymbol, currentTimeframe);
        });
    });

    // Keyboard shortcuts
    document.addEventListener('keydown', e => {
        if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA') return;
        if (e.ctrlKey && e.key === 'k') { e.preventDefault(); searchEl.focus(); return; }
        if (e.key === 'Escape') { closeAllModals(); return; }
        if (e.key === '?') { document.getElementById('kb-modal').style.display = 'flex'; return; }
        if (e.key === 'f' || e.key === 'F') { toggleFullscreen(); return; }
        if (e.key === 's') { switchView('screener'); return; }
        if (e.key === 'b') { switchView('backtest'); return; }
        if (e.key === 'p') { switchView('portfolio'); return; }
        if (e.key === 'h') { switchView('heatmap'); return; }
        const tfMap = { '1': '1m', '2': '5m', '3': '15m', '4': '1h', '5': '1d' };
        if (tfMap[e.key]) {
            document.querySelectorAll('.tf-btn').forEach(b => b.classList.toggle('active', b.dataset.tf === tfMap[e.key]));
            currentTimeframe = tfMap[e.key];
            loadStock(currentSymbol, currentTimeframe);
        }
    });
}

// ── Clock ──
function initClock() {
    const update = () => {
        const now = new Date().toLocaleTimeString('en-IN', { timeZone: 'Asia/Kolkata', hour12: false });
        document.getElementById('clock-time').textContent = now;
    };
    update();
    setInterval(update, 1000);
}

// ── Helpers ──
async function api(url) {
    try { const r = await fetch(url); if (!r.ok) return null; return await r.json(); }
    catch (e) { console.error('API:', url, e); return null; }
}
function fmt(n, d = 2) {
    if (n === null || n === undefined || n === 'null' || isNaN(n)) return '--';
    return Number(n).toLocaleString('en-IN', { minimumFractionDigits: d, maximumFractionDigits: d });
}
function fmtC(n) {
    if (n == null) return '--';
    const v = Number(n);
    if (Math.abs(v) >= 1e7) return '\u20B9' + (v / 1e7).toFixed(2) + ' Cr';
    if (Math.abs(v) >= 1e5) return '\u20B9' + (v / 1e5).toFixed(2) + ' L';
    return '\u20B9' + fmt(n);
}
function toast(msg, type = 'info') {
    const c = document.getElementById('toast-container');
    const el = document.createElement('div');
    el.className = `toast toast-${type}`;
    el.textContent = msg;
    c.appendChild(el);
    setTimeout(() => el.remove(), 4000);
}
function showLoading(id) {
    const el = document.getElementById(id);
    if (el) el.innerHTML = '<div class="loading-state"><div class="loader"></div>Loading...</div>';
}
function closeAllModals() {
    document.getElementById('trade-modal').style.display = 'none';
    document.getElementById('kb-modal').style.display = 'none';
}
function toggleFullscreen() {
    if (!document.fullscreenElement) document.documentElement.requestFullscreen();
    else document.exitFullscreen();
}

// ── View Switch ──
function switchView(view) {
    currentView = view;
    document.querySelectorAll('.nav-btn').forEach(b => b.classList.remove('active'));
    const btn = document.querySelector(`.nav-btn[data-view="${view}"]`);
    if (btn) btn.classList.add('active');
    document.querySelectorAll('.view-panel').forEach(p => p.classList.remove('active'));
    document.getElementById(`view-${view}`).classList.add('active');
    if (view === 'screener' && !scannerCache) runScanner();
    if (view === 'portfolio') loadPortfolio();
    if (view === 'heatmap' && scannerCache) renderHeatMap();
    if (view === 'chart') setTimeout(() => resizeCharts(), 50);
    if (view === 'profile') { loadProfile(); loadProfileStats(); }
}

function resizeCharts() {
    ['main-chart', 'volume-chart', 'rsi-chart', 'macd-chart'].forEach(id => {
        const el = document.getElementById(id);
        if (el && el.data) Plotly.Plots.resize(el);
    });
}

// ═══ TICKER BAR ═══
function buildTicker(results) {
    const track = document.getElementById('ticker-track');
    if (!results || results.length === 0) return;
    let html = '';
    // Duplicate for seamless scroll
    for (let i = 0; i < 2; i++) {
        results.forEach(r => {
            const chg = r.indicators?.momentum ? (r.indicators.momentum * 100) : 0;
            const color = chg >= 0 ? GRN : RED;
            const sign = chg >= 0 ? '+' : '';
            html += `<span class="ticker-item">
                <span class="ticker-sym">${r.symbol.replace('.NS','')}</span>
                <span class="ticker-price">\u20B9${fmt(r.price)}</span>
                <span class="ticker-chg" style="color:${color}">${sign}${fmt(chg)}%</span>
            </span>`;
        });
    }
    track.innerHTML = html;
}

// ═══ WATCHLIST ═══
let watchlistCustom = [];

async function loadWatchlistPrices() {
    const data = await api('/api/watchlist');
    if (!data) return;
    watchlistCustom = data.custom || [];
    const countEl = document.getElementById('wl-count');
    if (countEl) countEl.textContent = `(${data.total || data.symbols.length})`;

    const container = document.getElementById('watchlist-items');
    container.innerHTML = '';
    for (const sym of data.symbols) {
        const short = sym.replace('.NS', '').replace('.BO', '');
        const isCustom = watchlistCustom.includes(sym);
        const item = document.createElement('div');
        item.className = `wl-item${sym === currentSymbol ? ' active' : ''}`;
        item.dataset.symbol = sym;
        item.onclick = () => {
            currentSymbol = sym;
            loadStock(sym, currentTimeframe);
            document.querySelectorAll('.wl-item').forEach(w => w.classList.remove('active'));
            item.classList.add('active');
            if (currentView !== 'chart') switchView('chart');
        };
        // Right-click to remove custom stocks
        if (isCustom) {
            item.oncontextmenu = (e) => {
                e.preventDefault();
                removeFromWatchlist(sym);
            };
        }
        const badge = isCustom ? '<span style="color:#8B5CF6;font-size:7px;margin-left:3px">★</span>' : '';
        item.innerHTML = `<div><div class="wl-symbol">${short}${badge}</div><div class="wl-name">NSE</div></div>
            <div><div class="wl-price" id="wl-p-${short}">--</div><div class="wl-change" id="wl-c-${short}">--</div></div>`;
        container.appendChild(item);
    }
    // Background price fetch (batch, 8 at a time to avoid rate limiting)
    const symbols = data.symbols;
    for (let i = 0; i < symbols.length; i += 8) {
        const batch = symbols.slice(i, i + 8);
        batch.forEach(sym => {
            api(`/api/stock/${sym}/price`).then(d => {
                const s = sym.replace('.NS', '').replace('.BO', '');
                const p = document.getElementById(`wl-p-${s}`);
                const c = document.getElementById(`wl-c-${s}`);
                if (d && p) {
                    p.textContent = '\u20B9' + fmt(d.price);
                    const ch = d.change_pct || 0;
                    c.textContent = `${ch >= 0 ? '+' : ''}${fmt(ch)}%`;
                    c.style.color = ch >= 0 ? GRN : RED;
                }
            });
        });
    }
}

async function addCurrentToWatchlist() {
    const sym = currentSymbol;
    if (!sym) { toast('No stock selected', 'error'); return; }
    const res = await fetch(`/api/watchlist/add?symbol=${encodeURIComponent(sym)}`, { method: 'POST' });
    const data = await res.json();
    if (data.status === 'ok') {
        toast(data.message, 'success');
        loadWatchlistPrices();
    } else {
        toast(data.error || 'Failed', 'error');
    }
}

async function removeFromWatchlist(sym) {
    const res = await fetch(`/api/watchlist/remove?symbol=${encodeURIComponent(sym)}`, { method: 'POST' });
    const data = await res.json();
    if (data.status === 'ok') {
        toast(`${sym.replace('.NS','')} removed from watchlist`, 'info');
        loadWatchlistPrices();
    }
}

async function addSymbolToWatchlist(sym) {
    const res = await fetch(`/api/watchlist/add?symbol=${encodeURIComponent(sym)}`, { method: 'POST' });
    const data = await res.json();
    if (data.status === 'ok') {
        toast(data.message, 'success');
        loadWatchlistPrices();
    } else {
        toast(data.error || 'Failed to add', 'error');
    }
}

// ═══ LOAD STOCK ═══
async function loadStock(symbol, timeframe) {
    currentSymbol = symbol;
    const short = symbol.replace('.NS', '');
    document.getElementById('sym-name').textContent = short;
    document.getElementById('sym-exchange').textContent = symbol.includes('.NS') ? 'NSE' : 'BSE';
    document.getElementById('symbol-search').value = symbol;
    document.getElementById('bt-symbol').value = symbol;
    document.querySelectorAll('.wl-item').forEach(w => w.classList.toggle('active', w.dataset.symbol === symbol));

    const [sig, stock, indicators] = await Promise.all([
        api(`/api/signal/${symbol}?timeframe=${timeframe}`),
        api(`/api/stock/${symbol}?timeframe=${timeframe}&limit=200`),
        api(`/api/stock/${symbol}/indicators?timeframe=${timeframe}`),
    ]);

    if (sig) { updateHeader(sig); updateSignalChip(sig); updateRightPanel(sig); }
    if (stock?.data?.length) {
        currentChartData = stock.data;
        renderCandleChart(stock.data);
        renderVolumeChart(stock.data);
        checkPriceAlerts(symbol, stock.data[stock.data.length - 1].close);
    }
    if (indicators?.data?.length) { renderRSIChart(indicators.data); renderMACDChart(indicators.data); }
}

function updateHeader(sig) {
    const priceEl = document.getElementById('sym-price');
    const changeEl = document.getElementById('sym-change');
    priceEl.textContent = '\u20B9' + fmt(sig.price);
    const mom = sig.indicators?.momentum;
    if (mom != null) {
        const pct = mom * 100;
        changeEl.textContent = `${pct >= 0 ? '+' : ''}${fmt(pct)}%`;
        changeEl.style.color = pct >= 0 ? GRN : RED;
    }
}

function updateSignalChip(sig) {
    const chip = document.getElementById('signal-chip');
    chip.className = 'signal-chip ' + (sig.signal === 'BUY' ? 'buy' : sig.signal === 'SELL' ? 'sell' : 'hold');
    chip.querySelector('.signal-label').textContent = `${sig.signal} ${sig.strength}`;
}

function updateRightPanel(sig) {
    // Signal Hero
    const heroEl = document.getElementById('sh-signal');
    heroEl.textContent = sig.signal;
    heroEl.style.color = sig.signal === 'BUY' ? GRN : sig.signal === 'SELL' ? RED : AMB;
    document.getElementById('sh-strength').textContent = sig.strength + ' Signal';

    // Score Ring
    const score = sig.score || 0;
    const norm = (score + 10) / 20;
    const circ = 213.6;
    const ring = document.getElementById('ring-fill');
    ring.style.strokeDashoffset = circ - (norm * circ);
    ring.style.stroke = score > 0 ? GRN : score < 0 ? RED : AMB;
    document.getElementById('ring-value').textContent = (score > 0 ? '+' : '') + score;

    // Indicators
    const ind = sig.indicators || {};
    const il = document.getElementById('indicator-list');
    il.innerHTML = indRow('RSI (14)', ind.rsi, 0, 100, ind.rsi < 30 ? GRN : ind.rsi > 70 ? RED : '#E8ECF1')
        + indRow('EMA 12', ind.ema_12) + indRow('EMA 26', ind.ema_26)
        + indRow('MACD Hist', ind.macd_histogram, null, null, (ind.macd_histogram || 0) > 0 ? GRN : RED, 4)
        + indRow('BB Upper', ind.bb_upper) + indRow('BB Lower', ind.bb_lower)
        + indRow('Vol Ratio', ind.volume_ratio, 0, 5, (ind.volume_ratio || 0) > 2 ? AMB : '#E8ECF1')
        + indRow('Momentum', ind.momentum, -0.2, 0.2, (ind.momentum || 0) > 0 ? GRN : RED, 4);

    // Breakdown
    const det = sig.details || {};
    const names = { rsi: 'RSI', ema_cross: 'EMA Cross', macd: 'MACD', bollinger: 'Bollinger', volume: 'Volume', momentum: 'Momentum' };
    document.getElementById('signal-breakdown').innerHTML = Object.entries(det).map(([k, v]) => {
        const cls = v > 0 ? 'sb-pos' : v < 0 ? 'sb-neg' : 'sb-neu';
        return `<div class="sb-row"><span class="sb-name">${names[k] || k}</span><span class="sb-val ${cls}">${v > 0 ? '+' : ''}${v}</span></div>`;
    }).join('');

    // Fear & Greed
    updateFearGreed(score);
}

function indRow(label, value, min, max, color, d = 2) {
    const v = (value != null && value !== 'null') ? fmt(value, d) : '--';
    const c = color || '#A0A7B8';
    let bar = '';
    if (min != null && max != null && value != null && value !== 'null') {
        const pct = Math.max(0, Math.min(100, ((value - min) / (max - min)) * 100));
        bar = `<span class="ind-bar"><span class="ind-bar-fill" style="width:${pct}%;background:${c}"></span></span>`;
    }
    return `<div class="ind-row"><span class="ind-label">${label}</span><span class="ind-val" style="color:${c}">${v}${bar}</span></div>`;
}

// ── Fear & Greed ──
function updateFearGreed(score) {
    // score is -10..+10, map to 0..100
    const val = Math.round(((score + 10) / 20) * 100);
    const needle = document.getElementById('fg-needle');
    if (needle) {
        const angle = -90 + (val / 100) * 180;
        needle.setAttribute('transform', `rotate(${angle}, 100, 100)`);
    }
    const fill = document.getElementById('fg-mini-fill');
    const label = document.getElementById('fg-mini-label');
    if (fill) { fill.style.width = val + '%'; fill.style.background = val < 25 ? RED : val < 40 ? AMB : val < 60 ? '#FDD835' : val < 75 ? '#66BB6A' : GRN; }
    if (label) label.textContent = val;
    const vt = document.getElementById('fg-value-text');
    if (vt) {
        const txt = val < 20 ? 'Extreme Fear' : val < 40 ? 'Fear' : val < 60 ? 'Neutral' : val < 80 ? 'Greed' : 'Extreme Greed';
        vt.textContent = `${val} - ${txt}`;
        vt.style.color = val < 25 ? RED : val < 40 ? AMB : val < 60 ? '#FDD835' : val < 75 ? '#66BB6A' : GRN;
    }
}

// ═══ CHARTS ═══
function layout(opts = {}) {
    return {
        paper_bgcolor: BG, plot_bgcolor: BG,
        font: { color: TXT, size: 9, family: 'IBM Plex Sans, sans-serif' },
        margin: { t: opts.mt || 6, b: opts.mb || 24, l: opts.ml || 48, r: opts.mr || 48 },
        xaxis: { gridcolor: GRID, linecolor: GRID, zeroline: false, rangeslider: { visible: false }, showgrid: true, type: 'category', nticks: 8, tickfont: { size: 8, family: 'IBM Plex Mono' }, ...opts.x },
        yaxis: { gridcolor: GRID, linecolor: GRID, zeroline: false, side: 'right', showgrid: true, tickfont: { size: 8, family: 'IBM Plex Mono' }, ...opts.y },
        showlegend: false,
        hovermode: 'x unified',
        hoverlabel: { bgcolor: '#1E2230', bordercolor: '#313747', font: { color: '#E8ECF1', size: 10, family: 'IBM Plex Mono' } },
        ...opts.extra,
    };
}

function renderCandleChart(data) {
    const labels = data.map(d => String(d.timestamp || '').substring(0, 16));
    const candle = {
        x: labels, open: data.map(d => d.open), high: data.map(d => d.high),
        low: data.map(d => d.low), close: data.map(d => d.close),
        type: 'candlestick',
        increasing: { line: { color: GRN, width: 1 }, fillcolor: GRN },
        decreasing: { line: { color: RED, width: 1 }, fillcolor: RED },
        whiskerwidth: 0.4,
        hoverinfo: 'text',
        text: data.map(d => `O:${fmt(d.open)} H:${fmt(d.high)} L:${fmt(d.low)} C:${fmt(d.close)}`),
    };
    Plotly.newPlot('main-chart', [candle], layout(), CFG);
}

function renderVolumeChart(data) {
    const labels = data.map(d => String(d.timestamp || '').substring(0, 16));
    const trace = {
        x: labels, y: data.map(d => d.volume), type: 'bar',
        marker: { color: data.map(d => d.close >= d.open ? 'rgba(34,197,94,0.45)' : 'rgba(239,68,68,0.45)') },
        hoverinfo: 'y',
    };
    Plotly.newPlot('volume-chart', [trace], layout({ mt: 22, mb: 16, y: { showgrid: false, tickformat: '.2s' } }), CFG);
}

function renderRSIChart(data) {
    const labels = data.map(d => String(d.timestamp || '').substring(0, 16));
    const rsi = data.map(d => (d.rsi !== 'null' && d.rsi != null) ? d.rsi : null);
    const traces = [
        { x: labels, y: labels.map(() => 70), type: 'scatter', mode: 'lines', line: { color: RED, width: 0.7, dash: 'dot' }, hoverinfo: 'skip' },
        { x: labels, y: labels.map(() => 30), type: 'scatter', mode: 'lines', line: { color: GRN, width: 0.7, dash: 'dot' }, hoverinfo: 'skip' },
        { x: labels, y: labels.map(() => 50), type: 'scatter', mode: 'lines', line: { color: '#252A38', width: 0.5, dash: 'dot' }, hoverinfo: 'skip' },
        { x: labels, y: rsi, type: 'scatter', mode: 'lines', line: { color: PUR, width: 1.5 }, hoverinfo: 'y' },
    ];
    Plotly.newPlot('rsi-chart', traces, layout({ mt: 22, mb: 16, y: { range: [0, 100], dtick: 25 } }), CFG);
}

function renderMACDChart(data) {
    const labels = data.map(d => String(d.timestamp || '').substring(0, 16));
    const hist = data.map(d => (d.macd_histogram !== 'null' && d.macd_histogram != null) ? d.macd_histogram : null);
    const macd = data.map(d => (d.macd !== 'null' && d.macd != null) ? d.macd : null);
    const sig = data.map(d => (d.macd_signal !== 'null' && d.macd_signal != null) ? d.macd_signal : null);
    const traces = [
        { x: labels, y: hist, type: 'bar', marker: { color: hist.map(v => v != null && v >= 0 ? 'rgba(34,197,94,0.4)' : 'rgba(239,68,68,0.4)') }, hoverinfo: 'y' },
        { x: labels, y: macd, type: 'scatter', mode: 'lines', line: { color: BLU, width: 1.5 }, hoverinfo: 'y' },
        { x: labels, y: sig, type: 'scatter', mode: 'lines', line: { color: AMB, width: 1 }, hoverinfo: 'y' },
    ];
    Plotly.newPlot('macd-chart', traces, layout({ mt: 22, mb: 16, y: { showgrid: false } }), CFG);
}

// ═══ COMPARE ═══
function toggleCompare() {
    compareMode = !compareMode;
    document.getElementById('compare-bar').style.display = compareMode ? 'flex' : 'none';
}

async function runCompare() {
    let sym2 = document.getElementById('compare-input').value.trim().toUpperCase();
    if (!sym2) return;
    if (!sym2.includes('.')) sym2 += '.NS';
    const data2 = await api(`/api/stock/${sym2}?timeframe=${currentTimeframe}&limit=200`);
    if (!data2?.data?.length || !currentChartData) { toast('Could not load comparison data', 'error'); return; }

    // Normalize both datasets to percentage from start
    const base1 = currentChartData[0].close;
    const base2 = data2.data[0].close;
    const labels = currentChartData.map(d => String(d.timestamp || '').substring(0, 16));
    const line1 = {
        x: labels, y: currentChartData.map(d => ((d.close - base1) / base1) * 100),
        type: 'scatter', mode: 'lines', line: { color: BLU, width: 2 },
        name: currentSymbol.replace('.NS', ''),
    };
    const labels2 = data2.data.map(d => String(d.timestamp || '').substring(0, 16));
    const line2 = {
        x: labels2, y: data2.data.map(d => ((d.close - base2) / base2) * 100),
        type: 'scatter', mode: 'lines', line: { color: AMB, width: 2 },
        name: sym2.replace('.NS', ''),
    };
    Plotly.newPlot('main-chart', [line1, line2], {
        ...layout({ y: { title: '% Change' } }),
        showlegend: true,
        legend: { font: { color: '#A0A7B8', size: 11 }, bgcolor: 'transparent', x: 0.02, y: 0.98 },
    }, CFG);
    toast(`Comparing ${currentSymbol.replace('.NS', '')} vs ${sym2.replace('.NS', '')}`, 'info');
}

function clearCompare() {
    if (currentChartData) renderCandleChart(currentChartData);
    document.getElementById('compare-input').value = '';
    toast('Comparison cleared', 'info');
}

// ═══ EXPORT CSV ═══
function exportCSV() {
    if (!currentChartData) { toast('No data to export', 'error'); return; }
    const header = 'Timestamp,Open,High,Low,Close,Volume\n';
    const rows = currentChartData.map(d => `${d.timestamp},${d.open},${d.high},${d.low},${d.close},${d.volume}`).join('\n');
    downloadFile(`${currentSymbol}_${currentTimeframe}.csv`, header + rows);
    toast('CSV exported', 'success');
}

function exportScannerCSV() {
    if (!scannerCache?.results) { toast('Run scanner first', 'error'); return; }
    const header = 'Symbol,Price,Signal,Strength,Score,RSI,MACD,Momentum,VolRatio\n';
    const rows = scannerCache.results.map(r => {
        const i = r.indicators || {};
        return `${r.symbol},${r.price},${r.signal},${r.strength},${r.score},${i.rsi||''},${i.macd_histogram||''},${i.momentum||''},${i.volume_ratio||''}`;
    }).join('\n');
    downloadFile('scanner_results.csv', header + rows);
    toast('Scanner CSV exported', 'success');
}

function downloadFile(name, content) {
    const blob = new Blob([content], { type: 'text/csv' });
    const a = document.createElement('a');
    a.href = URL.createObjectURL(blob);
    a.download = name;
    a.click();
}

// ═══ PRICE ALERTS ═══
function addPriceAlert() {
    const price = parseFloat(document.getElementById('alert-price').value);
    const dir = document.getElementById('alert-dir').value;
    if (!price) { toast('Enter a price', 'error'); return; }
    priceAlerts.push({ symbol: currentSymbol, price, direction: dir });
    renderAlertList();
    document.getElementById('alert-price').value = '';
    toast(`Alert set: ${currentSymbol.replace('.NS','')} ${dir} \u20B9${fmt(price)}`, 'success');
}

function removeAlert(idx) {
    priceAlerts.splice(idx, 1);
    renderAlertList();
}

function renderAlertList() {
    const el = document.getElementById('alert-list');
    el.innerHTML = priceAlerts.filter(a => a.symbol === currentSymbol).map((a, i) => {
        const color = a.direction === 'above' ? GRN : RED;
        const arrow = a.direction === 'above' ? '\u2191' : '\u2193';
        return `<div class="alert-item"><span style="color:${color}">${arrow} \u20B9${fmt(a.price)}</span><button onclick="removeAlert(${i})">&times;</button></div>`;
    }).join('');
}

function checkPriceAlerts(symbol, price) {
    priceAlerts.forEach(a => {
        if (a.symbol !== symbol || a.triggered) return;
        if ((a.direction === 'above' && price >= a.price) || (a.direction === 'below' && price <= a.price)) {
            toast(`ALERT: ${symbol.replace('.NS','')} crossed ${a.direction} \u20B9${fmt(a.price)}! Now \u20B9${fmt(price)}`, 'success');
            a.triggered = true;
        }
    });
}

// ═══ HEAT MAP ═══
function renderHeatMap() {
    if (!scannerCache?.results) { toast('Run screener first', 'info'); switchView('screener'); return; }
    const metric = document.getElementById('heatmap-metric')?.value || 'score';
    const grid = document.getElementById('heatmap-grid');
    grid.innerHTML = scannerCache.results.map(r => {
        let val, display;
        const ind = r.indicators || {};
        if (metric === 'score') { val = r.score; display = r.score; }
        else if (metric === 'momentum') { val = (ind.momentum || 0) * 100; display = fmt(val) + '%'; }
        else { val = (ind.rsi || 50) - 50; display = fmt(ind.rsi); }

        // Color intensity
        const intensity = Math.min(Math.abs(val) / 8, 1);
        let bg;
        if (val > 0) bg = `rgba(34,197,94,${0.15 + intensity * 0.55})`;
        else if (val < 0) bg = `rgba(239,68,68,${0.15 + intensity * 0.55})`;
        else bg = 'rgba(107,114,128,0.2)';

        return `<div class="hm-cell" style="background:${bg}" onclick="selectFromScanner('${r.symbol}')">
            <div class="hm-sym">${r.symbol.replace('.NS','')}</div>
            <div class="hm-val">${display}</div>
            <div class="hm-sub">\u20B9${fmt(r.price)} | ${r.signal}</div>
        </div>`;
    }).join('');

    // Update Fear & Greed based on market average
    const avgScore = scannerCache.results.reduce((s, r) => s + r.score, 0) / scannerCache.results.length;
    updateFearGreed(avgScore);
}

// ═══ SCANNER ═══
async function runScanner() {
    showLoading('scanner-tbody');
    const tf = document.getElementById('scanner-tf')?.value || '1d';
    const data = await api(`/api/scanner?timeframe=${tf}`);
    if (!data) { toast('Scanner failed', 'error'); return; }
    scannerCache = data;

    const buys = data.results.filter(r => r.signal === 'BUY').length;
    const sells = data.results.filter(r => r.signal === 'SELL').length;
    document.getElementById('sc-total').textContent = data.total;
    document.getElementById('sc-buys').textContent = buys;
    document.getElementById('sc-sells').textContent = sells;
    document.getElementById('sc-holds').textContent = data.total - buys - sells;
    document.getElementById('sc-oversold').textContent = (data.oversold || []).length;
    document.getElementById('sc-overbought').textContent = (data.overbought || []).length;

    renderScannerTable(data.results);
    buildTicker(data.results);
    toast(`Scanned ${data.total} stocks`, 'success');
}

function renderScannerTable(results) {
    document.getElementById('scanner-tbody').innerHTML = results.map(r => {
        const i = r.indicators || {};
        const sc = r.signal === 'BUY' ? 'badge-buy' : r.signal === 'SELL' ? 'badge-sell' : 'badge-hold';
        const st = r.strength === 'Strong' ? 'badge-strong' : 'badge-weak';
        return `<tr onclick="selectFromScanner('${r.symbol}')">
            <td class="col-symbol">${r.symbol.replace('.NS','')}</td>
            <td>\u20B9${fmt(r.price)}</td>
            <td><span class="badge ${sc}">${r.signal}</span></td>
            <td><span class="badge ${st}">${r.strength||'--'}</span></td>
            <td style="color:${r.score>0?GRN:r.score<0?RED:'#A0A7B8'}">${r.score}</td>
            <td style="color:${(i.rsi||50)<30?GRN:(i.rsi||50)>70?RED:'#A0A7B8'}">${fmt(i.rsi)}</td>
            <td style="color:${(i.macd_histogram||0)>=0?GRN:RED}">${fmt(i.macd_histogram,4)}</td>
            <td style="color:${(i.momentum||0)>=0?GRN:RED}">${fmt(i.momentum,4)}</td>
            <td style="color:${(i.volume_ratio||0)>2?AMB:'#A0A7B8'}">${fmt(i.volume_ratio)}</td>
        </tr>`;
    }).join('');
}

function selectFromScanner(sym) { currentSymbol = sym; switchView('chart'); loadStock(sym, currentTimeframe); }

function filterScanner(filter) {
    document.querySelectorAll('.stab').forEach(b => b.classList.remove('active'));
    document.querySelector(`.stab[data-stab="${filter}"]`)?.classList.add('active');
    if (!scannerCache) return;
    let r;
    switch (filter) {
        case 'buys': r = scannerCache.results.filter(x => x.signal === 'BUY'); break;
        case 'sells': r = scannerCache.results.filter(x => x.signal === 'SELL'); break;
        case 'gainers': r = scannerCache.top_gainers || []; break;
        case 'losers': r = scannerCache.top_losers || []; break;
        case 'volume': r = scannerCache.volume_spikes || []; break;
        default: r = scannerCache.results;
    }
    renderScannerTable(r);
}

// ═══ BACKTEST ═══
async function runBacktest() {
    const sym = document.getElementById('bt-symbol').value.trim() || currentSymbol;
    const cap = document.getElementById('bt-capital').value || 1000000;
    const bt = document.getElementById('bt-buy-thresh').value || 3;
    const st = document.getElementById('bt-sell-thresh').value || -3;
    const container = document.getElementById('bt-results');
    container.innerHTML = '<div class="loading-state"><div class="loader"></div>Running backtest...</div>';

    const data = await api(`/api/backtest/${sym}?timeframe=1d&capital=${cap}&buy_threshold=${bt}&sell_threshold=${st}`);
    if (!data || data.error) { container.innerHTML = `<div class="empty-state"><p>${data?.error||'Failed'}</p></div>`; return; }

    const rc = data.total_return_pct >= 0 ? GRN : RED;
    const wc = data.win_rate_pct >= 50 ? GRN : RED;
    container.innerHTML = `
        <div class="bt-stats">
            <div class="bt-stat"><div class="bt-stat-value" style="color:${rc}">${data.total_return_pct>0?'+':''}${data.total_return_pct}%</div><div class="bt-stat-label">Total Return</div></div>
            <div class="bt-stat"><div class="bt-stat-value" style="color:${rc}">${fmtC(data.total_pnl)}</div><div class="bt-stat-label">Net P&L</div></div>
            <div class="bt-stat"><div class="bt-stat-value" style="color:${wc}">${data.win_rate_pct}%</div><div class="bt-stat-label">Win Rate</div></div>
            <div class="bt-stat"><div class="bt-stat-value" style="color:${RED}">${data.max_drawdown_pct}%</div><div class="bt-stat-label">Max Drawdown</div></div>
        </div>
        <div class="bt-detail-row">
            <span>Initial: <strong>${fmtC(data.initial_capital)}</strong></span>
            <span>Final: <strong style="color:${rc}">${fmtC(data.final_equity)}</strong></span>
            <span>Trades: <strong>${data.total_trades}</strong></span>
            <span>Wins: <strong style="color:${GRN}">${data.wins}</strong></span>
            <span>Losses: <strong style="color:${RED}">${data.losses}</strong></span>
        </div>
        <div id="bt-equity-chart" style="height:260px;margin-bottom:18px"></div>
        <div class="section-bar"><span>Trade Log</span></div>
        <div class="table-container" style="max-height:280px">
            <table class="data-table"><thead><tr><th>Type</th><th>Price</th><th>Shares</th><th>P&L</th><th>Score</th><th>Date</th></tr></thead>
            <tbody>${(data.trades||[]).map(t => {
                const tc = t.type==='BUY'?GRN:RED;
                return `<tr><td style="color:${tc};font-weight:700">${t.type}</td><td>\u20B9${fmt(t.price)}</td><td>${t.shares}</td>
                <td style="color:${(t.pnl||0)>=0?GRN:RED}">${t.pnl!=null?fmtC(t.pnl):'--'}</td><td>${t.score||'--'}</td>
                <td style="color:var(--t4)">${(t.timestamp||'').substring(0,10)}</td></tr>`;
            }).join('')}</tbody></table>
        </div>`;

    if (data.equity_curve?.length) {
        Plotly.newPlot('bt-equity-chart', [{
            x: data.equity_curve.map(p => p.timestamp.substring(0, 10)),
            y: data.equity_curve.map(p => p.equity),
            type: 'scatter', mode: 'lines',
            line: { color: rc, width: 2 },
            fill: 'tozeroy',
            fillcolor: data.total_return_pct >= 0 ? 'rgba(34,197,94,0.06)' : 'rgba(239,68,68,0.06)',
        }], layout({ y: { tickformat: ',.0f' } }), CFG);
    }
    toast(`Backtest: ${data.total_return_pct}% return`, data.total_return_pct >= 0 ? 'success' : 'error');
}

// ═══ PORTFOLIO ═══
async function loadPortfolio() {
    const [summary, trades] = await Promise.all([api('/api/portfolio'), api('/api/portfolio/trades')]);
    if (summary) {
        const c = summary.total_pnl >= 0 ? GRN : RED;
        document.getElementById('pf-invested').textContent = fmtC(summary.total_invested);
        document.getElementById('pf-current').textContent = fmtC(summary.total_value);
        const pnl = document.getElementById('pf-pnl'); pnl.textContent = fmtC(summary.total_pnl); pnl.style.color = c;
        const ret = document.getElementById('pf-return'); ret.textContent = (summary.total_pnl_pct>=0?'+':'') + summary.total_pnl_pct + '%'; ret.style.color = c;

        document.getElementById('portfolio-tbody').innerHTML = summary.holdings?.length
            ? summary.holdings.map(h => {
                const hc = h.pnl >= 0 ? GRN : RED;
                return `<tr onclick="selectFromScanner('${h.symbol}')">
                    <td class="col-symbol">${h.symbol.replace('.NS','')}</td><td>${h.quantity}</td>
                    <td>\u20B9${fmt(h.avg_price)}</td><td>\u20B9${fmt(h.current_price)}</td>
                    <td>\u20B9${fmt(h.invested)}</td><td>\u20B9${fmt(h.current_value)}</td>
                    <td style="color:${hc}">\u20B9${fmt(h.pnl)}</td><td style="color:${hc}">${h.pnl_pct>=0?'+':''}${h.pnl_pct}%</td></tr>`;
            }).join('')
            : '<tr><td colspan="8" style="text-align:center;color:#6B7280;padding:30px">No holdings yet</td></tr>';
    }
    if (trades) {
        document.getElementById('trades-tbody').innerHTML = trades.length
            ? trades.slice(0, 25).map(t => `<tr>
                <td style="color:#6B7280">${(t.timestamp||'').substring(0,19)}</td>
                <td class="col-symbol">${t.symbol.replace('.NS','')}</td>
                <td style="color:${t.type==='BUY'?GRN:RED};font-weight:700">${t.type}</td>
                <td>${t.quantity}</td><td>\u20B9${fmt(t.price)}</td>
                <td style="color:${(t.pnl||0)>=0?GRN:RED}">${t.pnl?fmtC(t.pnl):'--'}</td></tr>`).join('')
            : '<tr><td colspan="6" style="text-align:center;color:#6B7280;padding:30px">No trades</td></tr>';
    }
}

// ── Trade Modal ──
function openTradeModal(type) {
    tradeModalType = type;
    document.getElementById('trade-modal').style.display = 'flex';
    document.getElementById('modal-title').textContent = type === 'BUY' ? 'Buy Stock' : 'Sell Stock';
    const btn = document.getElementById('modal-submit');
    btn.textContent = type === 'BUY' ? 'Place Buy Order' : 'Place Sell Order';
    btn.className = type === 'BUY' ? 'btn-buy' : 'btn-sell';
    document.getElementById('trade-symbol').value = currentSymbol;
    document.getElementById('trade-qty').value = '';
    document.getElementById('trade-price').value = '';
}
function closeTradeModal() { document.getElementById('trade-modal').style.display = 'none'; }

async function executeTrade() {
    const sym = document.getElementById('trade-symbol').value.trim();
    const qty = parseInt(document.getElementById('trade-qty').value);
    const price = document.getElementById('trade-price').value ? parseFloat(document.getElementById('trade-price').value) : null;
    if (!sym || !qty || qty <= 0) { toast('Enter valid symbol and quantity', 'error'); return; }
    let url = `/api/portfolio/${tradeModalType.toLowerCase()}?symbol=${encodeURIComponent(sym)}&quantity=${qty}`;
    if (price) url += `&price=${price}`;
    const res = await fetch(url, { method: 'POST' });
    const data = await res.json();
    if (data.error) { toast(data.error, 'error'); }
    else { toast(`${tradeModalType} ${qty} x ${sym.replace('.NS','')} @ \u20B9${fmt(data.price||price)}`, 'success'); closeTradeModal(); loadPortfolio(); }
}

// ═══ AUTO REFRESH ═══
function startAutoRefresh() {
    if (autoRefreshTimer) clearInterval(autoRefreshTimer);
    autoRefreshTimer = setInterval(() => { if (currentView === 'chart') loadStock(currentSymbol, currentTimeframe); }, 60000);
}

// ═══ PROFILE VIEW ═══
let profileSelectedColor = '#3B82F6';

async function loadProfile() {
    const p = await api('/api/profile');
    if (!p) return;

    document.getElementById('pf-name').value = p.name || '';
    document.getElementById('pf-email').value = p.email || '';
    document.getElementById('pf-phone').value = p.phone || '';
    document.getElementById('pf-experience').value = p.experience || 'Beginner';
    document.getElementById('pf-risk').value = p.risk_appetite || 'Moderate';
    document.getElementById('pf-capital').value = p.default_capital || 1000000;
    document.getElementById('pf-bio').value = p.bio || '';
    document.getElementById('pf-sectors').value = p.preferred_sectors || '';
    document.getElementById('pf-tg-token').value = p.telegram_token || '';
    document.getElementById('pf-tg-chat').value = p.telegram_chat_id || '';

    profileSelectedColor = p.avatar_color || '#3B82F6';
    updateProfileUI(p.name || 'Trader', p.email, profileSelectedColor, p.experience, p.risk_appetite);

    document.querySelectorAll('.profile-color-opt').forEach(c => {
        c.classList.toggle('active', c.dataset.color === profileSelectedColor);
    });

    if (p.created_at) {
        const d = new Date(p.created_at);
        document.getElementById('profile-member-since').textContent = 'Member since ' + d.toLocaleDateString('en-IN', { year:'numeric', month:'long', day:'numeric' });
    }
}

function updateProfileUI(name, email, color, exp, risk) {
    const initials = name ? name.split(' ').map(w => w[0]).join('').toUpperCase().substring(0, 2) : 'T';
    document.getElementById('prof-avatar').style.background = color;
    document.getElementById('prof-initials').textContent = initials;
    document.getElementById('prof-name').textContent = name || 'Trader';
    document.getElementById('prof-email').textContent = email || 'Set your email in settings below';
    document.getElementById('prof-tag-exp').textContent = exp || 'Beginner';
    document.getElementById('prof-tag-risk').textContent = (risk || 'Moderate') + ' Risk';
}

function pickProfileColor(el) {
    document.querySelectorAll('.profile-color-opt').forEach(c => c.classList.remove('active'));
    el.classList.add('active');
    profileSelectedColor = el.dataset.color;
    document.getElementById('prof-avatar').style.background = profileSelectedColor;
}

async function saveUserProfile() {
    const data = {
        name: document.getElementById('pf-name').value.trim(),
        email: document.getElementById('pf-email').value.trim(),
        phone: document.getElementById('pf-phone').value.trim(),
        experience: document.getElementById('pf-experience').value,
        risk_appetite: document.getElementById('pf-risk').value,
        default_capital: parseFloat(document.getElementById('pf-capital').value) || 1000000,
        bio: document.getElementById('pf-bio').value.trim(),
        preferred_sectors: document.getElementById('pf-sectors').value.trim(),
        avatar_color: profileSelectedColor,
        telegram_token: document.getElementById('pf-tg-token').value.trim(),
        telegram_chat_id: document.getElementById('pf-tg-chat').value.trim(),
    };

    try {
        const res = await fetch('/api/profile', {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(data),
        });
        const result = await res.json();
        if (result && result.status === 'ok') {
            updateProfileUI(data.name, data.email, data.avatar_color, data.experience, data.risk_appetite);
            const ss = document.getElementById('profile-save-status');
            ss.style.display = 'inline';
            setTimeout(() => ss.style.display = 'none', 3000);
            toast('Profile saved successfully', 'success');
        } else {
            toast('Failed to save profile', 'error');
        }
    } catch(e) {
        toast('Failed to save profile', 'error');
    }
}

async function loadProfileStats() {
    const s = await api('/api/profile/stats');
    if (!s) return;

    document.getElementById('ps-trades').textContent = s.total_trades;
    document.getElementById('ps-buys').textContent = s.buy_trades;
    document.getElementById('ps-sells').textContent = s.sell_trades;
    document.getElementById('ps-signals').textContent = s.total_signals;
    document.getElementById('ps-alerts').textContent = s.total_alerts;

    const list = document.getElementById('profile-activity-list');
    if (s.recent_signals && s.recent_signals.length > 0) {
        list.innerHTML = s.recent_signals.map(sig => {
            const color = sig.signal === 'BUY' ? '#22C55E' : sig.signal === 'SELL' ? '#EF4444' : '#F59E0B';
            const time = sig.timestamp ? sig.timestamp.substring(0, 16) : '--';
            return '<div class="profile-activity-item">' +
                '<div class="profile-activity-dot" style="background:' + color + '"></div>' +
                '<div class="profile-activity-text"><strong>' + sig.symbol.replace('.NS','') + '</strong> -- ' + sig.signal + ' (' + (sig.strength || '--') + ') Score: ' + (sig.score || 0) + '</div>' +
                '<div class="profile-activity-time">' + time + '</div>' +
            '</div>';
        }).join('');
    } else {
        list.innerHTML = '<div style="text-align:center;color:#4B5263;padding:20px;font-size:12px">No signals yet. Scan the market first.</div>';
    }
}

function logoutUser() {
    localStorage.removeItem('sm_user');
    window.location.href = '/';
}

async function testTelegram() {
    const status = document.getElementById('tg-test-status');
    status.textContent = 'Sending...';
    status.style.color = '#F59E0B';
    try {
        const res = await fetch('/api/telegram/test', { method: 'POST' });
        const data = await res.json();
        if (data.status === 'ok') {
            status.textContent = 'Sent! Check your Telegram.';
            status.style.color = '#22C55E';
            toast('Test message sent to Telegram!', 'success');
        } else {
            status.textContent = data.error || 'Failed';
            status.style.color = '#EF4444';
            toast(data.error || 'Failed to send', 'error');
        }
    } catch(e) {
        status.textContent = 'Error connecting';
        status.style.color = '#EF4444';
    }
}
