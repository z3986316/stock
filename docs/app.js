const UP = "#ef4444";
const DOWN = "#3b82f6";
const FLAT = "#9ca3af";

const fmtKrw = (n) => (n == null ? "-" : n.toLocaleString("ko-KR") + "원");
const fmtPct = (v) => (v > 0 ? "+" : "") + v.toFixed(2) + "%";
const cls = (v) => (v > 0.005 ? "up" : v < -0.005 ? "down" : "flat");
const arrow = (v) => (v > 0.005 ? "▲" : v < -0.005 ? "▼" : "—");

async function load() {
  const res = await fetch("data.json?v=" + Date.now());
  if (!res.ok) {
    document.body.innerHTML = "<p>data.json 로드 실패</p>";
    return;
  }
  const data = await res.json();
  document.getElementById("generated").textContent =
    "마지막 갱신: " + data.generated_at;
  renderComparison(data.tickers);
  renderTickers(data.tickers);
}

function renderComparison(tickers) {
  const valid = tickers.filter((t) => t.history && t.history.length > 0);
  if (valid.length === 0) return;

  const minLen = Math.min(...valid.map((t) => t.history.length));
  const slice = (arr) => arr.slice(arr.length - minLen);

  const labels = slice(valid[0].history).map((h) => h.date.slice(5));
  const datasets = valid.map((t, i) => {
    const hist = slice(t.history);
    const base = hist[0].close;
    const color = i === 0 ? "#60a5fa" : "#f59e0b";
    return {
      label: `${t.ticker} ${t.name}`,
      data: hist.map((h) => (h.close / base) * 100),
      borderColor: color,
      backgroundColor: color + "22",
      tension: 0.15,
      pointRadius: 0,
      borderWidth: 2,
    };
  });

  new Chart(document.getElementById("comparison-chart"), {
    type: "line",
    data: { labels, datasets },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      interaction: { mode: "index", intersect: false },
      plugins: {
        legend: { position: "bottom", labels: { color: "#8b93a7" } },
        tooltip: {
          callbacks: {
            label: (ctx) => `${ctx.dataset.label}: ${ctx.parsed.y.toFixed(2)}`,
          },
        },
      },
      scales: {
        x: { ticks: { color: "#8b93a7", maxTicksLimit: 8 }, grid: { display: false } },
        y: { ticks: { color: "#8b93a7" }, grid: { color: "#262b3622" } },
      },
    },
  });
}

function renderTickers(tickers) {
  const root = document.getElementById("tickers");
  tickers.forEach((t) => root.appendChild(renderTicker(t)));
}

function renderTicker(t) {
  const card = document.createElement("section");
  card.className = "card";

  if (t.error) {
    card.innerHTML = `<h2>${t.ticker} ${t.name}</h2><p>${t.error}</p>`;
    return card;
  }

  const today = t.past[t.past.length - 1];
  const todayPct = today && today.change_pct != null ? today.change_pct : 0;

  const realtimeHtml = t.realtime
    ? `<span class="realtime-tag">${
        t.realtime.market_open ? "장중" : "장마감"
      } ${t.realtime.traded_at || ""}</span>
       <span class="price-change ${cls(t.realtime.pct)}">${arrow(t.realtime.pct)} ${fmtPct(t.realtime.pct)}</span>`
    : "";

  card.innerHTML = `
    <div class="ticker-head">
      <div>
        <div class="ticker-name">${escapeHtml(t.name)}</div>
        <div class="ticker-meta">${t.ticker} · 종가 ${t.latest_date}</div>
      </div>
    </div>
    <div class="price-row">
      <span class="price-now">${fmtKrw(t.latest_price)}</span>
      <span class="price-change ${cls(todayPct)}">${arrow(todayPct)} ${fmtPct(todayPct)}</span>
      ${realtimeHtml}
    </div>

    <div class="section">
      <h3>가격 흐름 (최근 ${t.history.length}거래일)</h3>
      <div class="chart-wrap"><canvas id="chart-${t.ticker}"></canvas></div>
    </div>

    <div class="section">
      <h3>예상 (GBM 95% 구간)</h3>
      <div class="forecast-grid">
        ${t.forecast.map(renderForecastItem).join("")}
      </div>
    </div>

    <div class="section">
      <h3>특이사항</h3>
      <ul class="obs-list">
        ${t.observations.map((o) => `<li>${escapeHtml(o)}</li>`).join("")}
      </ul>
    </div>

    <div class="section">
      <h3>관련 뉴스 (최근 48시간)</h3>
      <ul class="news-list">
        ${t.news.map(renderNewsItem).join("")}
      </ul>
    </div>
  `;

  setTimeout(() => drawPriceChart(t), 0);
  return card;
}

function renderForecastItem(f) {
  const c = cls(f.center_pct);
  return `
    <div class="forecast-item">
      <div class="fi-label">${escapeHtml(f.label)} (${escapeHtml(f.date_short)})</div>
      <div class="fi-center">${fmtKrw(f.center)} <span class="${c}-text">${arrow(f.center_pct)} ${fmtPct(f.center_pct)}</span></div>
      <div class="fi-range">${fmtKrw(f.low)} ~ ${fmtKrw(f.high)}</div>
    </div>
  `;
}

function renderNewsItem(n) {
  const href = n.link ? `href="${escapeAttr(n.link)}" target="_blank" rel="noopener"` : "";
  const titleHtml = n.link
    ? `<a ${href}>${escapeHtml(n.title)}</a>`
    : escapeHtml(n.title);
  return `
    <li>
      <span class="news-meta">${escapeHtml(n.at)}</span>
      <span class="news-kw">${escapeHtml(n.kw)}</span>
      ${titleHtml}
    </li>
  `;
}

function drawPriceChart(t) {
  const labels = t.history.map((h) => h.date.slice(5));
  const data = t.history.map((h) => h.close);
  const last = data[data.length - 1];
  const first = data[0];
  const up = last >= first;
  const color = up ? UP : DOWN;

  new Chart(document.getElementById(`chart-${t.ticker}`), {
    type: "line",
    data: {
      labels,
      datasets: [
        {
          label: t.ticker,
          data,
          borderColor: color,
          backgroundColor: color + "18",
          fill: true,
          tension: 0.15,
          pointRadius: 0,
          borderWidth: 2,
        },
      ],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: { display: false },
        tooltip: {
          callbacks: {
            label: (ctx) => fmtKrw(ctx.parsed.y),
          },
        },
      },
      scales: {
        x: { ticks: { color: "#8b93a7", maxTicksLimit: 8 }, grid: { display: false } },
        y: {
          ticks: { color: "#8b93a7", callback: (v) => v.toLocaleString("ko-KR") },
          grid: { color: "#262b3622" },
        },
      },
    },
  });
}

function escapeHtml(s) {
  if (s == null) return "";
  return String(s)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
}
function escapeAttr(s) {
  return escapeHtml(s);
}

load();
