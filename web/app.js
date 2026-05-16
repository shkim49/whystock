const state = {
  categories: [],
  allEvents: [],
  selectedEventId: null,
  detail: null,
  watchlist: [],
};

const MOVERS_REFRESH_INTERVAL_MS = 30 * 60 * 1000;
const LIVE_DETAIL_REFRESH_INTERVAL_MS = 60 * 1000;
const WATCHLIST_KEY = "whystock.watchlist";
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
    "watchButton",
    "summaryText",
    "reasonList",
    "materialTagList",
    "newsTimelineList",
    "watchlistList",
    "sourceList",
    "relatedList",
    "termButtons",
    "termExplanation",
    "disclaimerText",
  ].forEach((id) => {
    nodes[id] = document.getElementById(id);
  });

  bindEvents();
  loadWatchlist();
  preferGeneratedPng();
  loadMovers({ forceRefresh: true }).catch((error) => {
    console.error("Failed to load mover events", error);
    showError("이벤트 정보를 가져오지 못했습니다. 잠시 후 다시 시도해 주세요.");
  });
  setInterval(() => {
    loadMovers({ preserveSelection: true, silent: true }).catch((error) => {
      console.error("Failed to refresh mover events", error);
    });
  }, MOVERS_REFRESH_INTERVAL_MS);
  setInterval(() => {
    refreshSelectedDetail().catch((error) => {
      console.error("Failed to refresh selected detail", error);
    });
  }, LIVE_DETAIL_REFRESH_INTERVAL_MS);
});

function bindEvents() {
  nodes.analyzeButton.addEventListener("click", rerunAnalysis);
  nodes.watchButton.addEventListener("click", toggleCurrentWatch);
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

async function loadMovers(options = {}) {
  if (!options.silent) {
    setLoading("급등락 이벤트를 불러오는 중입니다.");
  }
  const previousEventId = state.selectedEventId;
  const refresh = options.forceRefresh ? "?refresh=1" : "";
  const data = await fetchJson(`/api/events/movers${refresh}`);
  state.categories = data.categories || [];
  state.allEvents = data.events || state.categories.flatMap((category) => category.events || []);
  nodes.asOfText.textContent = `기준 ${formatTime(data.as_of)}`;
  nodes.eventCount.textContent = String(state.allEvents.length);
  renderMovers();

  if (state.allEvents.length === 0) {
    return;
  }

  if (options.preserveSelection && previousEventId?.startsWith("briefing-")) {
    return;
  }

  const selectedStillExists = state.allEvents.some((event) => event.id === previousEventId);
  if (options.preserveSelection && selectedStillExists) {
    await selectEvent(previousEventId);
  } else if (options.preserveSelection && state.allEvents[0]) {
    await selectEvent(state.allEvents[0].id);
  } else if (!options.preserveSelection) {
    await selectEvent(state.allEvents[0].id);
  }
}

async function selectEvent(eventId) {
  state.selectedEventId = eventId;
  renderMovers();
  setLoading("근거 자료와 분석을 불러오는 중입니다.");
  try {
    state.detail = await fetchJson(`/api/events/${encodeURIComponent(eventId)}`);
    renderDetail();
  } catch (error) {
    console.error("Failed to load event detail", error);
    showError("상세 분석을 불러오지 못했습니다. 잠시 후 다시 시도해 주세요.");
  }
}

async function selectStockBriefing(ticker) {
  state.selectedEventId = `briefing-${ticker}`;
  renderMovers();
  nodes.searchResults.innerHTML = "";
  setLoading("선택한 종목의 시세와 뉴스를 검색하는 중입니다.");
  try {
    state.detail = await fetchJson(`/api/stocks/${encodeURIComponent(ticker)}/briefing`);
    renderDetail();
  } catch (error) {
    console.error("Failed to load stock briefing", error);
    showError("종목 브리핑을 불러오지 못했습니다. 잠시 후 다시 시도해 주세요.");
  }
}

function setLoading(message) {
  nodes.eventTitle.textContent = "불러오는 중";
  nodes.eventSubtitle.textContent = message;
  resetDetailState();
}

function resetDetailState() {
  nodes.basisNote.textContent = "";
  nodes.basisNote.hidden = true;
  nodes.currentPrice.textContent = "-";
  nodes.changeRate.textContent = "-";
  nodes.changeRate.className = "";
  nodes.volumeChange.textContent = "-";
  nodes.dataBasis.textContent = "-";
  nodes.summaryText.textContent = "";
  nodes.reasonList.innerHTML = "";
  nodes.materialTagList.innerHTML = "";
  nodes.newsTimelineList.innerHTML = "";
  nodes.watchlistList.innerHTML = "";
  nodes.sourceList.innerHTML = "";
  nodes.relatedList.innerHTML = "";
  nodes.termButtons.innerHTML = "";
  nodes.termExplanation.textContent = "잠시만 기다려 주세요.";
}

function showError(message) {
  nodes.eventTitle.textContent = "정보를 불러오지 못했습니다.";
  nodes.eventSubtitle.textContent = message;
  nodes.runtimeBadge.textContent = "request failed";
  resetDetailState();
  nodes.termExplanation.textContent = "잠시 후 다시 시도해 주세요.";
}

function renderMovers() {
  nodes.moverList.innerHTML = "";
  state.categories.forEach((category) => {
    const section = document.createElement("section");
    section.className = "mover-category";
    const items = category.events || [];
    const buttons = items
      .map((event) => {
        const changeClass = event.change_rate >= 0 ? "up" : "down";
        return `
          <button
            type="button"
            class="mover-item"
            aria-current="${event.id === state.selectedEventId ? "true" : "false"}"
            data-event-id="${escapeHtml(event.id)}"
          >
            <div class="mover-top">
              <span class="mover-name">
                <strong>${escapeHtml(event.stock_name)}</strong>
                <span>${escapeHtml(event.ticker)} · ${escapeHtml(event.sector)}</span>
              </span>
              <span class="pct ${changeClass}">${formatPercent(event.change_rate)}</span>
            </div>
            <div class="mover-summary">${escapeHtml(event.summary || "실제 시세 기준 이벤트입니다.")}</div>
          </button>
        `;
      })
      .join("");

    section.innerHTML = `
      <div class="mover-category-head">
        <strong>${escapeHtml(category.label)}</strong>
        <span>${items.length}개</span>
      </div>
      <p class="mover-category-note">${escapeHtml(category.description || "")}</p>
      <div class="mover-category-list">${buttons || '<div class="empty">표시할 종목이 없습니다.</div>'}</div>
    `;
    nodes.moverList.appendChild(section);
  });

  nodes.moverList.querySelectorAll("[data-event-id]").forEach((button) => {
    button.addEventListener("click", () => selectEvent(button.getAttribute("data-event-id")));
  });
}

function renderDetail() {
  const {
    event,
    stock,
    analysis,
    sources,
    related_stocks: relatedStocks,
    data_basis: dataBasis,
    news_timeline: newsTimeline,
    material_tags: materialTags,
    terms,
  } = state.detail;
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
  const basisNote = dataBasis?.note || "";
  nodes.basisNote.textContent = basisNote;
  nodes.basisNote.hidden = !basisNote;
  nodes.summaryText.textContent = analysis?.summary || "아직 분석 결과가 없습니다.";
  nodes.disclaimerText.textContent = analysis?.disclaimer || "투자 추천이 아닌 정보 요약입니다.";
  renderWatchButton(stock);

  renderReasons(analysis?.reasons || [], sources);
  renderMaterialTags(materialTags || []);
  renderNewsTimeline(newsTimeline || []);
  renderWatchlist();
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

function renderMaterialTags(tags) {
  nodes.materialTagList.innerHTML = "";
  if (tags.length === 0) {
    nodes.materialTagList.innerHTML = `<div class="empty">감지된 재료가 없습니다.</div>`;
    return;
  }

  tags.forEach((tag) => {
    const item = document.createElement("div");
    item.className = "material-tag";
    item.innerHTML = `
      <strong>${escapeHtml(tag.label)}</strong>
      <p>${escapeHtml(tag.description)}</p>
    `;
    nodes.materialTagList.appendChild(item);
  });
}

function renderNewsTimeline(items) {
  nodes.newsTimelineList.innerHTML = "";
  if (items.length === 0) {
    nodes.newsTimelineList.innerHTML = `<div class="empty">관련 뉴스가 없습니다.</div>`;
    return;
  }

  items.forEach((news) => {
    const item = document.createElement("a");
    item.className = "timeline-item";
    item.href = news.url;
    item.target = "_blank";
    item.rel = "noopener noreferrer";
    item.innerHTML = `
      <span>${escapeHtml(formatTime(news.published_at))} · ${escapeHtml(news.publisher)}</span>
      <strong>${escapeHtml(news.title)}</strong>
      <p>${escapeHtml(news.summary)}</p>
    `;
    nodes.newsTimelineList.appendChild(item);
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
      ${stock.theme ? `<div class="related-theme">${escapeHtml(stock.theme)}</div>` : ""}
      <p>${escapeHtml(stock.reason)}</p>
    `;
    nodes.relatedList.appendChild(item);
  });
}

function loadWatchlist() {
  try {
    state.watchlist = JSON.parse(localStorage.getItem(WATCHLIST_KEY) || "[]");
  } catch {
    state.watchlist = [];
  }
  renderWatchlist();
}

function saveWatchlist() {
  localStorage.setItem(WATCHLIST_KEY, JSON.stringify(state.watchlist));
}

function toggleCurrentWatch() {
  const stock = state.detail?.stock;
  if (!stock) return;
  const exists = state.watchlist.some((item) => item.ticker === stock.ticker);
  if (exists) {
    state.watchlist = state.watchlist.filter((item) => item.ticker !== stock.ticker);
  } else {
    state.watchlist.unshift({
      ticker: stock.ticker,
      name: stock.name,
      market: stock.market,
      sector: stock.sector,
    });
  }
  state.watchlist = state.watchlist.slice(0, 8);
  saveWatchlist();
  renderWatchButton(stock);
  renderWatchlist();
}

function renderWatchButton(stock) {
  const watched = state.watchlist.some((item) => item.ticker === stock.ticker);
  nodes.watchButton.setAttribute("aria-pressed", watched ? "true" : "false");
  nodes.watchButton.title = watched ? "관심종목 제거" : "관심종목 저장";
}

function renderWatchlist() {
  if (!nodes.watchlistList) return;
  nodes.watchlistList.innerHTML = "";
  if (state.watchlist.length === 0) {
    nodes.watchlistList.innerHTML = `<div class="empty">저장된 종목이 없습니다.</div>`;
    return;
  }
  state.watchlist.forEach((stock) => {
    const item = document.createElement("button");
    item.type = "button";
    item.className = "watch-item";
    item.innerHTML = `
      <strong>${escapeHtml(stock.name)} <span>${escapeHtml(stock.ticker)}</span></strong>
      <p>${escapeHtml(stock.market)} · ${escapeHtml(stock.sector)}</p>
    `;
    item.addEventListener("click", () => selectStockBriefing(stock.ticker));
    nodes.watchlistList.appendChild(item);
  });
}

function renderTerms(terms) {
  nodes.termButtons.innerHTML = "";
  if (terms.length === 0) {
    nodes.termExplanation.textContent = "설명할 용어가 없습니다.";
    return;
  }

  const buildTermDetail = (item) => {
    if (item.definition || item.why_it_matters) {
      return [item.definition, item.why_it_matters].filter(Boolean).join(" ");
    }
    return item.explanation || "";
  };

  terms.forEach((item, index) => {
    const button = document.createElement("button");
    button.type = "button";
    button.textContent = item.term;
    button.addEventListener("click", () => {
      const detail = buildTermDetail(item);
      nodes.termExplanation.textContent = `${item.term}: ${detail}`;
    });
    nodes.termButtons.appendChild(button);
    if (index === 0) {
      const detail = buildTermDetail(item);
      nodes.termExplanation.textContent = `${item.term}: ${detail}`;
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
  } catch (error) {
    console.error("Failed to rerun analysis", error);
    showError("분석을 다시 실행하지 못했습니다. 잠시 후 다시 시도해 주세요.");
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
    const match = state.allEvents.find((event) => event.ticker === stock.ticker);
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

async function refreshSelectedDetail() {
  if (!state.selectedEventId) return;
  if (state.selectedEventId.startsWith("briefing-")) {
    const ticker = state.selectedEventId.replace("briefing-", "");
    state.detail = await fetchJson(`/api/stocks/${encodeURIComponent(ticker)}/briefing`);
    renderDetail();
    return;
  }
  state.detail = await fetchJson(`/api/events/${encodeURIComponent(state.selectedEventId)}`);
  renderDetail();
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
