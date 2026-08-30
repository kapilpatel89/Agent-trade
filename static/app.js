// ==========================================================================
// NEXUS CRYPTO SURVIVAL AGENT — Frontend Controller v2.0
// ==========================================================================

const API = window.location.origin;

let activePair  = "I-BTC_INR";
let activeMarket = "BTCINR";
let activeSymbol = "BTC";
let chartInst   = null;
let currentFilter = "ALL";
let isRunning   = false;

const TRACKED_PAIRS = [
  { market:"BTCINR",  pair:"I-BTC_INR",  symbol:"BTC",  name:"Bitcoin"  },
  { market:"ETHINR",  pair:"I-ETH_INR",  symbol:"ETH",  name:"Ethereum" },
  { market:"SOLINR",  pair:"I-SOL_INR",  symbol:"SOL",  name:"Solana"   },
  { market:"XRPINR",  pair:"I-XRP_INR",  symbol:"XRP",  name:"Ripple"   },
  { market:"DOGEINR", pair:"I-DOGE_INR", symbol:"DOGE", name:"Dogecoin" },
  { market:"ADAINR",  pair:"I-ADA_INR",  symbol:"ADA",  name:"Cardano"  },
];

// --------------------------------------------------------------------------
// BOOT
// --------------------------------------------------------------------------
document.addEventListener("DOMContentLoaded", () => {
  buildPairButtons();
  wireEvents();
  initChart();
  bootDashboard();
  // Live price tick every 800ms (fast)
  setInterval(tickLivePrices, 800);
  // Full dashboard every 4s
  setInterval(fullPoll, 4000);
  // Thoughts every 3s
  setInterval(fetchThoughts, 3000);
  // Force chart resize after DOM settles
  setTimeout(() => { if (chartInst) { chartInst.resize(); loadChart(activePair); } }, 800);

  // Redraw chart on window resize
  window.addEventListener('resize', () => { if (chartInst) chartInst.resize(); });
});

async function bootDashboard() {
  await fullPoll();
  fetchMovers(false);
  fetchNews(false);
  // Load chart immediately
  await loadChart(activePair);
}

// --------------------------------------------------------------------------
// PAIR BUTTONS
// --------------------------------------------------------------------------
function buildPairButtons() {
  const c = document.getElementById("pair-buttons-container");
  c.innerHTML = "";
  TRACKED_PAIRS.forEach(p => {
    const btn = document.createElement("button");
    btn.className = `pair-btn${p.pair === activePair ? " active" : ""}`;
    btn.textContent = `${p.symbol}/INR`;
    btn.onclick = () => selectPair(p);
    c.appendChild(btn);
  });
}

function selectPair(p) {
  activePair   = p.pair;
  activeMarket = p.market;
  activeSymbol = p.symbol;
  document.querySelectorAll(".pair-btn").forEach(b =>
    b.classList.toggle("active", b.textContent.startsWith(p.symbol))
  );
  document.getElementById("chart-symbol").textContent = `${p.symbol}/INR`;
  loadChart(activePair);
  fetchAnalysis();
}

// --------------------------------------------------------------------------
// LIVE PRICE TICK (fast, lightweight)
// --------------------------------------------------------------------------
async function tickLivePrices() {
  try {
    const r = await fetch(`${API}/api/market/tickers`);
    const d = await r.json();
    updatePriceTicker(d);
  } catch(e) { /* ignore */ }
}

function updatePriceTicker(data) {
  const tickers = data.tickers || [];
  const cur = tickers.find(t => t.market === activeMarket);
  if (cur) {
    const price  = parseFloat(cur.last_price || 0);
    const change = parseFloat(cur.change_24_hour || 0);
    document.getElementById("chart-price").textContent =
      `₹${price.toLocaleString("en-IN", { maximumFractionDigits: 4 })}`;
    const chEl = document.getElementById("chart-change");
    const sign = change >= 0 ? "+" : "";
    chEl.textContent = `${sign}${change.toFixed(2)}%`;
    chEl.style.color = change >= 0 ? "#00f59b" : "#ff3366";
  }
  // Update scan ticker with a random interesting coin
  const inr = tickers.filter(t => t.market && t.market.endsWith("INR"));
  if (inr.length) {
    const pick = inr[Math.floor(Math.random() * Math.min(40, inr.length))];
    const sym  = (pick.market || "").replace("INR","");
    const pr   = parseFloat(pick.last_price || 0);
    const ch   = parseFloat(pick.change_24_hour || 0);
    const sign = ch >= 0 ? "+" : "";
    setTickerText(`📡 Scanning ${sym}/INR  ₹${pr.toLocaleString("en-IN",{maximumFractionDigits:4})}  ${sign}${ch.toFixed(2)}%  |  ${inr.length} markets live`);
  }
}

function setTickerText(txt) {
  const el = document.getElementById("scan-ticker-text");
  if (el) el.textContent = txt;
}

// --------------------------------------------------------------------------
// FULL POLL
// --------------------------------------------------------------------------
async function fullPoll() {
  try {
    const [status, tickers] = await Promise.all([
      fetch(`${API}/api/status`).then(r => r.json()),
      fetch(`${API}/api/market/tickers`).then(r => r.json()),
    ]);
    updateHUD(status);
    updatePriceTicker(tickers);
    fetchPositions();
    fetchTrades();
    fetchAnalysis();
    fetchThoughts();
  } catch(e) { console.error("poll error:", e); }
}

// --------------------------------------------------------------------------
// HUD
// --------------------------------------------------------------------------
function updateHUD(s) {
  setLoopState(s.is_running);

  // Mode badge
  const modeBadge = document.getElementById("trading-mode-badge");
  const modeText  = document.getElementById("trading-mode-text");
  if (s.trading_mode === "live") {
    modeBadge.className = "mode-pill live";
    modeText.textContent = "⚡ LIVE SPOT";
  } else {
    modeBadge.className = "mode-pill";
    modeText.textContent = `🧪 PAPER ₹${(s.initial_capital||1000).toFixed(0)}`;
  }

  // Equity
  document.getElementById("hud-total-equity").textContent =
    `₹${s.total_equity.toLocaleString("en-IN",{minimumFractionDigits:2,maximumFractionDigits:2})}`;
  document.getElementById("hud-inr-cash").textContent =
    `₹${s.inr_cash.toLocaleString("en-IN",{minimumFractionDigits:2})}`;

  const pnlEl   = document.getElementById("hud-net-pnl");
  const pnlSign = s.net_pnl_inr >= 0 ? "+" : "";
  pnlEl.textContent = `${pnlSign}₹${s.net_pnl_inr.toFixed(2)} (${pnlSign}${s.net_pnl_pct.toFixed(2)}%)`;
  pnlEl.className   = `hm-val ${s.net_pnl_inr >= 0 ? "positive" : "negative"}`;

  const stance = s.stance || {};
  document.getElementById("hud-peak-equity").textContent = `₹${(stance.peak_equity||s.total_equity).toFixed(0)}`;
  document.getElementById("hud-drawdown").textContent    = `${s.drawdown_pct.toFixed(2)}%`;

  // Health
  const hp = s.health_pct || 100;
  document.getElementById("hud-health-pct").textContent = `${hp.toFixed(1)}%`;
  const bar = document.getElementById("hud-health-bar");
  bar.style.width = `${Math.min(100, Math.max(0, hp))}%`;
  if (hp > 80)       bar.style.background = "linear-gradient(90deg,#00f59b,#00d2ff)";
  else if (hp > 50)  bar.style.background = "linear-gradient(90deg,#ffb800,#00f59b)";
  else               bar.style.background = "linear-gradient(90deg,#ff3366,#ffb800)";

  const runwayEl = document.getElementById("hud-runway");
  if (hp > 80)       { runwayEl.textContent = "OPTIMAL";  runwayEl.className = "hm-val text-success"; }
  else if (hp > 50)  { runwayEl.textContent = "CAUTION";  runwayEl.className = "hm-val text-warning"; }
  else               { runwayEl.textContent = "CRITICAL"; runwayEl.className = "hm-val negative"; }

  document.getElementById("hud-win-rate").textContent    = `${s.win_rate.toFixed(1)}%`;
  document.getElementById("hud-total-trades").textContent = s.total_trades;
  document.getElementById("hud-total-fees").textContent   = `₹${s.total_fees_inr.toFixed(2)}`;

  // Stance
  const sb = document.getElementById("hud-stance-badge");
  sb.textContent = stance.label || "PRUDENT";
  const sl = (stance.stance || "prudent").toLowerCase().replace("_mode","");
  sb.className = `stance-badge-large stance-${sl}`;
  document.getElementById("hud-stance-desc").textContent = stance.description || "";
  document.getElementById("hud-risk-pct").textContent =
    `${((stance.risk_per_trade_pct||0.15)*100).toFixed(0)}% (₹${(s.total_equity*(stance.risk_per_trade_pct||0.15)).toFixed(0)})`;
  document.getElementById("hud-positions-limit").textContent =
    `${s.open_positions_count} / ${stance.max_positions||2}`;
  document.getElementById("hud-trailing-stop").textContent =
    `${((stance.trailing_stop_pct||0.015)*100).toFixed(1)}%`;
  document.getElementById("hud-stop-loss").textContent =
    `${((stance.stop_loss_pct||0.02)*100).toFixed(1)}%`;

  // AI badge
  fetch(`${API}/api/ai/status`).then(r => r.json()).then(ai => {
    const el = document.getElementById("ai-brain-badge-text");
    if (!el) return;
    if (ai.provider === "gemini" && ai.has_key) {
      const m = (ai.gemini_model||"gemini").replace("gemini-","").toUpperCase();
      el.textContent = `✨ GEMINI ${m}`;
    } else if (ai.provider === "openai" && ai.has_key) {
      el.textContent = "✨ GPT-4O";
    } else {
      el.textContent = "🧠 QUANT AI";
    }
  }).catch(() => {});
}

function setLoopState(running) {
  isRunning = running;
  const dot  = document.getElementById("system-status-dot");
  const txt  = document.getElementById("system-status-text");
  const icon = document.getElementById("loop-icon");
  const bTxt = document.getElementById("loop-btn-text");
  const btn  = document.getElementById("btn-toggle-loop");
  if (running) {
    dot.style.background  = "#00f59b";
    txt.textContent       = "AGENT RUNNING";
    icon.textContent      = "⏸";
    bTxt.textContent      = "Pause";
    btn.className         = "btn btn-primary";
  } else {
    dot.style.background  = "#ffb800";
    txt.textContent       = "AGENT PAUSED";
    icon.textContent      = "▶";
    bTxt.textContent      = "Resume";
    btn.className         = "btn btn-secondary";
  }
}

// --------------------------------------------------------------------------
// THOUGHT STREAM
// --------------------------------------------------------------------------
let rawThoughts = [];

async function fetchThoughts() {
  try {
    const r = await fetch(`${API}/api/thoughts?limit=80`);
    const d = await r.json();
    rawThoughts = d.thoughts || [];
    renderThoughts();
  } catch(e) { /* ignore */ }
}

function renderThoughts() {
  const feed = document.getElementById("thought-feed");
  let list = rawThoughts;
  if (currentFilter !== "ALL") {
    list = rawThoughts.filter(t => t.category === currentFilter);
  }
  if (!list.length) {
    feed.innerHTML = `<div class="thought-item info"><div class="thought-body">No entries for "${currentFilter}" filter.</div></div>`;
    return;
  }
  const html = list.map(t => `
    <div class="thought-item ${t.level||"info"}">
      <div class="thought-meta">
        <span class="thought-badge">${t.category}</span>
        <span class="thought-time">${t.timestamp}</span>
      </div>
      <div class="thought-title">${escHtml(t.title)}</div>
      <div class="thought-body">${escHtml(t.details)}</div>
    </div>
  `).join("");
  feed.innerHTML = html;
}

function escHtml(str) {
  return String(str)
    .replace(/&/g,"&amp;").replace(/</g,"&lt;")
    .replace(/>/g,"&gt;").replace(/"/g,"&quot;");
}

// --------------------------------------------------------------------------
// MARKET MOVERS
// --------------------------------------------------------------------------
async function fetchMovers(force = false) {
  try {
    const r = await fetch(`${API}/api/market/movers?force_refresh=${force}`);
    const d = await r.json();

    const badge = document.getElementById("scanned-total-badge");
    if (d.total_scanned) {
      badge.textContent = `${d.liquid_count||d.total_scanned} liquid / ${d.total_scanned} scanned`;
    }

    const gainers = d.top_gainers || [];
    const container = document.getElementById("movers-container");

    if (!gainers.length) {
      container.innerHTML = `<div class="placeholder-row">Scanning CoinDCX markets...</div>`;
      return;
    }

    container.innerHTML = "";
    gainers.slice(0, 15).forEach(m => {
      const isPos = m.change_24h >= 0;
      const sign  = isPos ? "+" : "";
      const row   = document.createElement("div");
      row.className = "mover-row";
      row.onclick = () => selectPair({ market:m.market, pair:m.pair, symbol:m.symbol, name:m.name });

      // Show some technical hints from scanner data
      let techHint = "";
      if (m.volume_surge && m.volume_surge > 1.5) techHint = `🔥 Vol ${m.volume_surge.toFixed(1)}x`;
      else if (m.spread_pct !== undefined) techHint = `Spd ${m.spread_pct.toFixed(2)}%`;

      row.innerHTML = `
        <div class="mover-left">
          <span class="mover-symbol">#${m.symbol}</span>
          <span class="mover-name">${m.name}</span>
          ${techHint ? `<span class="mover-indicators">${techHint}</span>` : ""}
        </div>
        <div class="mover-right">
          <span class="mover-price">₹${m.last_price.toLocaleString("en-IN",{maximumFractionDigits:4})}</span>
          <span class="mover-change ${isPos ? "positive" : "negative"}">${sign}${m.change_24h.toFixed(2)}%</span>
        </div>
      `;
      container.appendChild(row);
    });
  } catch(e) { console.error("movers error:", e); }
}

// --------------------------------------------------------------------------
// TECHNICAL ANALYSIS PANEL
// --------------------------------------------------------------------------
async function fetchAnalysis() {
  try {
    const r = await fetch(`${API}/api/market/analysis`);
    const d = await r.json();
    const decisions = d.decisions || [];
    const dec = decisions.find(x => x.market === activeMarket);

    if (dec && dec.ta) {
      const ta = dec.ta;
      const sig = document.getElementById("tech-overall-signal");
      sig.textContent = `${dec.action} ${dec.composite_score >= 0 ? "+" : ""}${dec.composite_score}`;
      sig.className = `signal-tag ${dec.action === "BUY" ? "positive" : dec.action === "SELL" ? "negative" : ""}`;

      // RSI
      const rsi = parseFloat(ta.rsi);
      document.getElementById("ind-rsi").textContent = rsi.toFixed(1);
      document.getElementById("ind-rsi").style.color =
        rsi < 35 ? "#00f59b" : rsi > 65 ? "#ff3366" : "#eef2fc";
      document.getElementById("ind-rsi-status").textContent =
        rsi < 30 ? "🟢 Oversold — Bounce Zone" : rsi > 70 ? "🔴 Overbought" : rsi < 45 ? "Mild Oversold" : "Neutral";

      // MACD
      const macd = parseFloat(ta.macd_hist);
      const macdSign = macd >= 0 ? "+" : "";
      document.getElementById("ind-macd").textContent = `${macdSign}${macd.toFixed(3)}`;
      document.getElementById("ind-macd").style.color = macd > 0 ? "#00f59b" : "#ff3366";
      document.getElementById("ind-macd-status").textContent =
        macd > 0 ? "Bullish Momentum" : "Bearish Momentum";

      // EMA
      document.getElementById("ind-ema").textContent = `${ta.ema9} / ${ta.ema21}`;
      document.getElementById("ind-ema-status").textContent =
        ta.current_price > ta.ema9 ? "✅ Price > EMA9" : "⚠ Price < EMA9";

      // BB
      const bbSpread = (parseFloat(ta.bb_upper) - parseFloat(ta.bb_lower)).toFixed(0);
      document.getElementById("ind-bb").textContent = `±₹${bbSpread}`;
      document.getElementById("ind-bb-status").textContent = `${ta.bb_lower} – ${ta.bb_upper}`;

      // ATR
      document.getElementById("ind-atr").textContent = `₹${ta.atr}`;
      document.getElementById("ind-atr-status").textContent = `SL Base -${dec.stop_loss_pct||"--"}%`;

      // Volume
      const vs = parseFloat(ta.volume_surge);
      document.getElementById("ind-vol").textContent = `${vs.toFixed(2)}x`;
      document.getElementById("ind-vol-status").textContent =
        vs > 2 ? "🔥 Heavy Spike" : vs > 1.3 ? "📈 Elevated" : "Normal Flow";

      // Breakdown
      const list = document.getElementById("breakdown-list");
      list.innerHTML = "";
      (ta.signals_breakdown || []).forEach(s => {
        const li = document.createElement("li");
        li.textContent = s;
        list.appendChild(li);
      });
      if (dec.thesis) {
        const li = document.createElement("li");
        li.style.color = "#00d2ff";
        li.textContent = `🧠 ${dec.thesis}`;
        list.appendChild(li);
      }
    }
  } catch(e) { /* ignore */ }
}

// --------------------------------------------------------------------------
// NEWS
// --------------------------------------------------------------------------
async function fetchNews(force = false) {
  try {
    const r = await fetch(`${API}/api/news?force_refresh=${force}`);
    const d = await r.json();

    const threat   = d.threat_level || 0;
    const sentiment = d.crypto_sentiment || 0;
    const sentSign  = sentiment >= 0 ? "+" : "";

    document.getElementById("hud-threat-badge").textContent =
      d.threat_status || "STABLE";
    document.getElementById("hud-threat-badge").className =
      `threat-badge ${threat >= 70 ? "threat-high" : threat >= 40 ? "threat-med" : "threat-low"}`;
    document.getElementById("hud-threat-level").textContent = `${threat}/100`;
    document.getElementById("hud-threat-fill").style.width = `${threat}%`;
    document.getElementById("hud-crypto-sentiment").textContent =
      `${d.sentiment_label||"NEUTRAL"} (${sentSign}${sentiment})`;
    document.getElementById("hud-alerts-count").textContent =
      `${(d.breaking_alerts||[]).length}`;
    document.getElementById("hud-sources-count").textContent =
      `${d.total_articles_scanned||0} articles scanned`;

    const articles = d.articles || [];
    const newsEl   = document.getElementById("news-feed-container");
    if (!articles.length) {
      newsEl.innerHTML = `<div class="placeholder-row">No recent news available.</div>`;
      return;
    }
    newsEl.innerHTML = "";
    articles.forEach(art => {
      const item = document.createElement("div");
      item.className = "news-item";
      item.innerHTML = `
        <span class="news-badge ${art.badge_class || "info"}">${art.badge || "NEWS"}</span>
        <div>
          <div class="news-title">
            <a href="${art.link}" target="_blank" rel="noopener">${escHtml(art.title)}</a>
            <span class="news-source">${escHtml(art.source||"")}</span>
          </div>
        </div>
      `;
      newsEl.appendChild(item);
    });
  } catch(e) { /* ignore */ }
}

// --------------------------------------------------------------------------
// POSITIONS
// --------------------------------------------------------------------------
async function fetchPositions() {
  try {
    const r = await fetch(`${API}/api/positions`);
    const d = await r.json();
    const positions = d.positions || [];
    const badge = document.getElementById("open-positions-count-badge");
    badge.textContent = `${positions.length} Open`;

    const tbody = document.getElementById("positions-table-body");
    if (!positions.length) {
      tbody.innerHTML = `<tr><td colspan="9" class="empty-row">No active positions. Capital held in INR.</td></tr>`;
      return;
    }
    tbody.innerHTML = "";
    positions.forEach(p => {
      const pnlSign  = p.unrealized_pnl_inr >= 0 ? "+" : "";
      const pnlClass = p.unrealized_pnl_inr >= 0 ? "positive" : "negative";
      const tr = document.createElement("tr");
      tr.innerHTML = `
        <td><strong>${p.symbol}</strong></td>
        <td><span class="stance-badge-large stance-expansion" style="padding:2px 6px;font-size:9px">${p.side}</span></td>
        <td>${p.quantity}</td>
        <td>₹${p.entry_price.toLocaleString("en-IN")}</td>
        <td>₹${p.current_price.toLocaleString("en-IN")}</td>
        <td>₹${p.trailing_stop_price || p.stop_loss_price}</td>
        <td>₹${p.take_profit_1} / ₹${p.take_profit_2}</td>
        <td class="${pnlClass}">${pnlSign}₹${p.unrealized_pnl_inr.toFixed(2)} (${pnlSign}${p.unrealized_pnl_pct.toFixed(2)}%)</td>
        <td><button class="btn btn-xs btn-danger" onclick="closePosition('${p.id}')">Close</button></td>
      `;
      tbody.appendChild(tr);
    });
  } catch(e) { /* ignore */ }
}

async function closePosition(id) {
  if (confirm("Close this position at market price?")) {
    await fetch(`${API}/api/control/emergency-liquidate`, { method:"POST" });
    fetchPositions();
    fullPoll();
  }
}

// --------------------------------------------------------------------------
// TRADES
// --------------------------------------------------------------------------
async function fetchTrades() {
  try {
    const r = await fetch(`${API}/api/trades?limit=30`);
    const d = await r.json();
    const trades = d.trades || [];
    document.getElementById("trade-history-count-badge").textContent = `${trades.length} Closed`;

    const tbody = document.getElementById("trades-table-body");
    if (!trades.length) {
      tbody.innerHTML = `<tr><td colspan="9" class="empty-row">No closed trades yet.</td></tr>`;
      return;
    }
    tbody.innerHTML = "";
    trades.forEach(t => {
      const pnlSign  = t.net_pnl_inr >= 0 ? "+" : "";
      const pnlClass = t.net_pnl_inr >= 0 ? "positive" : "negative";
      const tr = document.createElement("tr");
      tr.innerHTML = `
        <td>${t.closed_at ? t.closed_at.split(" ")[1] : "--"}</td>
        <td><strong>${t.symbol}</strong></td>
        <td>${t.quantity}</td>
        <td>₹${t.entry_price}</td>
        <td>₹${t.exit_price}</td>
        <td>₹${t.net_return_inr ? t.net_return_inr.toFixed(2) : "--"}</td>
        <td>₹${t.fees_inr ? t.fees_inr.toFixed(2) : "0.00"}</td>
        <td class="${pnlClass}">${pnlSign}₹${t.net_pnl_inr.toFixed(2)} (${pnlSign}${t.net_pnl_pct.toFixed(2)}%)</td>
        <td style="font-size:10px;color:#8899b5">${t.exit_reason||"--"}</td>
      `;
      tbody.appendChild(tr);
    });
  } catch(e) { /* ignore */ }
}

// --------------------------------------------------------------------------
// CHART
// --------------------------------------------------------------------------
function initChart() {
  const canvas = document.getElementById("trading-chart");
  const ctx = canvas.getContext("2d");
  // Ensure canvas has proper height set
  canvas.style.width = "100%";
  chartInst = new Chart(ctx, {
    type: "line",
    data: {
      labels: [],
      datasets: [
        {
          label: "Price",
          data: [],
          borderColor: "#00f59b",
          borderWidth: 2,
          backgroundColor: "rgba(0,245,155,0.05)",
          fill: true,
          tension: 0.2,
          pointRadius: 0,
          pointHoverRadius: 4,
        },
        {
          label: "EMA 9",
          data: [],
          borderColor: "#00d2ff",
          borderWidth: 1.5,
          borderDash: [3, 3],
          fill: false,
          pointRadius: 0,
          tension: 0.2,
        },
        {
          label: "EMA 21",
          data: [],
          borderColor: "#ffb800",
          borderWidth: 1.5,
          borderDash: [4, 4],
          fill: false,
          pointRadius: 0,
          tension: 0.2,
        },
      ],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      animation: { duration: 200 },
      interaction: { intersect: false, mode: "index" },
      plugins: {
        legend: {
          display: true,
          position: "top",
          labels: { color:"#8899b5", font:{ family:"'JetBrains Mono',monospace", size:10 }, boxWidth:20 },
        },
        tooltip: {
          backgroundColor: "rgba(11,18,32,0.95)",
          borderColor: "rgba(255,255,255,0.1)",
          borderWidth: 1,
          titleFont: { family:"'Outfit',sans-serif", size:12 },
          bodyFont:  { family:"'JetBrains Mono',monospace", size:11 },
          callbacks: {
            label: ctx => `${ctx.dataset.label}: ₹${Number(ctx.parsed.y).toLocaleString("en-IN")}`,
          },
        },
      },
      scales: {
        x: {
          grid: { color:"rgba(255,255,255,0.04)" },
          ticks: { color:"#4a5c7a", font:{ family:"'JetBrains Mono',monospace", size:9 }, maxTicksLimit:8 },
        },
        y: {
          position: "right",
          grid: { color:"rgba(255,255,255,0.04)" },
          ticks: {
            color: "#4a5c7a",
            font: { family:"'JetBrains Mono',monospace", size:9 },
            callback: v => "₹" + Number(v).toLocaleString("en-IN"),
          },
        },
      },
    },
  });
}

async function loadChart(pair) {
  try {
    const r = await fetch(`${API}/api/market/candles?pair=${pair}&interval=1h&limit=60`);
    const d = await r.json();
    const candles = d.candles || [];
    if (!candles.length || !chartInst) {
      console.warn("[Chart] No candle data for", pair, candles.length, "candles received");
      return;
    }

    const labels = candles.map(c => {
      const dt = new Date(c.time);
      return `${dt.getHours().toString().padStart(2,"0")}:${dt.getMinutes().toString().padStart(2,"0")}`;
    });
    const prices = candles.map(c => parseFloat(c.close));
    const ema9   = calcEMA(prices, 9);
    const ema21  = calcEMA(prices, 21);

    // Resize first so Chart.js has correct canvas dimensions
    chartInst.resize();

    chartInst.data.labels           = labels;
    chartInst.data.datasets[0].data = prices;
    chartInst.data.datasets[1].data = ema9;
    chartInst.data.datasets[2].data = ema21;
    chartInst.update();
  } catch(e) { console.error("[Chart] Error:", e); }
}

function calcEMA(vals, span) {
  const k = 2 / (span + 1);
  let prev = vals[0];
  return vals.map(v => { prev = v * k + prev * (1 - k); return +prev.toFixed(4); });
}

// --------------------------------------------------------------------------
// EVENT WIRING
// --------------------------------------------------------------------------
function wireEvents() {
  // Run cycle
  document.getElementById("btn-run-cycle").onclick = async () => {
    const btn = document.getElementById("btn-run-cycle");
    btn.disabled = true;
    btn.innerHTML = "⏳ Running...";
    try {
      await fetch(`${API}/api/control/cycle`, { method:"POST" });
      await fullPoll();
    } finally {
      btn.disabled = false;
      btn.innerHTML = `<svg width="14" height="14" viewBox="0 0 16 16" fill="currentColor"><path d="M8 1a7 7 0 100 14A7 7 0 008 1zm0 12a5 5 0 110-10A5 5 0 018 13zM7 5v4l3 1.5-.5 1L6 9V5h1z"/></svg> Run Cycle`;
    }
  };

  // Toggle loop
  document.getElementById("btn-toggle-loop").onclick = async () => {
    const r = await fetch(`${API}/api/control/toggle-loop`, { method:"POST" });
    const d = await r.json();
    setLoopState(d.is_running);
  };

  // Emergency liquidate
  document.getElementById("btn-emergency-liquidate").onclick = async () => {
    if (confirm("🚨 Emergency: Liquidate ALL positions to 100% INR cash?")) {
      const r = await fetch(`${API}/api/control/emergency-liquidate`, { method:"POST" });
      const d = await r.json();
      alert(`Liquidated ${d.closed_positions} position(s). Cash: ₹${d.inr_cash.toFixed(2)}`);
      fullPoll();
    }
  };

  // Settings
  document.getElementById("btn-settings").onclick = openModal;
  document.getElementById("modal-close-btn").onclick = closeModal;
  document.getElementById("btn-cancel-modal").onclick = closeModal;

  // Trading mode toggle — show/hide live keys section
  document.querySelectorAll("input[name='trading_mode']").forEach(radio => {
    radio.addEventListener("change", () => {
      const liveSection = document.getElementById("live-keys-section");
      liveSection.style.display = radio.value === "live" ? "block" : "none";
    });
  });

  // Save settings
  document.getElementById("btn-save-settings").onclick = saveSettings;

  // Reset wallet
  document.getElementById("btn-reset-wallet").onclick = async () => {
    const cap = parseFloat(document.getElementById("cfg-initial-capital").value) || 1000;
    if (confirm(`Reset paper wallet to ₹${cap.toFixed(2)} INR?`)) {
      await fetch(`${API}/api/control/reset-wallet`, {
        method:"POST", headers:{"Content-Type":"application/json"},
        body: JSON.stringify({ capital: cap })
      });
      closeModal();
      fullPoll();
    }
  };

  // Refresh buttons
  document.getElementById("btn-refresh-news").onclick   = () => fetchNews(true);
  document.getElementById("btn-refresh-movers").onclick = () => fetchMovers(true);

  // Telegram detect
  document.getElementById("btn-detect-telegram").onclick = detectTelegramChat;
  // Telegram test
  document.getElementById("btn-test-telegram").onclick   = testTelegram;

  // Thought filter tabs
  document.querySelectorAll(".filter-btn").forEach(btn => {
    btn.onclick = () => {
      document.querySelectorAll(".filter-btn").forEach(b => b.classList.remove("active"));
      btn.classList.add("active");
      currentFilter = btn.getAttribute("data-filter") || "ALL";
      renderThoughts();
    };
  });

  // Close modal on overlay click
  document.getElementById("config-modal").addEventListener("click", e => {
    if (e.target === e.currentTarget) closeModal();
  });
}

function openModal() {
  document.body.style.overflow = "hidden";
  fetch(`${API}/api/settings`).then(r => r.json()).then(s => {
    const modeEl = document.querySelector(`input[name="trading_mode"][value="${s.trading_mode}"]`);
    if (modeEl) {
      modeEl.checked = true;
      document.getElementById("live-keys-section").style.display =
        s.trading_mode === "live" ? "block" : "none";
    }
    document.getElementById("cfg-initial-capital").value = s.initial_capital || 1000;
    document.getElementById("cfg-interval").value = s.cycle_interval || 30;
    if (s.telegram_chat_id)
      document.getElementById("cfg-telegram-chat").value = s.telegram_chat_id;
    document.getElementById("config-modal").classList.add("active");
  });
}

function closeModal() {
  document.body.style.overflow = "";
  document.getElementById("config-modal").classList.remove("active");
  document.getElementById("telegram-feedback").innerHTML = "";
}

async function saveSettings() {
  const mode     = document.querySelector("input[name='trading_mode']:checked")?.value || "paper";
  const capital  = parseFloat(document.getElementById("cfg-initial-capital").value) || 1000;
  const interval = parseInt(document.getElementById("cfg-interval").value) || 30;
  const chatId   = document.getElementById("cfg-telegram-chat").value.trim();
  const apiKey   = document.getElementById("cfg-api-key")?.value?.trim() || null;
  const apiSec   = document.getElementById("cfg-api-secret")?.value?.trim() || null;

  try {
    await fetch(`${API}/api/control/settings`, {
      method:"POST", headers:{"Content-Type":"application/json"},
      body: JSON.stringify({
        trading_mode: mode,
        initial_capital: capital,
        cycle_interval: interval,
        telegram_chat_id: chatId || null,
        api_key: apiKey,
        api_secret: apiSec,
        ai_provider: "quantitative"
      })
    });
    closeModal();
    fullPoll();
    showNotification("✅ Settings saved!", "success");
  } catch(e) {
    showNotification("❌ Error saving settings", "error");
  }
}

async function detectTelegramChat() {
  const btn = document.getElementById("btn-detect-telegram");
  btn.disabled = true;
  btn.textContent = "🔍 Detecting...";
  setFeedback("info", "🔍 Scanning @antigravitycode_bot for your Chat ID...");
  try {
    const r = await fetch(`${API}/api/telegram/detect-chat-id`, {
      method:"POST", headers:{"Content-Type":"application/json"},
      body: JSON.stringify({ token: null })
    });
    const d = await r.json();
    if (d.success) {
      document.getElementById("cfg-telegram-chat").value = d.chat_id;
      setFeedback("success", `✅ Chat ID found: <strong>${d.chat_id}</strong>`);
    } else {
      setFeedback("error", `ℹ️ ${d.message} — <a href="https://t.me/antigravitycode_bot" target="_blank">Open @antigravitycode_bot</a>`);
    }
  } catch(e) {
    setFeedback("error", "❌ Network error.");
  } finally {
    btn.disabled = false;
    btn.textContent = "🔍 Detect";
  }
}

async function testTelegram() {
  const btn    = document.getElementById("btn-test-telegram");
  const chatId = document.getElementById("cfg-telegram-chat").value.trim();
  btn.disabled = true;
  btn.textContent = "📲 Sending...";
  setFeedback("info", "📲 Dispatching test alert...");
  try {
    const r = await fetch(`${API}/api/telegram/test`, {
      method:"POST", headers:{"Content-Type":"application/json"},
      body: JSON.stringify({ token: null, chat_id: chatId || null })
    });
    const d = await r.json();
    if (d.success) {
      setFeedback("success", "✅ Test alert delivered! Check Telegram.");
    } else {
      setFeedback("error", `❌ ${d.message}`);
    }
  } catch(e) {
    setFeedback("error", "❌ Network error.");
  } finally {
    btn.disabled = false;
    btn.textContent = "📲 Test Alert";
  }
}

function setFeedback(type, html) {
  const el = document.getElementById("telegram-feedback");
  el.innerHTML = `<div class="feedback-${type}">${html}</div>`;
}

// --------------------------------------------------------------------------
// SMALL NOTIFICATION TOAST
// --------------------------------------------------------------------------
function showNotification(msg, type = "info") {
  const toast = document.createElement("div");
  toast.style.cssText = `
    position:fixed; bottom:20px; right:20px; z-index:9999;
    padding:10px 16px; border-radius:8px; font-size:12px; font-weight:600;
    background:${type==="success"?"rgba(0,245,155,0.15)":type==="error"?"rgba(255,51,102,0.15)":"rgba(0,210,255,0.12)"};
    border:1px solid ${type==="success"?"rgba(0,245,155,0.4)":type==="error"?"rgba(255,51,102,0.4)":"rgba(0,210,255,0.3)"};
    color:${type==="success"?"#00f59b":type==="error"?"#ff3366":"#00d2ff"};
    backdrop-filter:blur(10px);
    animation:fadeInUp 0.3s ease;
  `;
  toast.textContent = msg;
  document.body.appendChild(toast);
  setTimeout(() => toast.remove(), 3500);
}
