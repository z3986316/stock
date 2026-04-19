const UP = "#ef4444";
const DOWN = "#3b82f6";
const RANGES = [
  { key: "3M", days: 63, label: "3개월" },
  { key: "6M", days: 126, label: "6개월" },
  { key: "1Y", days: 252, label: "1년" },
];
const DEFAULT_RANGE = "1Y";
const OVERVIEW_RANGE_DAYS = 63; // 종합 탭의 종목별 미니 차트

const tickerCharts = {}; // { ticker: Chart } — detail charts
const tickerRange = {}; // { ticker: "3M" | "6M" | "1Y" }

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

  buildTabs(data.tickers);
  renderComparison(data.tickers);
  renderOverviewMinis(data.tickers);
  renderTickerPanes(data.tickers);
  activateTab("overview");
}

function buildTabs(tickers) {
  const nav = document.getElementById("tabs");
  const btns = [{ id: "overview", label: "종합" }].concat(
    tickers.map((t, i) => ({ id: `ticker-${i}`, label: t.name }))
  );
  nav.innerHTML = btns
    .map(
      (b) =>
        `<button class="tab" data-pane="${b.id}">${escapeHtml(b.label)}</button>`
    )
    .join("");
  nav.querySelectorAll(".tab").forEach((el) => {
    el.addEventListener("click", () => activateTab(el.dataset.pane));
  });
}

function activateTab(paneId) {
  document.querySelectorAll(".tab").forEach((el) => {
    el.classList.toggle("active", el.dataset.pane === paneId);
  });
  document.querySelectorAll(".pane").forEach((el) => {
    el.hidden = el.id !== `pane-${paneId}`;
  });
  window.scrollTo({ top: 0, behavior: "instant" });
}

function sliceHistory(history, days) {
  if (!history || history.length === 0) return [];
  if (days >= history.length) return history;
  return history.slice(history.length - days);
}

function renderComparison(tickers) {
  const valid = tickers.filter((t) => t.history && t.history.length > 0);
  if (valid.length === 0) return;

  const minLen = Math.min(...valid.map((t) => t.history.length));
  const slice = (arr) => arr.slice(arr.length - minLen);

  const labels = slice(valid[0].history).map((h) => h.date);
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
      pointHoverRadius: 5,
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
            label: (ctx) =>
              `${ctx.dataset.label}: ${ctx.parsed.y.toFixed(2)}`,
          },
        },
      },
      scales: {
        x: {
          ticks: {
            color: "#8b93a7",
            maxTicksLimit: 8,
            callback: function (v) {
              return this.getLabelForValue(v).slice(5);
            },
          },
          grid: { display: false },
        },
        y: { ticks: { color: "#8b93a7" }, grid: { color: "#262b3622" } },
      },
    },
  });
}

function renderOverviewMinis(tickers) {
  const root = document.getElementById("overview-minis");
  root.innerHTML = "";
  tickers.forEach((t) => {
    if (t.error) return;
    const card = document.createElement("section");
    card.className = "card";
    card.innerHTML = `
      <div class="ticker-head">
        <div class="ticker-name">${escapeHtml(t.name)}</div>
        <div class="ticker-meta">${t.ticker} · 최근 3개월</div>
      </div>
      <div class="chart-wrap mini"><canvas id="mini-${t.ticker}"></canvas></div>
    `;
    root.appendChild(card);
    setTimeout(() => drawMiniChart(t), 0);
  });
}

function drawMiniChart(t) {
  const hist = sliceHistory(t.history, OVERVIEW_RANGE_DAYS);
  const labels = hist.map((h) => h.date);
  const data = hist.map((h) => h.close);
  const up = data[data.length - 1] >= data[0];
  const color = up ? UP : DOWN;
  new Chart(document.getElementById(`mini-${t.ticker}`), {
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
          pointHoverRadius: 5,
          borderWidth: 2,
        },
      ],
    },
    options: chartOptions(false),
  });
}

function renderTickerPanes(tickers) {
  const root = document.getElementById("ticker-panes");
  root.innerHTML = "";
  tickers.forEach((t, i) => {
    const pane = document.createElement("div");
    pane.id = `pane-ticker-${i}`;
    pane.className = "pane";
    pane.hidden = true;
    pane.appendChild(buildTickerDetail(t));
    root.appendChild(pane);
    if (!t.error) setTimeout(() => drawDetailChart(t, DEFAULT_RANGE), 0);
  });
}

function buildTickerDetail(t) {
  const card = document.createElement("section");
  card.className = "card";

  if (t.error) {
    card.innerHTML = `<h2>${escapeHtml(t.ticker)} ${escapeHtml(t.name)}</h2><p>${escapeHtml(t.error)}</p>`;
    return card;
  }

  const today = t.past[t.past.length - 1];
  const todayPct = today && today.change_pct != null ? today.change_pct : 0;

  const realtimeHtml = t.realtime
    ? `<span class="realtime-tag">${
        t.realtime.market_open ? "장중" : "장마감"
      } ${escapeHtml(t.realtime.traded_at || "")}</span>
       <span class="price-change ${cls(t.realtime.pct)}">${arrow(t.realtime.pct)} ${fmtPct(t.realtime.pct)}</span>`
    : "";

  const rangeButtons = RANGES.map(
    (r) =>
      `<button class="range-btn ${r.key === DEFAULT_RANGE ? "active" : ""}" data-ticker="${t.ticker}" data-range="${r.key}">${r.label}</button>`
  ).join("");

  card.innerHTML = `
    <div class="ticker-head">
      <div class="ticker-name">${escapeHtml(t.name)}</div>
      <div class="ticker-meta">${t.ticker} · 종가 ${escapeHtml(t.latest_date)}</div>
    </div>
    <div class="price-row">
      <span class="price-now">${fmtKrw(t.latest_price)}</span>
      <span class="price-change ${cls(todayPct)}">${arrow(todayPct)} ${fmtPct(todayPct)}</span>
      ${realtimeHtml}
    </div>

    <div class="section">
      <h3>가격 흐름</h3>
      <div class="range-buttons">${rangeButtons}</div>
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

  card.querySelectorAll(".range-btn").forEach((btn) => {
    btn.addEventListener("click", () => {
      const ticker = btn.dataset.ticker;
      const range = btn.dataset.range;
      card.querySelectorAll(".range-btn").forEach((b) =>
        b.classList.toggle("active", b === btn)
      );
      drawDetailChart(t, range);
      tickerRange[ticker] = range;
    });
  });

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
  const titleHtml = n.link
    ? `<a href="${escapeAttr(n.link)}" target="_blank" rel="noopener">${escapeHtml(n.title)}</a>`
    : escapeHtml(n.title);
  return `
    <li>
      <span class="news-meta">${escapeHtml(n.at)}</span>
      <span class="news-kw">${escapeHtml(n.kw)}</span>
      ${titleHtml}
    </li>
  `;
}

function drawDetailChart(t, rangeKey) {
  const range = RANGES.find((r) => r.key === rangeKey) || RANGES[RANGES.length - 1];
  const hist = sliceHistory(t.history, range.days);
  const labels = hist.map((h) => h.date);
  const data = hist.map((h) => h.close);
  const up = data[data.length - 1] >= data[0];
  const color = up ? UP : DOWN;

  if (tickerCharts[t.ticker]) {
    const chart = tickerCharts[t.ticker];
    chart.data.labels = labels;
    chart.data.datasets[0].data = data;
    chart.data.datasets[0].borderColor = color;
    chart.data.datasets[0].backgroundColor = color + "18";
    chart.update();
    return;
  }

  tickerCharts[t.ticker] = new Chart(document.getElementById(`chart-${t.ticker}`), {
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
          pointHoverRadius: 5,
          borderWidth: 2,
        },
      ],
    },
    options: chartOptions(true),
  });
}

function chartOptions(currency) {
  return {
    responsive: true,
    maintainAspectRatio: false,
    interaction: { mode: "index", intersect: false },
    plugins: {
      legend: { display: false },
      tooltip: {
        callbacks: {
          label: (ctx) => (currency ? fmtKrw(ctx.parsed.y) : ctx.parsed.y.toLocaleString("ko-KR")),
        },
      },
    },
    scales: {
      x: {
        ticks: {
          color: "#8b93a7",
          maxTicksLimit: 8,
          callback: function (v) {
            return this.getLabelForValue(v).slice(5);
          },
        },
        grid: { display: false },
      },
      y: {
        ticks: { color: "#8b93a7", callback: (v) => v.toLocaleString("ko-KR") },
        grid: { color: "#262b3622" },
      },
    },
  };
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
