const state = {
  categories: [],
  allEvents: [],
  selectedEventId: null,
  detail: null,
  watchlist: [],
  presentationOpen: false,
  presentationStep: 0,
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
    "assistantForm",
    "assistantInput",
    "assistantSubmit",
    "assistantAnswer",
    "presentationButton",
    "presentationOverlay",
    "presentationClose",
    "presentationCounter",
    "presentationStepLabel",
    "presentationStage",
    "presentationPrev",
    "presentationNext",
    "presentationDots",
    "moverList",
    "eventTitle",
    "eventSubtitle",
    "currentPrice",
    "changeRate",
    "volumeChange",
    "dataBasis",
    "basisNote",
    "analyzeButton",
    "watchButton",
    "summaryText",
    "reasonList",
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
  nodes.assistantForm.addEventListener("submit", submitAssistantQuestion);
  nodes.presentationButton.addEventListener("click", openPresentationMode);
  nodes.presentationClose.addEventListener("click", closePresentationMode);
  nodes.presentationPrev.addEventListener("click", () => setPresentationStep(state.presentationStep - 1));
  nodes.presentationNext.addEventListener("click", () => setPresentationStep(state.presentationStep + 1));
  document.addEventListener("keydown", handlePresentationKeydown);
  window.addEventListener("resize", () => {
    if (state.presentationOpen) {
      renderPresentation();
    }
  });
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
  renderNewsTimeline(newsTimeline || []);
  renderWatchlist();
  renderSources(sources);
  renderRelated(relatedStocks || []);
  renderTerms(terms || []);
  if (state.presentationOpen) {
    renderPresentation();
  }
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

function openPresentationMode() {
  state.presentationOpen = true;
  state.presentationStep = 0;
  nodes.presentationOverlay.hidden = false;
  document.body.classList.add("presentation-active");
  renderPresentation();
}

function closePresentationMode() {
  state.presentationOpen = false;
  nodes.presentationOverlay.hidden = true;
  document.body.classList.remove("presentation-active");
}

function setPresentationStep(step) {
  const steps = buildPresentationSteps();
  state.presentationStep = Math.min(Math.max(step, 0), steps.length - 1);
  renderPresentation();
}

function handlePresentationKeydown(event) {
  if (!state.presentationOpen) return;
  if (event.key === "Escape") {
    closePresentationMode();
    return;
  }
  if (event.key === "ArrowRight" || event.key === " ") {
    event.preventDefault();
    setPresentationStep(state.presentationStep + 1);
    return;
  }
  if (event.key === "ArrowLeft") {
    event.preventDefault();
    setPresentationStep(state.presentationStep - 1);
  }
}

function renderPresentation() {
  const steps = buildPresentationSteps();
  const currentStep = steps[state.presentationStep] || steps[0];
  nodes.presentationCounter.textContent = `${state.presentationStep + 1} / ${steps.length}`;
  nodes.presentationStepLabel.textContent = currentStep.label;
  nodes.presentationStage.innerHTML = currentStep.html;
  nodes.presentationPrev.disabled = state.presentationStep === 0;
  nodes.presentationNext.disabled = state.presentationStep === steps.length - 1;
  nodes.presentationDots.innerHTML = steps
    .map(
      (_, index) => `
        <button
          type="button"
          aria-label="${index + 1}단계"
          aria-current="${index === state.presentationStep ? "true" : "false"}"
          data-presentation-step="${index}"
        ></button>
      `,
    )
    .join("");
  nodes.presentationDots.querySelectorAll("[data-presentation-step]").forEach((button) => {
    button.addEventListener("click", () => setPresentationStep(Number(button.dataset.presentationStep)));
  });
  nodes.presentationStage.querySelectorAll("[data-presentation-ticker]").forEach((button) => {
    button.addEventListener("click", () => {
      closePresentationMode();
      selectStockBriefing(button.dataset.presentationTicker);
    });
  });
}

function buildPresentationSteps() {
  if (!state.detail) {
    return [
      {
        label: "준비",
        html: `
          <article class="presentation-slide presentation-empty-slide">
            <p class="presentation-kicker">WhyStock briefing</p>
            <h2>먼저 종목을 선택해 주세요</h2>
            <p>왼쪽 목록에서 종목을 고르거나 채팅창에 종목명 또는 코드를 입력하면 발표 모드가 해당 브리핑을 단계별로 정리합니다.</p>
          </article>
        `,
      },
    ];
  }

  const detail = state.detail;
  const event = detail.event || {};
  const stock = detail.stock || {};
  const analysis = detail.analysis || {};
  const sources = detail.sources || [];
  const newsTimeline = detail.news_timeline || [];
  const relatedStocks = detail.related_stocks || [];
  const terms = detail.terms || [];
  const reasons = analysis.reasons || [];
  const changeClass = Number(event.change_rate) >= 0 ? "up" : "down";
  const title = `${stock.name || "-"} 브리핑`;

  return [
    {
      label: "한눈에 보기",
      html: `
        <article class="presentation-slide">
          <p class="presentation-kicker">${escapeHtml(stock.market || "Stock")} · ${escapeHtml(stock.ticker || "-")}</p>
          <h2>${escapeHtml(title)}</h2>
          <div class="presentation-metrics">
            <div><span>현재가</span><strong>${escapeHtml(formatPrice(event.current_price))}</strong></div>
            <div><span>변동률</span><strong class="${changeClass}">${escapeHtml(formatPercent(event.change_rate))}</strong></div>
            <div><span>거래량 변화</span><strong>${escapeHtml(formatPercent(event.volume_change_rate))}</strong></div>
          </div>
          <p class="presentation-summary">${escapeHtml(analysis.summary || "아직 분석 요약이 없습니다.")}</p>
        </article>
      `,
    },
    {
      label: "가격 반응",
      html: `
        <article class="presentation-slide">
          <p class="presentation-kicker">Price action</p>
          <h2>가격과 거래량이 먼저 보여주는 신호</h2>
          <div class="presentation-split">
            <div class="presentation-focus ${changeClass}">
              <span>등락률</span>
              <strong>${escapeHtml(formatPercent(event.change_rate))}</strong>
            </div>
            <div class="presentation-facts">
              <div><span>거래량 변화</span><strong>${escapeHtml(formatPercent(event.volume_change_rate))}</strong></div>
              <div><span>자료 기준</span><strong>${escapeHtml(detail.data_basis?.label || `${sources.length}건`)}</strong></div>
              <div><span>감지 시각</span><strong>${escapeHtml(formatTime(event.detected_at))}</strong></div>
            </div>
          </div>
          <p class="presentation-note">${escapeHtml(detail.data_basis?.note || "가격, 거래량, 뉴스, 공시 자료를 함께 확인해 해석합니다.")}</p>
        </article>
      `,
    },
    {
      label: "원인 정리",
      html: `
        <article class="presentation-slide">
          <p class="presentation-kicker">Why it moved</p>
          <h2>핵심 원인 후보</h2>
          ${presentationReasonList(reasons)}
        </article>
      `,
    },
    {
      label: "근거 자료",
      html: `
        <article class="presentation-slide">
          <p class="presentation-kicker">Evidence</p>
          <h2>확인한 뉴스와 공시</h2>
          <div class="presentation-two-column">
            <div>
              <h3>근거 자료</h3>
              ${presentationSourceList(sources)}
            </div>
            <div>
              <h3>뉴스 흐름</h3>
              ${presentationNewsList(newsTimeline)}
            </div>
          </div>
        </article>
      `,
    },
    {
      label: "함께 볼 것",
      html: `
        <article class="presentation-slide">
          <p class="presentation-kicker">Next checks</p>
          <h2>관련 종목과 용어</h2>
          <div class="presentation-two-column">
            <div>
              <h3>관련 종목</h3>
              ${presentationRelatedList(relatedStocks)}
            </div>
            <div>
              <h3>감지된 용어</h3>
              ${presentationTermList(terms)}
            </div>
          </div>
        </article>
      `,
    },
  ];
}

function presentationReasonList(reasons) {
  const items = reasons.slice(0, 4);
  if (items.length === 0) {
    return `<div class="presentation-empty-card">분석된 원인 후보가 없습니다.</div>`;
  }
  return `
    <ol class="presentation-card-list">
      ${items
        .map(
          (reason) => `
            <li>
              <strong>${escapeHtml(reason.title)}</strong>
              <p>${escapeHtml(reason.explanation)}</p>
            </li>
          `,
        )
        .join("")}
    </ol>
  `;
}

function presentationSourceList(sources) {
  const items = sources.slice(0, 4);
  if (items.length === 0) {
    return `<div class="presentation-empty-card">표시할 근거 자료가 없습니다.</div>`;
  }
  return `
    <div class="presentation-card-stack">
      ${items
        .map(
          (source) => `
            <div>
              <strong>#${source.id} ${escapeHtml(source.title)}</strong>
              <p>${escapeHtml(source.publisher)} · ${escapeHtml(formatTime(source.published_at))}</p>
            </div>
          `,
        )
        .join("")}
    </div>
  `;
}

function presentationNewsList(newsTimeline) {
  const items = newsTimeline.slice(0, 4);
  if (items.length === 0) {
    return `<div class="presentation-empty-card">표시할 뉴스 흐름이 없습니다.</div>`;
  }
  return `
    <div class="presentation-card-stack">
      ${items
        .map(
          (news) => `
            <div>
              <strong>${escapeHtml(news.title)}</strong>
              <p>${escapeHtml(news.publisher)} · ${escapeHtml(formatTime(news.published_at))}</p>
            </div>
          `,
        )
        .join("")}
    </div>
  `;
}

function presentationRelatedList(relatedStocks) {
  const items = relatedStocks.slice(0, 4);
  if (items.length === 0) {
    return `<div class="presentation-empty-card">관련 종목이 없습니다.</div>`;
  }
  return `
    <div class="presentation-card-stack">
      ${items
        .map(
          (stock) => `
            <button type="button" data-presentation-ticker="${escapeHtml(stock.ticker)}">
              <strong>${escapeHtml(stock.name)} <span>${escapeHtml(stock.ticker)}</span></strong>
              <p>${escapeHtml(stock.reason || stock.theme || "")}</p>
            </button>
          `,
        )
        .join("")}
    </div>
  `;
}

function presentationTermList(terms) {
  const items = terms.slice(0, 5);
  if (items.length === 0) {
    return `<div class="presentation-empty-card">감지된 용어가 없습니다.</div>`;
  }
  return `
    <div class="presentation-card-stack">
      ${items
        .map((item) => {
          const detail = [item.definition, item.why_it_matters, item.explanation].filter(Boolean).join(" ");
          return `
            <div>
              <strong>${escapeHtml(item.term)}</strong>
              <p>${escapeHtml(detail)}</p>
            </div>
          `;
        })
        .join("")}
    </div>
  `;
}

function openPresentationMode() {
  state.presentationOpen = true;
  state.presentationStep = 0;
  nodes.presentationStage.dataset.presentationKey = "";
  nodes.presentationOverlay.hidden = false;
  document.body.classList.add("presentation-active");
  renderPresentation();
}

function setPresentationStep(step) {
  const { steps } = buildPresentationModel();
  state.presentationStep = Math.min(Math.max(step, 0), steps.length - 1);
  renderPresentation();
}

function renderPresentation() {
  const model = buildPresentationModel();
  const steps = model.steps;
  const currentStep = steps[state.presentationStep] || steps[0];
  nodes.presentationCounter.textContent = `${state.presentationStep + 1} / ${steps.length}`;
  nodes.presentationStepLabel.textContent = currentStep.label;

  if (nodes.presentationStage.dataset.presentationKey !== model.key) {
    nodes.presentationStage.innerHTML = model.html;
    nodes.presentationStage.dataset.presentationKey = model.key;
  }

  nodes.presentationPrev.disabled = state.presentationStep === 0;
  nodes.presentationNext.disabled = state.presentationStep === steps.length - 1;
  nodes.presentationDots.innerHTML = steps
    .map(
      (_, index) => `
        <button
          type="button"
          aria-label="${index + 1}단계"
          aria-current="${index === state.presentationStep ? "true" : "false"}"
          data-presentation-step="${index}"
        ></button>
      `,
    )
    .join("");

  nodes.presentationDots.querySelectorAll("[data-presentation-step]").forEach((button) => {
    button.addEventListener("click", () => setPresentationStep(Number(button.dataset.presentationStep)));
  });
  nodes.presentationStage.querySelectorAll("[data-presentation-card]").forEach((card) => {
    card.classList.toggle("is-active", card.dataset.presentationCard === String(currentStep.card));
  });
  nodes.presentationStage.querySelectorAll("[data-presentation-ticker]").forEach((button) => {
    button.addEventListener("click", () => {
      closePresentationMode();
      selectStockBriefing(button.dataset.presentationTicker);
    });
  });

  applyPresentationTransform(currentStep.view);
}

function applyPresentationTransform(view) {
  const viewport = nodes.presentationStage.querySelector(".presentation-viewport");
  const canvas = nodes.presentationStage.querySelector(".presentation-canvas");
  if (!viewport || !canvas) return;

  const rect = viewport.getBoundingClientRect();
  const scale = rect.width < 760 ? view.mobileScale || Math.min(view.scale, 0.52) : view.scale;
  const x = rect.width / 2 - view.x * scale;
  const y = rect.height / 2 - view.y * scale;

  canvas.style.transform = `translate3d(${x}px, ${y}px, 0) scale(${scale})`;
}

function buildPresentationModel() {
  if (!state.detail) {
    return {
      key: "empty",
      steps: [
        {
          label: "준비",
          card: 0,
          view: { x: 430, y: 280, scale: 0.95, mobileScale: 0.5 },
        },
      ],
      html: `
        <div class="presentation-viewport">
          <div class="presentation-canvas presentation-canvas-empty">
            <article class="presentation-card presentation-card-empty" data-presentation-card="0" style="left: 80px; top: 80px; width: 700px;">
              <span class="presentation-node-index">00</span>
              <p class="presentation-kicker">WhyStock briefing</p>
              <h2>먼저 종목을 선택해 주세요</h2>
              <p class="presentation-summary">왼쪽 목록에서 종목을 고르거나 채팅창에 종목명 또는 코드를 입력하면 발표 모드가 해당 브리핑을 큰 화면 이동 방식으로 정리합니다.</p>
            </article>
          </div>
        </div>
      `,
    };
  }

  const detail = state.detail;
  const event = detail.event || {};
  const stock = detail.stock || {};
  const analysis = detail.analysis || {};
  const sources = detail.sources || [];
  const newsTimeline = detail.news_timeline || [];
  const relatedStocks = detail.related_stocks || [];
  const terms = detail.terms || [];
  const reasons = analysis.reasons || [];
  const changeClass = Number(event.change_rate) >= 0 ? "up" : "down";
  const title = `${stock.name || "-"} 브리핑`;
  const basisLabel = detail.data_basis?.label || `${sources.length}건`;
  const key = [
    stock.ticker,
    event.current_price,
    event.change_rate,
    event.volume_change_rate,
    sources.length,
    newsTimeline.length,
    relatedStocks.length,
    terms.length,
    reasons.length,
  ].join(":");

  return {
    key,
    steps: [
      { label: "전체 지도", card: 0, view: { x: 1060, y: 900, scale: 0.42, mobileScale: 0.22 } },
      { label: "종목 요약", card: 1, view: { x: 430, y: 315, scale: 0.95, mobileScale: 0.48 } },
      { label: "가격 반응", card: 2, view: { x: 1240, y: 330, scale: 1.02, mobileScale: 0.48 } },
      { label: "원인 정리", card: 3, view: { x: 620, y: 915, scale: 0.82, mobileScale: 0.43 } },
      { label: "근거 자료", card: 4, view: { x: 1500, y: 955, scale: 0.78, mobileScale: 0.42 } },
      { label: "함께 볼 것", card: 5, view: { x: 1060, y: 1520, scale: 0.82, mobileScale: 0.43 } },
    ],
    html: `
      <div class="presentation-viewport">
        <div class="presentation-canvas">
          <div class="presentation-map-label" style="left: 78px; top: 30px;">WhyStock camera map</div>
          <article class="presentation-card presentation-overview-card" data-presentation-card="1" style="left: 80px; top: 90px; width: 700px;">
            <span class="presentation-node-index">01</span>
            <p class="presentation-kicker">${escapeHtml(stock.market || "Stock")} · ${escapeHtml(stock.ticker || "-")}</p>
            <h2>${escapeHtml(title)}</h2>
            <div class="presentation-metrics">
              <div><span>현재가</span><strong>${escapeHtml(formatPrice(event.current_price))}</strong></div>
              <div><span>변동률</span><strong class="${changeClass}">${escapeHtml(formatPercent(event.change_rate))}</strong></div>
              <div><span>거래량 변화</span><strong>${escapeHtml(formatPercent(event.volume_change_rate))}</strong></div>
            </div>
            <p class="presentation-summary">${escapeHtml(analysis.summary || "아직 분석 요약이 없습니다.")}</p>
          </article>

          <article class="presentation-card presentation-price-card" data-presentation-card="2" style="left: 940px; top: 120px; width: 600px;">
            <span class="presentation-node-index">02</span>
            <p class="presentation-kicker">Price action</p>
            <h2>가격과 거래량이 먼저 보여주는 신호</h2>
            <div class="presentation-split">
              <div class="presentation-focus ${changeClass}">
                <span>등락률</span>
                <strong>${escapeHtml(formatPercent(event.change_rate))}</strong>
              </div>
              <div class="presentation-facts">
                <div><span>거래량 변화</span><strong>${escapeHtml(formatPercent(event.volume_change_rate))}</strong></div>
                <div><span>자료 기준</span><strong>${escapeHtml(basisLabel)}</strong></div>
                <div><span>감지 시각</span><strong>${escapeHtml(formatTime(event.detected_at))}</strong></div>
              </div>
            </div>
            <p class="presentation-note">${escapeHtml(detail.data_basis?.note || "가격, 거래량, 뉴스, 공시 자료를 함께 확인해 해석합니다.")}</p>
          </article>

          <article class="presentation-card presentation-reasons-card" data-presentation-card="3" style="left: 250px; top: 680px; width: 740px;">
            <span class="presentation-node-index">03</span>
            <p class="presentation-kicker">Why it moved</p>
            <h2>핵심 원인 후보</h2>
            ${presentationReasonList(reasons)}
          </article>

          <article class="presentation-card presentation-evidence-card" data-presentation-card="4" style="left: 1130px; top: 680px; width: 740px;">
            <span class="presentation-node-index">04</span>
            <p class="presentation-kicker">Evidence</p>
            <h2>확인한 뉴스와 공시</h2>
            <div class="presentation-two-column">
              <div>
                <h3>근거 자료</h3>
                ${presentationSourceList(sources)}
              </div>
              <div>
                <h3>뉴스 흐름</h3>
                ${presentationNewsList(newsTimeline)}
              </div>
            </div>
          </article>

          <article class="presentation-card presentation-next-card" data-presentation-card="5" style="left: 700px; top: 1310px; width: 720px;">
            <span class="presentation-node-index">05</span>
            <p class="presentation-kicker">Next checks</p>
            <h2>관련 종목과 용어</h2>
            <div class="presentation-two-column">
              <div>
                <h3>관련 종목</h3>
                ${presentationRelatedList(relatedStocks)}
              </div>
              <div>
                <h3>감지된 용어</h3>
                ${presentationTermList(terms)}
              </div>
            </div>
          </article>
        </div>
      </div>
    `,
  };
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

async function submitAssistantQuestion(event) {
  event?.preventDefault();
  const message = nodes.assistantInput.value.trim();
  if (!message) {
    nodes.assistantAnswer.hidden = false;
    nodes.assistantAnswer.textContent = "질문을 입력해 주세요.";
    return;
  }

  nodes.assistantSubmit.disabled = true;
  nodes.assistantAnswer.hidden = false;
  nodes.assistantAnswer.textContent = "답변을 준비하는 중입니다.";

  try {
    const data = await fetchJson("/api/assistant/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message }),
    });
    renderAssistantAnswer(data);
    if (data.intent === "stock_briefing" && data.stock?.ticker) {
      await selectStockBriefing(data.stock.ticker);
    }
  } catch (error) {
    console.error("Failed to ask assistant", error);
    nodes.assistantAnswer.textContent = "답변을 가져오지 못했습니다. 잠시 후 다시 시도해 주세요.";
  } finally {
    nodes.assistantSubmit.disabled = false;
  }
}

function renderAssistantAnswer(data) {
  const answer = document.createElement("div");
  answer.className = "assistant-answer-body";

  const heading = document.createElement("strong");
  heading.textContent = intentLabel(data.intent);
  const text = document.createElement("p");
  text.textContent = data.answer || "답변이 없습니다.";

  answer.append(heading, text);

  if (data.stock?.ticker && data.intent === "related_stocks") {
    const button = document.createElement("button");
    button.type = "button";
    button.className = "assistant-link-button";
    button.textContent = `${data.stock.name} 브리핑 보기`;
    button.addEventListener("click", () => selectStockBriefing(data.stock.ticker));
    answer.appendChild(button);
  }

  nodes.assistantAnswer.replaceChildren(answer);
}

function intentLabel(intent) {
  const labels = {
    stock_briefing: "종목 브리핑",
    market_summary: "시장 요약",
    term_explanation: "용어 설명",
    related_stocks: "관련 종목",
    unsupported: "지원 범위",
  };
  return labels[intent] || "답변";
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
