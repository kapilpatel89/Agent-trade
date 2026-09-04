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

// Radar & Opportunities State
let radarData = null;
let currentOppCategory = "all";
let lastSeenPopups = new Set();

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
  // Market Radar every 5s
  setInterval(fetchRadar, 5000);
  // Force chart resize after DOM settles
  setTimeout(() => { if (chartInst) { chartInst.resize(); loadChart(activePair); } }, 800);

  // Redraw chart on window resize
  window.addEventListener('resize', () => { if (chartInst) chartInst.resize(); });
});

async function bootDashboard() {
  await fullPoll();
  fetchRadar(true);
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

  // Futures short selling toggle — show/hide futures options panel
  const futuresToggle = document.getElementById("cfg-enable-futures");
  if (futuresToggle) {
    futuresToggle.addEventListener("change", (e) => {
      const panel = document.getElementById("futures-options-panel");
      if (panel) panel.style.display = e.target.checked ? "block" : "none";
    });
  }

  // Leverage selector buttons
  document.querySelectorAll("#leverage-selector .btn-lev").forEach(b => {
    b.onclick = () => {
      document.querySelectorAll("#leverage-selector .btn-lev").forEach(x => x.classList.remove("active"));
      b.classList.add("active");
      const levInput = document.getElementById("cfg-futures-leverage");
      if (levInput) levInput.value = b.getAttribute("data-lev");
    };
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

  // Smart Radar Modal
  document.getElementById("btn-open-radar").onclick = openRadarModal;
  document.getElementById("radar-modal-close-btn").onclick = closeRadarModal;
  document.getElementById("btn-close-radar-foot").onclick = closeRadarModal;
  document.getElementById("radar-modal").addEventListener("click", e => {
    if (e.target === e.currentTarget) closeRadarModal();
  });

  // Opportunity Category Filter Chips
  document.querySelectorAll(".filter-chip").forEach(chip => {
    chip.onclick = () => {
      document.querySelectorAll(".filter-chip").forEach(c => c.classList.remove("active"));
      chip.classList.add("active");
      currentOppCategory = chip.getAttribute("data-category") || "all";
      renderOpportunities();
    };
  });

  // Telegram Alert Triggers inside Radar Modal
  document.getElementById("btn-trigger-overlap-alert").onclick = () => triggerRadarAlert("seller_overlap");
  document.getElementById("btn-trigger-war-alert").onclick = () => triggerRadarAlert("war_news");
  document.getElementById("btn-trigger-corr-alert").onclick = () => triggerRadarAlert("correlation");
  const buyBtnAlert = document.getElementById("btn-trigger-buy-buttons-alert");
  if (buyBtnAlert) buyBtnAlert.onclick = () => triggerRadarAlert("buy_buttons");
  const sellBtnAlert = document.getElementById("btn-trigger-sell-buttons-alert");
  if (sellBtnAlert) sellBtnAlert.onclick = () => triggerRadarAlert("sell_buttons");
  const shortBtnAlert = document.getElementById("btn-trigger-short-buttons-alert");
  if (shortBtnAlert) shortBtnAlert.onclick = () => triggerRadarAlert("short_alert");

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

    // Futures Short Selling State
    const futuresCheckbox = document.getElementById("cfg-enable-futures");
    const futuresPanel = document.getElementById("futures-options-panel");
    const isFuturesEnabled = Boolean(s.enable_futures_shorting);
    if (futuresCheckbox) futuresCheckbox.checked = isFuturesEnabled;
    if (futuresPanel) futuresPanel.style.display = isFuturesEnabled ? "block" : "none";

    const lev = s.futures_leverage || 2;
    const levInput = document.getElementById("cfg-futures-leverage");
    if (levInput) levInput.value = lev;
    document.querySelectorAll("#leverage-selector .btn-lev").forEach(b => {
      b.classList.toggle("active", b.getAttribute("data-lev") == lev);
    });

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
  const enableFutures = document.getElementById("cfg-enable-futures")?.checked || false;
  const leverage = parseInt(document.getElementById("cfg-futures-leverage")?.value) || 2;

  try {
    await fetch(`${API}/api/control/settings`, {
      method:"POST", headers:{"Content-Type":"application/json"},
      body: JSON.stringify({
        trading_mode: mode,
        initial_capital: capital,
        cycle_interval: interval,
        telegram_chat_id: chatId || null,
        enable_futures_shorting: enableFutures,
        futures_leverage: leverage,
        api_key: apiKey,
        api_secret: apiSec,
        ai_provider: "quantitative"
      })
    });
    closeModal();
    fullPoll();
    fetchRadar(true);
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

// ==========================================================================
// SMART RADAR & OPPORTUNITIES CONTROLLER
// ==========================================================================

async function fetchRadar(force = false) {
  try {
    const url = `${API}/api/radar/overview${force ? "?force_refresh=true" : ""}`;
    const r = await fetch(url);
    const d = await r.json();
    radarData = d;
    renderRadarSummaryStrip(d);
    renderOpportunities();
    handleUrgentPopups(d.urgent_popups || []);
    if (document.getElementById("radar-modal").classList.contains("active")) {
      renderRadarModalContent(d);
    }
  } catch(e) {
    console.error("[Radar] Error fetching radar overview:", e);
  }
}

function renderRadarSummaryStrip(data) {
  if (!data) return;
  const obList = data.orderbook_watchouts || [];
  // Find depth for current active pair or default to BTC
  const ob = obList.find(w => w.pair === activePair) || obList[0] || {};
  
  const bidPct = ob.bid_pressure_pct || 50;
  const askPct = ob.ask_pressure_pct || 50;

  document.getElementById("depth-bid-pct").textContent = `${bidPct}%`;
  document.getElementById("depth-ask-pct").textContent = `${askPct}%`;
  document.getElementById("depth-bar-bids").style.width = `${bidPct}%`;
  document.getElementById("depth-bar-asks").style.width = `${askPct}%`;

  const statusBadge = document.getElementById("radar-main-status");
  const narrativeEl = document.getElementById("radar-main-narrative");
  const timeEl      = document.getElementById("radar-update-time");

  if (ob.overlap_flag) {
    statusBadge.textContent = "🚨 SELLER OVERLAPPING BUYER";
    statusBadge.className   = "rss-status-badge badge-danger";
  } else if (ob.absorption_flag) {
    statusBadge.textContent = "🛡️ BUYER ABSORBING SELLER";
    statusBadge.className   = "rss-status-badge badge-success";
  } else {
    statusBadge.textContent = "⚖️ ORDERBOOK BALANCED";
    statusBadge.className   = "rss-status-badge badge-neutral";
  }

  narrativeEl.textContent = ob.summary || "Orderbook depth balanced.";
  if (data.timestamp) {
    const parts = data.timestamp.split(" ");
    timeEl.textContent = parts[1] || data.timestamp;
  }

  // Live Stick (1h)
  const sticks = data.live_sticks || [];
  const stick = sticks.find(s => s.symbol === activeSymbol) || sticks[0];
  const stickBadge  = document.getElementById("live-stick-badge");
  const stickDetail = document.getElementById("live-stick-detail");

  if (stick) {
    if (stick.status === "BEARISH_WICK") {
      stickBadge.textContent = "🔴 Seller Wick Rejection";
      stickBadge.style.color = "var(--red)";
    } else if (stick.status === "BULLISH_WICK") {
      stickBadge.textContent = "🟢 Buyer Hammer Absorption";
      stickBadge.style.color = "var(--green)";
    } else if (stick.status === "BULL_BODY") {
      stickBadge.textContent = "🚀 Bull Candle Expansion";
      stickBadge.style.color = "var(--green)";
    } else if (stick.status === "BEAR_BODY") {
      stickBadge.textContent = "⚠️ Bearish Dump Expansion";
      stickBadge.style.color = "var(--red)";
    } else {
      stickBadge.textContent = "⚖️ Standard Formation";
      stickBadge.style.color = "var(--cyan)";
    }
    stickDetail.textContent = `Upper ${stick.upper_wick_pct}% | Lower ${stick.lower_wick_pct}%`;
  }
}

function renderOpportunities() {
  if (!radarData || !radarData.opportunities) return;
  const grid = document.getElementById("opportunities-grid");
  const totalBadge = document.getElementById("opps-total-badge");
  const shortChip = document.getElementById("filter-chip-short");

  // Conditional visibility of the Short Setups filter chip
  const isShortingEnabled = Boolean(radarData.enable_futures_shorting);
  if (shortChip) {
    shortChip.style.display = isShortingEnabled ? "inline-flex" : "none";
    if (!isShortingEnabled && currentOppCategory === "short_futures") {
      currentOppCategory = "all";
      document.querySelectorAll(".filter-chip").forEach(c => {
        c.classList.toggle("active", c.getAttribute("data-category") === "all");
      });
    }
  }

  const allOpps = radarData.opportunities || [];
  const filtered = currentOppCategory === "all" 
    ? allOpps 
    : allOpps.filter(o => o.category === currentOppCategory);

  totalBadge.textContent = `${filtered.length} Setup${filtered.length === 1 ? "" : "s"}`;

  if (filtered.length === 0) {
    grid.innerHTML = `<div class="placeholder-row" style="grid-column: 1/-1;">No opportunities found under '${currentOppCategory}' filter at this moment.</div>`;
    return;
  }

  grid.innerHTML = filtered.map(opp => {
    const isBuy = opp.signal === "BUY" || opp.signal === "STRONG_BUY";
    const isShort = opp.signal === "SHORT";

    let sigClass = "signal-danger";
    let sigLabel = "🛡️ DEFENSIVE";
    let execLabel = "🛡️ Set Guard";
    let btnClass = "btn-execute-opp";

    if (isBuy) {
      sigClass = "signal-buy";
      sigLabel = "⚡ BUY SIGNAL";
      execLabel = "⚡ Execute Trade";
    } else if (isShort) {
      sigClass = "signal-danger";
      sigLabel = "🔴 SHORT (FUTURES)";
      execLabel = "🔴 Execute Short";
      btnClass = "btn-execute-opp btn-execute-short";
    }

    const curP = parseFloat(opp.current_price || 0);
    const tgtP = parseFloat(opp.target_price || 0);
    const slP  = parseFloat(opp.stop_loss_price || 0);

    let gainPct = "0.0";
    let lossPct = "0.0";

    if (isShort) {
      gainPct = curP > 0 && tgtP > 0 ? (((curP - tgtP) / curP) * 100).toFixed(1) : "0.0";
      lossPct = curP > 0 && slP > 0 ? (((slP - curP) / curP) * 100).toFixed(1) : "0.0";
    } else {
      gainPct = curP > 0 && tgtP > 0 ? (((tgtP - curP) / curP) * 100).toFixed(1) : "0.0";
      lossPct = curP > 0 && slP > 0  ? (((curP - slP) / curP) * 100).toFixed(1) : "0.0";
    }

    const targetLabel = isShort ? "TARGET (DOWN)" : "TARGET (UP)";
    const stopLabel   = isShort ? "STOP LOSS (UP)" : "STOP LOSS (DOWN)";

    const tagsHtml = (opp.tags || []).map(t => `<span class="opp-tag">${t}</span>`).join("");

    return `
      <div class="opportunity-card ${isShort ? 'opportunity-card-short' : ''}" id="card-${opp.id}">
        <div class="opp-head">
          <div class="opp-asset-title">#${opp.symbol} <span class="opp-cat-pill">${opp.category_label || opp.category}</span></div>
          <span class="opp-signal-badge ${sigClass}">${sigLabel}</span>
        </div>
        <div class="opp-headline">${opp.headline}</div>
        <div class="opp-narrative-box">${opp.narrative}</div>
        <div class="opp-metrics-row">
          <div class="opp-metric-item">
            <span class="opp-metric-lbl">ENTRY</span>
            <span class="opp-metric-val">₹${curP.toLocaleString("en-IN", {maximumFractionDigits: 4})}</span>
          </div>
          <div class="opp-metric-item">
            <span class="opp-metric-lbl">${targetLabel}</span>
            <span class="opp-metric-val" style="color:var(--green);">₹${tgtP.toLocaleString("en-IN", {maximumFractionDigits: 4})} (+${gainPct}%)</span>
          </div>
          <div class="opp-metric-item">
            <span class="opp-metric-lbl">${stopLabel}</span>
            <span class="opp-metric-val" style="color:var(--red);">₹${slP.toLocaleString("en-IN", {maximumFractionDigits: 4})} (-${lossPct}%)</span>
          </div>
        </div>
        <div class="opp-tags-row">
          ${tagsHtml}
        </div>
        <div class="opp-footer-row">
          <div class="opp-conf">⚡ Confidence: <strong>${opp.confidence || 80}%</strong></div>
          <button class="${btnClass}" onclick="executeOpportunity('${opp.id}')">
            ${execLabel}
          </button>
        </div>
      </div>
    `;
  }).join("");
}

async function executeOpportunity(oppId) {
  const btn = event?.currentTarget;
  if (btn) {
    btn.disabled = true;
    btn.textContent = "⏳ Executing...";
  }
  try {
    const r = await fetch(`${API}/api/trades/execute-opportunity`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ opportunity_id: oppId })
    });
    const d = await r.json();
    if (d.success) {
      showNotification(`✅ ${d.message}`, "success");
      fullPoll();
    } else {
      showNotification(`ℹ️ ${d.message}`, "error");
    }
  } catch(e) {
    showNotification("❌ Network error executing trade", "error");
  } finally {
    if (btn) {
      btn.disabled = false;
      btn.textContent = "⚡ Execute Trade";
    }
  }
}

// --------------------------------------------------------------------------
// DESKTOP BROWSER TOAST POPUPS (Live Seller Overlap & War Alerts)
// --------------------------------------------------------------------------

function handleUrgentPopups(popups) {
  if (!popups || popups.length === 0) return;
  popups.forEach(p => {
    if (!lastSeenPopups.has(p.id)) {
      lastSeenPopups.add(p.id);
      showRichToastPopup(p);
    }
  });
  // Keep set size bounded
  if (lastSeenPopups.size > 50) {
    lastSeenPopups = new Set(Array.from(lastSeenPopups).slice(-20));
  }
}

function showRichToastPopup(p) {
  const container = document.getElementById("toast-popup-container");
  if (!container) return;

  const toast = document.createElement("div");
  const isDanger = p.level === "danger";
  toast.className = `toast-popup ${isDanger ? "toast-danger" : "toast-warning"}`;

  const icon = isDanger ? "🚨" : "⚔️";

  toast.innerHTML = `
    <span class="toast-icon">${icon}</span>
    <div class="toast-body">
      <div class="toast-title">${p.title}</div>
      <div class="toast-desc">${p.message}</div>
    </div>
    <button class="toast-close" title="Dismiss">✕</button>
  `;

  toast.querySelector(".toast-close").onclick = () => {
    toast.style.opacity = "0";
    toast.style.transform = "translateX(50px)";
    setTimeout(() => toast.remove(), 300);
  };

  container.appendChild(toast);

  // Auto dismiss after 8 seconds
  setTimeout(() => {
    if (toast.parentElement) {
      toast.style.opacity = "0";
      toast.style.transform = "translateX(50px)";
      setTimeout(() => toast.remove(), 300);
    }
  }, 8000);
}

// --------------------------------------------------------------------------
// SMART RADAR & POPUPS MENU MODAL
// --------------------------------------------------------------------------

function openRadarModal() {
  document.body.style.overflow = "hidden";
  document.getElementById("radar-modal").classList.add("active");
  if (radarData) renderRadarModalContent(radarData);
  fetchRadar(true);
}

function closeRadarModal() {
  document.body.style.overflow = "";
  document.getElementById("radar-modal").classList.remove("active");
  document.getElementById("radar-alert-feedback").innerHTML = "";
}

function renderRadarModalContent(data) {
  if (!data) return;

  // 1. Orderbook Matrix Grid
  const obContainer = document.getElementById("modal-ob-matrix");
  const obList = data.orderbook_watchouts || [];
  if (obList.length > 0) {
    obContainer.innerHTML = obList.map(ob => {
      const isOverlap = ob.overlap_flag;
      const isAbsorb = ob.absorption_flag;
      const tagClass = isOverlap ? "badge-danger" : (isAbsorb ? "badge-success" : "badge-neutral");
      const tagText = isOverlap ? "SELLER OVERLAP" : (isAbsorb ? "BUYER ABSORBING" : "BALANCED");

      return `
        <div class="ob-card">
          <div class="ob-card-top">
            <span>#${ob.symbol}/INR</span>
            <span class="ob-card-tag ${tagClass}">${tagText}</span>
          </div>
          <div class="dgc-label">
            <span class="dgc-bid-lbl">Bids: ${ob.bid_pressure_pct}%</span>
            <span class="dgc-ask-lbl">Asks: ${ob.ask_pressure_pct}%</span>
          </div>
          <div class="depth-split-track" style="margin-bottom:6px;">
            <div class="depth-split-bids" style="width:${ob.bid_pressure_pct}%"></div>
            <div class="depth-split-asks" style="width:${ob.ask_pressure_pct}%"></div>
          </div>
          <div style="font-size:10px; color:var(--text-muted); line-height:1.35;">${ob.summary}</div>
        </div>
      `;
    }).join("");
  }

  // 2. Relation Trades Matrix
  const relContainer = document.getElementById("modal-relation-matrix");
  const relList = data.relation_trades || [];
  if (relList.length > 0) {
    relContainer.innerHTML = relList.map(r => {
      const isBuy = r.signal === "BUY";
      const icon = isBuy ? "🚀" : "⚠️";
      const badgeClass = isBuy ? "signal-buy" : "signal-danger";
      return `
        <div class="relation-item-card">
          <div class="ric-left">
            <div class="ric-title">${icon} #${r.symbol} (${r.cluster || "Altcoin"}) <span class="opp-signal-badge ${badgeClass}">${r.signal}</span></div>
            <div class="ric-sub">${r.narrative}</div>
          </div>
          <div class="ric-metrics">
            <div style="color:#fff; font-weight:700;">Price: ₹${r.current_price.toLocaleString("en-IN", {maximumFractionDigits:2})}</div>
            <div style="color:var(--green);">Target: ₹${r.target_price.toLocaleString("en-IN", {maximumFractionDigits:2})} (+${r.expected_return_pct}%)</div>
            <div style="color:var(--text-dim); font-size:10px;">BTC Lag Gap: ${r.lag_pct >= 0 ? '+' : ''}${parseFloat(r.lag_pct || 0).toFixed(2)}%</div>
          </div>
        </div>
      `;
    }).join("");
  } else {
    relContainer.innerHTML = `<div class="placeholder-row">Correlations aligned with Bitcoin momentum. No extreme sympathy gaps.</div>`;
  }

  // 3. Social Media (X.com) & Geopolitical War Radar
  const socContainer = document.getElementById("modal-social-radar");
  const newsData = data.social_news || {};
  const dir = newsData.direction_probability || {};
  const buzz = newsData.social_buzz_alerts || [];

  socContainer.innerHTML = `
    <div class="srb-row">
      <div>
        <span style="font-size:11px; font-weight:700; color:#fff;">MACRO THREAT LEVEL:</span>
        <strong style="color:${newsData.threat_level >= 50 ? 'var(--red)' : 'var(--green)'}; margin-left:6px;">${newsData.threat_level || 0}/100</strong>
        <span class="count-pill" style="margin-left:6px;">${newsData.threat_status || 'STABLE'}</span>
      </div>
      <div>
        <span style="font-size:11px; font-weight:700; color:#fff;">DIRECTION FORECAST:</span>
        <strong style="color:var(--cyan); margin-left:6px;">${dir.bias || 'NEUTRAL'}</strong>
        <span style="font-size:10px; color:var(--text-muted); margin-left:4px;">(Down: ${dir.down_prob || 50}% | Up: ${dir.up_prob || 50}%)</span>
      </div>
    </div>
    <div class="srb-summary">${newsData.social_summary || 'Monitoring social media and macro RSS feeds.'}</div>
    ${buzz.length > 0 ? `
      <div style="margin-top:10px; padding-top:8px; border-top:1px solid var(--border); font-size:11px;">
        <span class="opp-tag" style="background:rgba(255,184,0,0.15); color:var(--amber);">${buzz[0].tag || 'ALERT'}</span>
        <strong style="color:#fff; margin-left:6px;">${buzz[0].headline || ''}</strong>
        <p style="color:var(--text-muted); margin:3px 0 0;">Impact: ${buzz[0].market_impact || ''}</p>
      </div>
    ` : ''}
  `;
}

async function triggerRadarAlert(alertType) {
  const fb = document.getElementById("radar-alert-feedback");
  fb.innerHTML = `⏳ Dispatching ${alertType} alert to Telegram...`;
  try {
    const r = await fetch(`${API}/api/radar/test-alert`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ alert_type: alertType })
    });
    const d = await r.json();
    if (d.success) {
      fb.innerHTML = `<span style="color:var(--green);">✅ ${d.message}</span>`;
      showNotification(`📲 ${d.message}`, "success");
    } else {
      fb.innerHTML = `<span style="color:var(--red);">❌ ${d.message}</span>`;
      showNotification(`❌ ${d.message}`, "error");
    }
  } catch(e) {
    fb.innerHTML = `<span style="color:var(--red);">❌ Network error sending test alert</span>`;
  }
}

// --------------------------------------------------------------------------
// RADAR & INTERACTIVE ALERT BUTTON BINDINGS
// --------------------------------------------------------------------------
document.getElementById("btn-open-radar")?.addEventListener("click", openRadarModal);
document.getElementById("radar-modal-close-btn")?.addEventListener("click", closeRadarModal);
document.getElementById("btn-close-radar-foot")?.addEventListener("click", closeRadarModal);

document.getElementById("btn-trigger-overlap-alert")?.addEventListener("click", () => triggerRadarAlert("seller_overlap"));
document.getElementById("btn-trigger-war-alert")?.addEventListener("click", () => triggerRadarAlert("war_news"));
document.getElementById("btn-trigger-corr-alert")?.addEventListener("click", () => triggerRadarAlert("correlation"));
document.getElementById("btn-trigger-buy-buttons-alert")?.addEventListener("click", () => triggerRadarAlert("buy_buttons"));
document.getElementById("btn-trigger-sell-buttons-alert")?.addEventListener("click", () => triggerRadarAlert("sell_buttons"));


