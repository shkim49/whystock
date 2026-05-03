const state = {
  events: [],
  selectedEventId: null,
  detail: null,
};

const nodes = {};

document.addEventListener("DOMContentLoaded", () => {
  [
    "runtimeBadge",
    "asOfText",
    "eventCount",
    "stockSearch",
    "searchResults",
    "moverList",
    "eventTitle",
    "eventSubtitle",
    "brandVisual",
    "currentPrice",
    "changeRate",
    "volumeChange",
    "dataBasis",
    "basisNote",
    "analyzeButton",
    "summaryText",
    "reasonList",
    "scenarioList",
    "sourceList",
    "relatedList",
    "termButtons",
    "termExplanation",
    "disclaimerText",
  ].forEach((id) => {
    nodes[id] = document.getElementById(id);
  });

  bindEvents();
  preferGeneratedPng();
  loadMovers();
});

function bindEvents() {
  nodes.analyzeButton.addEventListener("click", rerunAnalysis);
  nodes.stockSearch.addEventListener("input", debounce(searchStocks, 220));
}

function preferGeneratedPng() {
  const probe = new Image();
  probe.onload = () => {
    nodes.brandVisual.src = "/assets/generated/why-stock-hero.png";
  };
  probe.onerror = () => {};
  probe.src = `/assets/generated/why-stock-hero.png?probe=${Date.now()}`;
}

async function loadMovers() {
  setLoading("급등락 이벤트를 불러오는 중입니다.");
  const data = await fetchJson("/api/events/movers");
  state.events = data.events;
  nodes.asOfText.textContent = `기준 ${formatTime(data.as_of)}`;
  nodes.eventCount.textContent = String(data.events.length);
  renderMovers();

  if (state.events.length > 0) {
    await selectEvent(state.events[0].id);
  }
}

async function selectEvent(eventId) {
  state.selectedEventId = eventId;
  renderMovers();
  setLoading("근거 자료와 분석을 불러오는 중입니다.");
  state.detail = await fetchJson(`/api/events/${encodeURIComponent(eventId)}`);
  renderDetail();
}

async function selectStockBriefing(ticker) {
  state.selectedEventId = `briefing-${ticker}`;
  renderMovers();
  nodes.searchResults.innerHTML = "";
  setLoading("선택한 종목의 시세와 뉴스를 검색하는 중입니다.");
  state.detail = await fetchJson(`/api/stocks/${encodeURIComponent(ticker)}/briefing`);
  renderDetail();
}

function setLoading(message) {
  nodes.eventTitle.textContent = "불러오는 중";
  nodes.eventSubtitle.textContent = message;
  nodes.summaryText.textContent = "";
  nodes.reasonList.innerHTML = "";
  nodes.scenarioList.innerHTML = "";
  nodes.sourceList.innerHTML = "";
  nodes.relatedList.innerHTML = "";
  nodes.termButtons.innerHTML = "";
  nodes.termExplanation.textContent = "잠시만 기다려 주세요.";
}

function renderMovers() {
  nodes.moverList.innerHTML = "";
  state.events.forEach((event) => {
    const button = document.createElement("button");
    button.type = "button";
    button.className = "mover-item";
    button.setAttribute("aria-current", event.id === state.selectedEventId ? "true" : "false");
    button.addEventListener("click", () => selectEvent(event.id));

    const changeClass = event.change_rate >= 0 ? "up" : "down";
    button.innerHTML = `
      <div class="mover-top">
        <span class="mover-name">
          <strong>${escapeHtml(event.stock_name)}</strong>
          <span>${escapeHtml(event.ticker)} · ${escapeHtml(event.sector)}</span>
        </span>
        <span class="pct ${changeClass}">${formatPercent(event.change_rate)}</span>
      </div>
      <div class="mover-summary">${escapeHtml(event.summary || "실제 시세 기준 이벤트입니다.")}</div>
    `;
    nodes.moverList.appendChild(button);
  });
}

function renderDetail() {
  const { event, stock, analysis, sources, related_stocks: relatedStocks, data_basis: dataBasis, terms } = state.detail;
  const changeClass = Number(event.change_rate) >= 0 ? "up" : "down";
  const modeLabel = event.event_type === "surge" ? "상승 이유" : event.event_type === "drop" ? "하락 이유" : "시장 브리핑";

  nodes.runtimeBadge.textContent = analysis?.generated_by || "analysis pending";
  nodes.eventTitle.textContent = `${stock.name} ${modeLabel}`;
  nodes.eventSubtitle.textContent = `${stock.ticker} · ${stock.market} · ${stock.sector} · ${formatTime(
    event.detected_at,
  )} 기준`;
  nodes.currentPrice.textContent = formatPrice(event.current_price);
  nodes.changeRate.textContent = formatPercent(event.change_rate);
  nodes.changeRate.className = changeClass;
  nodes.volumeChange.textContent = formatPercent(event.volume_change_rate);
  nodes.dataBasis.textContent = dataBasis?.label || `${sources.length}건`;
  nodes.basisNote.textContent =
    dataBasis?.note ||
    "신뢰점수는 임의 산식이 될 수 있어 제거했고, 실제 시세 출처와 근거 링크를 기준으로 보여줍니다.";
  nodes.summaryText.textContent = analysis?.summary || "아직 분석 결과가 없습니다.";
  nodes.disclaimerText.textContent = analysis?.disclaimer || "투자 추천이 아닌 정보 요약입니다.";

  renderReasons(analysis?.reasons || [], sources);
  renderScenarios(analysis?.scenarios || []);
  renderSources(sources);
  renderRelated(relatedStocks || []);
  renderTerms(terms || []);
}

function renderReasons(reasons, sources) {
  const sourceMap = new Map(sources.map((source) => [source.id, source]));
  nodes.reasonList.innerHTML = "";

  if (reasons.length === 0) {
    nodes.reasonList.innerHTML = `<div class="empty">분석 결과가 없습니다.</div>`;
    return;
  }

  reasons.forEach((reason) => {
    const item = document.createElement("li");
    item.className = "reason-card";
    const chips = (reason.evidence_source_ids || [])
      .map((id) => {
        const source = sourceMap.get(id);
        if (!source) return "";
        return `<span class="chip">${escapeHtml(source.source_type_label || source.source_type)} #${source.id}</span>`;
      })
      .join("");

    item.innerHTML = `
      <h4>${escapeHtml(reason.title)}</h4>
      <p>${escapeHtml(reason.explanation)}</p>
      <div class="evidence-chips">${chips}</div>
    `;
    nodes.reasonList.appendChild(item);
  });
}

function renderScenarios(scenarios) {
  nodes.scenarioList.innerHTML = "";
  if (scenarios.length === 0) {
    nodes.scenarioList.innerHTML = `<div class="empty">시나리오가 없습니다.</div>`;
    return;
  }

  scenarios.forEach((scenario) => {
    const card = document.createElement("div");
    card.className = "scenario";
    card.innerHTML = `
      <strong>${escapeHtml(scenario.title)}</strong>
      <p>${escapeHtml(scenario.condition)}</p>
    `;
    nodes.scenarioList.appendChild(card);
  });
}

function renderSources(sources) {
  nodes.sourceList.innerHTML = "";
  sources.forEach((source) => {
    const item = document.createElement("a");
    item.className = "source source-link";
    item.href = source.url;
    item.target = "_blank";
    item.rel = "noopener noreferrer";
    item.innerHTML = `
      <strong>#${source.id} ${escapeHtml(source.title)}</strong>
      <p>${escapeHtml(source.excerpt)}</p>
      <div class="source-meta">
        <span>${escapeHtml(source.publisher)}</span>
        <span>${escapeHtml(source.source_type_label || source.source_type)}</span>
        <span>${escapeHtml(formatTime(source.published_at))}</span>
      </div>
    `;
    nodes.sourceList.appendChild(item);
  });
}

function renderRelated(relatedStocks) {
  nodes.relatedList.innerHTML = "";
  if (relatedStocks.length === 0) {
    nodes.relatedList.innerHTML = `<div class="empty">관련 종목이 없습니다.</div>`;
    return;
  }

  relatedStocks.forEach((stock) => {
    const item = document.createElement("button");
    item.type = "button";
    item.className = "related related-button";
    item.addEventListener("click", () => selectStockBriefing(stock.ticker));
    item.innerHTML = `
      <strong>${escapeHtml(stock.name)} <span class="chip">${escapeHtml(stock.ticker)}</span></strong>
      <p>${escapeHtml(stock.reason)}</p>
    `;
    nodes.relatedList.appendChild(item);
  });
}

function renderTerms(terms) {
  nodes.termButtons.innerHTML = "";
  if (terms.length === 0) {
    nodes.termExplanation.textContent = "감지된 용어가 없습니다.";
    return;
  }

  terms.forEach((item, index) => {
    const button = document.createElement("button");
    button.type = "button";
    button.textContent = item.term;
    button.addEventListener("click", () => {
      nodes.termExplanation.textContent = `${item.term}: ${item.explanation}`;
    });
    nodes.termButtons.appendChild(button);
    if (index === 0) {
      nodes.termExplanation.textContent = `${item.term}: ${item.explanation}`;
    }
  });
}

async function rerunAnalysis() {
  if (!state.selectedEventId) return;
  nodes.analyzeButton.disabled = true;
  try {
    state.detail = await fetchJson(`/api/events/${encodeURIComponent(state.selectedEventId)}/analyze`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ refresh: true }),
    });
    renderDetail();
  } finally {
    nodes.analyzeButton.disabled = false;
  }
}

async function searchStocks() {
  const query = nodes.stockSearch.value.trim();
  if (!query) {
    nodes.searchResults.innerHTML = "";
    return;
  }

  nodes.searchResults.innerHTML = `<div class="empty">검색 중...</div>`;
  const data = await fetchJson(`/api/stocks/search?query=${encodeURIComponent(query)}`);
  nodes.searchResults.innerHTML = "";

  if (data.stocks.length === 0) {
    nodes.searchResults.innerHTML = `<div class="empty">검색 결과 없음</div>`;
    return;
  }

  data.stocks.forEach((stock) => {
    const match = state.events.find((event) => event.ticker === stock.ticker);
    const button = document.createElement("button");
    button.type = "button";
    button.className = "search-result";
    button.innerHTML = `
      <strong>${escapeHtml(stock.name)} · ${escapeHtml(stock.ticker)}</strong>
      <span>${escapeHtml(stock.market)} · ${escapeHtml(stock.sector)} · ${match ? "급등락 이벤트" : "종목 브리핑"}</span>
    `;
    button.addEventListener("click", () => {
      nodes.stockSearch.value = stock.name;
      if (match) {
        selectEvent(match.id);
      } else {
        selectStockBriefing(stock.ticker);
      }
    });
    nodes.searchResults.appendChild(button);
  });
}

async function fetchJson(url, options = {}) {
  const response = await fetch(url, options);
  if (!response.ok) {
    throw new Error(`Request failed: ${response.status}`);
  }
  return response.json();
}

function debounce(callback, delay) {
  let timer = 0;
  return (...args) => {
    window.clearTimeout(timer);
    timer = window.setTimeout(() => callback(...args), delay);
  };
}

function formatPercent(value) {
  if (value === null || value === undefined || Number.isNaN(Number(value))) {
    return "확인 불가";
  }
  return `${Number(value) >= 0 ? "+" : ""}${Number(value).toFixed(2)}%`;
}

function formatPrice(value) {
  if (value === null || value === undefined || Number.isNaN(Number(value))) {
    return "확인 불가";
  }
  return `${Number(value).toLocaleString("ko-KR")}원`;
}

function formatTime(value) {
  if (!value) return "-";
  try {
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) return value;
    return new Intl.DateTimeFormat("ko-KR", {
      month: "2-digit",
      day: "2-digit",
      hour: "2-digit",
      minute: "2-digit",
    }).format(date);
  } catch {
    return value;
  }
}

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}
