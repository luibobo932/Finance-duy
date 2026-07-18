"use strict";

const byId = (id) => document.getElementById(id);
const number = new Intl.NumberFormat("vi-VN", { maximumFractionDigits: 2 });
let privatePortfolio = {};

function get(object, ...path) {
  return path.reduce((value, key) => value?.[key], object);
}

function verifiedFieldsFor(data, snapshot) {
  if (!snapshot) return new Set();
  const item = (data.history_provenance || []).find((row) => row.date === snapshot.date && row.ky === snapshot.ky);
  return new Set(item?.verified_fields || []);
}

function fieldIsVerified(fields, field) {
  if (field === "gold.premium_trieu") {
    return ["gold.sjc_sell", "gold.xauusd", "fx_vcb_sell"].every((name) => fields.has(name));
  }
  return fields.has(field);
}

function fmt(value, suffix = "") {
  return Number.isFinite(value) ? `${number.format(value)}${suffix}` : "Chưa có";
}

function period(snapshot) {
  if (!snapshot) return "Chưa có kỳ trước";
  return `${snapshot.date} · ${snapshot.ky === "sang" ? "kỳ sáng" : "kỳ chiều"}`;
}

function delta(current, previous) {
  if (!Number.isFinite(current) || !Number.isFinite(previous)) return null;
  return current - previous;
}

function deltaText(current, previous, suffix = "") {
  const value = delta(current, previous);
  if (value === null) return { text: "Chưa đủ dữ liệu", className: "muted" };
  const pct = previous ? ` (${value / previous * 100 >= 0 ? "+" : ""}${number.format(value / previous * 100)}%)` : "";
  return {
    text: `${value > 0 ? "▲" : value < 0 ? "▼" : "="} ${number.format(Math.abs(value))}${suffix}${pct}`,
    className: value > 0 ? "positive" : value < 0 ? "negative" : "muted",
  };
}

function addMetric(container, label, value, detail, tone = "muted") {
  const card = document.createElement("article");
  card.className = "metric";
  const labelNode = document.createElement("span");
  labelNode.className = "metric-label";
  labelNode.textContent = label;
  const valueNode = document.createElement("span");
  valueNode.className = "metric-value";
  valueNode.textContent = value;
  const detailNode = document.createElement("span");
  detailNode.className = `metric-detail ${tone}`;
  detailNode.textContent = detail;
  card.append(labelNode, valueNode, detailNode);
  container.append(card);
}

function addStackItem(container, label, description, value, tone = "") {
  const row = document.createElement("div");
  row.className = "stack-item";
  const left = document.createElement("div");
  const title = document.createElement("strong");
  title.textContent = label;
  const note = document.createElement("small");
  note.textContent = description;
  left.append(title, note);
  const right = document.createElement("div");
  right.className = `stack-value number ${tone}`;
  right.textContent = value;
  row.append(left, right);
  container.append(row);
}

function renderSummary(data) {
  const current = data.latest;
  const previous = data.previous;
  const container = byId("summary");
  const coveredFields = verifiedFieldsFor(data, current);
  const previousFields = verifiedFieldsFor(data, previous);
  const marketComparable = Boolean(current.market_date && previous?.market_date && current.market_date !== previous.market_date && coveredFields.has("market_date") && previousFields.has("market_date"));
  const unavailableMarketDelta = { text: "Thiếu/không đổi market_date", className: "muted" };
  const vn = marketComparable ? deltaText(get(current, "vnindex", "close"), get(previous, "vnindex", "close"), " điểm") : unavailableMarketDelta;
  const vcb = marketComparable ? deltaText(get(current, "vcb", "close"), get(previous, "vcb", "close"), " đ") : unavailableMarketDelta;
  const ctd = marketComparable ? deltaText(get(current, "ctd", "close"), get(previous, "ctd", "close"), " đ") : unavailableMarketDelta;
  const goldComparable = Boolean(get(current, "gold", "observed_at") && get(previous, "gold", "observed_at") && get(current, "gold", "observed_at") !== get(previous, "gold", "observed_at") && coveredFields.has("gold.observed_at") && previousFields.has("gold.observed_at"));
  const gold = goldComparable
    ? deltaText(get(current, "gold", "xauusd"), get(previous, "gold", "xauusd"), " $")
    : { text: "Thiếu/không đổi thời điểm giá", className: "muted" };
  const topRate = data.decision?.savings?.eligible_products?.[0];

  addMetric(container, "VN-Index", coveredFields.has("vnindex.close") ? fmt(get(current, "vnindex", "close")) : "Chưa xác minh", vn.text, vn.className);
  addMetric(container, "VCB", coveredFields.has("vcb.close") ? fmt(get(current, "vcb", "close"), " đ") : "Chưa xác minh", vcb.text, vcb.className);
  addMetric(container, "CTD", coveredFields.has("ctd.close") ? fmt(get(current, "ctd", "close"), " đ") : "Chưa xác minh", ctd.text, ctd.className);
  addMetric(container, "Vàng thế giới", coveredFields.has("gold.xauusd") ? fmt(get(current, "gold", "xauusd"), " $/oz") : "Chưa xác minh", gold.text, gold.className);
  const rateVerified = data.decision?.savings?.decision_status === "READY";
  addMetric(container, "Lãi suất đã xác minh", topRate && rateVerified ? fmt(topRate.rate_pct, "%/năm") : "Chưa xác minh", topRate && rateVerified ? `${topRate.bank} · ${topRate.term_months} tháng` : "Không dùng mức trong snapshot để ra quyết định");
}

function renderComparison(data) {
  byId("period-badge").textContent = period(data.latest);
  const rows = [
    ["VN-Index", ["vnindex", "close"], ""],
    ["VCB", ["vcb", "close"], " đ"],
    ["CTD", ["ctd", "close"], " đ"],
    ["Vàng SJC bán ra", ["gold", "sjc_sell"], " triệu"],
    ["XAU/USD", ["gold", "xauusd"], " $"],
    ["Chênh vàng VN–TG", ["gold", "premium_trieu"], " triệu"],
  ];
  const body = byId("comparison");
  const currentFields = verifiedFieldsFor(data, data.latest);
  const previousFields = verifiedFieldsFor(data, data.previous);
  const marketComparable = Boolean(
    data.latest.market_date &&
    data.previous?.market_date &&
    data.latest.market_date !== data.previous.market_date &&
    currentFields.has("market_date") &&
    previousFields.has("market_date")
  );
  const goldComparable = Boolean(
    get(data.latest, "gold", "observed_at") &&
    get(data.previous, "gold", "observed_at") &&
    get(data.latest, "gold", "observed_at") !== get(data.previous, "gold", "observed_at") &&
    currentFields.has("gold.observed_at") &&
    previousFields.has("gold.observed_at")
  );
  rows.forEach(([label, path, suffix], rowIndex) => {
    const field = path.join(".");
    const current = fieldIsVerified(currentFields, field) ? get(data.latest, ...path) : null;
    const previous = fieldIsVerified(previousFields, field) ? get(data.previous, ...path) : null;
    const change = rowIndex < 3 && !marketComparable
      ? { text: "Thiếu/không đổi market_date", className: "muted" }
      : rowIndex >= 3 && !goldComparable
        ? { text: "Thiếu/không đổi thời điểm giá", className: "muted" }
        : deltaText(current, previous, suffix);
    const tr = document.createElement("tr");
    [label, fmt(current, suffix), fmt(previous, suffix), change.text].forEach((value, index) => {
      const td = document.createElement("td");
      td.textContent = value;
      if (index > 0) td.className = `number ${index === 3 ? change.className : ""}`;
      tr.append(td);
    });
    body.append(tr);
  });
}

function renderPortfolio(data) {
  const container = byId("portfolio");
  container.replaceChildren();
  const form = document.createElement("form");
  form.className = "portfolio-form";
  const coveredFields = verifiedFieldsFor(data, data.latest);
  ["VCB", "CTD"].forEach((ticker) => {
    const position = privatePortfolio[ticker] || {};
    const price = coveredFields.has(`${ticker.toLowerCase()}.close`) ? get(data.latest, ticker.toLowerCase(), "close") : null;
    const group = document.createElement("fieldset");
    const legend = document.createElement("legend");
    legend.textContent = `${ticker} · giá gần nhất ${fmt(price, " đ")}`;
    const cost = document.createElement("input");
    cost.type = "number";
    cost.min = "0";
    cost.step = "100";
    cost.placeholder = "Giá vốn";
    cost.value = Number.isFinite(position.avg_cost) ? position.avg_cost : "";
    cost.dataset.field = "avg_cost";
    cost.dataset.ticker = ticker;
    cost.setAttribute("aria-label", `Giá vốn ${ticker}`);
    const quantity = document.createElement("input");
    quantity.type = "number";
    quantity.min = "0";
    quantity.step = "1";
    quantity.placeholder = "Số lượng";
    quantity.value = Number.isFinite(position.quantity) ? position.quantity : "";
    quantity.dataset.field = "quantity";
    quantity.dataset.ticker = ticker;
    quantity.setAttribute("aria-label", `Số lượng ${ticker}`);
    group.append(legend, cost, quantity);
    form.append(group);

    if (Number.isFinite(position.avg_cost) && Number.isFinite(position.quantity) && Number.isFinite(price)) {
      const pnl = (price - position.avg_cost) * position.quantity;
      const pct = position.avg_cost ? (price - position.avg_cost) / position.avg_cost * 100 : 0;
      addStackItem(container, `${ticker} tạm tính`, "Chỉ nằm trong bộ nhớ của tab", `${pnl >= 0 ? "+" : "−"}${number.format(Math.abs(pnl))} đ (${number.format(pct)}%)`, pnl >= 0 ? "positive" : "negative");
    }
  });
  const button = document.createElement("button");
  button.type = "submit";
  button.textContent = "Tính tạm trong phiên này";
  const clear = document.createElement("button");
  clear.type = "button";
  clear.textContent = "Xóa số liệu";
  form.append(button, clear);
  form.addEventListener("submit", (event) => {
    event.preventDefault();
    const portfolio = {};
    ["VCB", "CTD"].forEach((ticker) => {
      const avgCost = Number(form.querySelector(`[data-ticker="${ticker}"][data-field="avg_cost"]`).value);
      const quantity = Number(form.querySelector(`[data-ticker="${ticker}"][data-field="quantity"]`).value);
      portfolio[ticker] = {
        avg_cost: avgCost > 0 ? avgCost : null,
        quantity: quantity > 0 ? quantity : null,
      };
    });
    privatePortfolio = portfolio;
    renderPortfolio(data);
  });
  clear.addEventListener("click", () => {
    privatePortfolio = {};
    renderPortfolio(data);
  });
  container.prepend(form);
  const note = document.createElement("p");
  note.className = "empty";
  note.textContent = "Giá vốn và số lượng chỉ nằm trong bộ nhớ của tab này; đóng hoặc tải lại trang sẽ xóa.";
  container.append(note);
}

function renderDataHealth(decision) {
  const container = byId("data-health");
  const quality = decision.data_quality;
  const left = document.createElement("div");
  const title = document.createElement("strong");
  title.textContent = `Sức khỏe dữ liệu: ${quality.score}/100 · ${quality.grade}`;
  const detail = document.createElement("div");
  detail.className = "muted";
  detail.textContent = `${quality.source_count} nguồn khớp registry · phủ ${quality.source_coverage_pct || 0}% nhóm dữ liệu · cách hiện tại ${quality.age_days} ngày`;
  left.append(title, detail);
  const list = document.createElement("ul");
  (quality.warnings || []).slice(0, 3).forEach((warning) => {
    const item = document.createElement("li");
    item.textContent = warning;
    list.append(item);
  });
  container.append(left, list);
}

function applyRuntimeFreshness(data) {
  const latest = data.latest;
  const rawTime = latest.collected_at || `${latest.date}T23:59:59+07:00`;
  const effectiveTime = new Date(rawTime).getTime();
  const ageDays = Number.isFinite(effectiveTime)
    ? Math.max(0, Math.floor((Date.now() - effectiveTime) / 86400000))
    : Number.POSITIVE_INFINITY;
  const threshold = data.decision.profile.stale_after_days ?? 3;
  const quality = data.decision.data_quality;
  quality.age_days = ageDays;
  quality.is_stale = ageDays > threshold;
  if (!quality.is_stale) return;
  quality.score = Math.min(quality.score, 40);
  quality.grade = "Thấp";
  const warning = `Dữ liệu đã quá hạn ${ageDays} ngày khi mở dashboard`;
  if (!quality.warnings.includes(warning)) quality.warnings.unshift(warning);
  const decisions = [
    ...data.decision.asset_classes,
    data.decision.gold,
    data.decision.savings,
    ...data.decision.stocks,
  ];
  decisions.forEach((item) => {
    item.decision_status = "WAIT_DATA";
    item.signal = "Chờ dữ liệu";
    if (item.action && !item.action.startsWith("CHỜ DỮ LIỆU")) item.action = `CHỜ DỮ LIỆU — ${item.action}`;
  });
}

function decisionCard(item) {
  const card = document.createElement("article");
  card.className = "decision-card";
  const top = document.createElement("div");
  top.className = "decision-top";
  const heading = document.createElement("div");
  const title = document.createElement("h3");
  title.textContent = item.name;
  const status = document.createElement("div");
  status.className = item.decision_status === "READY" ? "status-ready" : "status-wait";
  status.textContent = item.signal;
  heading.append(title, status);
  const score = document.createElement("span");
  score.className = "decision-score";
  score.textContent = `${item.score}/100`;
  top.append(heading, score);
  const confidenceNode = document.createElement("div");
  confidenceNode.className = "confidence";
  confidenceNode.textContent = `Độ tin cậy ${item.confidence}/100 · Rủi ro ${item.risk_level || "—"}`;
  const action = document.createElement("p");
  action.textContent = item.action || "Xem chi tiết từng mã trước khi quyết định.";
  const details = document.createElement("details");
  const summary = document.createElement("summary");
  summary.textContent = "Lý do, rủi ro và dữ liệu còn thiếu";
  const list = document.createElement("ul");
  [
    ...(item.reasons || []).map((text) => `✓ ${text}`),
    ...(item.risks || []).map((text) => `! ${text}`),
    ...(item.hard_blockers || []).map((text) => `⛔ ${text}`),
    ...(item.missing_data || []).map((text) => `? Thiếu: ${text}`),
    ...(item.invalidation || []).map((text) => `Dừng luận điểm nếu: ${text}`),
  ].forEach((text) => {
    const row = document.createElement("li");
    row.textContent = text;
    list.append(row);
  });
  details.append(summary, list);
  card.append(top, confidenceNode, action, details);
  return card;
}

function renderDecisions(data) {
  const decision = data.decision;
  renderDataHealth(decision);
  const main = byId("asset-decisions");
  const detailsById = {
    savings: decision.savings,
    gold: decision.gold,
    stocks: { ...decision.asset_classes.find((item) => item.id === "stocks") },
  };
  ["savings", "gold", "stocks"].forEach((id) => main.append(decisionCard(detailsById[id])));
  const stocks = byId("stock-decisions");
  decision.stocks.forEach((item) => stocks.append(decisionCard(item)));
  const guardrails = byId("guardrails");
  decision.guardrails.forEach((text) => {
    const item = document.createElement("li");
    item.textContent = text;
    guardrails.append(item);
  });
  const sources = byId("sources");
  const verifiedSources = data.decision.verified_sources || [];
  if (!verifiedSources.length) {
    sources.textContent = "Chưa có nguồn được gắn vào snapshot — mọi quyết định bị khóa.";
  } else {
    verifiedSources.forEach((source) => {
      const row = document.createElement("div");
      const link = document.createElement("a");
      link.href = source.url;
      link.target = "_blank";
      link.rel = "noopener noreferrer";
      link.textContent = `${source.name} · ${source.fields.join(", ")}`;
      row.append(link);
      sources.append(row);
    });
  }
}

function normalizedWeights(weights) {
  const total = Object.values(weights).reduce((sum, value) => sum + value, 0);
  return Object.fromEntries(Object.entries(weights).map(([key, value]) => [key, value / total * 100]));
}

function renderScenario(data) {
  const form = byId("scenario-form");
  const calculate = () => {
    const capital = Number(byId("capital").value);
    const reserve = Number(byId("reserve").value);
    const investable = Math.max(0, capital - reserve);
    const goal = byId("goal").value;
    const horizon = Number(byId("horizon").value);
    const liquidity = byId("liquidity").value;
    const bases = {
      conservative: { savings: 70, gold: 20, stocks: 10 },
      balanced: { savings: 45, gold: 20, stocks: 35 },
      growth: { savings: 25, gold: 15, stocks: 60 },
    };
    const weights = { ...bases[goal] };
    if (horizon < 12) { weights.savings += 15; weights.stocks -= 15; }
    if (horizon >= 60) { weights.stocks += 10; weights.savings -= 10; }
    if (liquidity === "high") { weights.savings += 10; weights.stocks -= 10; }
    if (liquidity === "low" && horizon >= 24) { weights.stocks += 5; weights.savings -= 5; }

    const classMap = Object.fromEntries(data.decision.asset_classes.map((item) => [item.id, item]));
    Object.keys(weights).forEach((id) => {
      const item = classMap[id];
      if (item?.decision_status === "READY") weights[id] *= 0.85 + item.score / 200;
      weights[id] = Math.max(0, weights[id]);
    });
    const finalWeights = normalizedWeights(weights);
    const allReady = data.decision.asset_classes.every((item) => item.decision_status === "READY");
    const provisionalSavingsAmount = investable * finalWeights.savings / 100;
    const savingsProductFits = (data.decision.savings.eligible_products || []).some((item) =>
      provisionalSavingsAmount >= item.minimum_amount_vnd && provisionalSavingsAmount <= item.maximum_amount_vnd
    );
    const scenarioReady = allReady && savingsProductFits;
    const output = byId("allocation");
    output.replaceChildren();
    [["savings", "Gửi tiết kiệm"], ["gold", "Vàng"], ["stocks", "VCB/CTD (không đại diện thị trường)"]].forEach(([id, label]) => {
      const card = document.createElement("div");
      card.className = "allocation-card";
      const title = document.createElement("strong");
      title.textContent = `${label} · ${number.format(finalWeights[id])}%`;
      const amount = document.createElement("span");
      amount.textContent = scenarioReady
        ? `${number.format(investable * finalWeights[id] / 100)} đ`
        : "Khóa — chưa đủ dữ liệu cho cả 3 nhóm";
      card.append(title, amount);
      output.append(card);
    });
    const savingsAmount = scenarioReady ? provisionalSavingsAmount : 0;
    const insuranceLimit = data.decision.profile.deposit_insurance_limit_vnd || 0;
    const insuranceNote = insuranceLimit && savingsAmount > insuranceLimit
      ? ` Phần gửi tiết kiệm vượt ${number.format(insuranceLimit)} đ; nên kiểm tra phạm vi bảo hiểm và cân nhắc chia tổ chức.`
      : "";
    byId("allocation-note").textContent = investable <= 0
      ? "Quỹ dự phòng đang bằng hoặc lớn hơn tổng vốn; chưa có tiền có thể phân bổ."
      : `Vốn có thể mô phỏng: ${number.format(investable)} đ. ${scenarioReady ? "Tỷ trọng đã điều chỉnh nhẹ theo các tín hiệu đủ tin cậy." : allReady ? "Khoản dự kiến gửi tiết kiệm không nằm trong dải số tiền của sản phẩm đã xác minh; hệ thống khóa phân bổ." : "Chưa đủ dữ liệu cho cả ba nhóm tài sản; hệ thống khóa toàn bộ số tiền phân bổ."}${insuranceNote}`;
  };
  form.addEventListener("submit", (event) => { event.preventDefault(); calculate(); });
  calculate();
}

function renderScorecard(scorecard) {
  const container = byId("scorecard");
  const items = [
    ["Trạng thái", scorecard.status === "READY" ? "Đủ mẫu" : "Chưa đủ mẫu"],
    ["Nhật ký", `${scorecard.journal_entries} kỳ`],
    ["Đã đánh giá", `${scorecard.assessed}/${scorecard.minimum_assessed}`],
    ["Đúng hướng", Number.isFinite(scorecard.directional_accuracy_pct) ? `${number.format(scorecard.directional_accuracy_pct)}%` : "Chưa công bố"],
  ];
  items.forEach(([label, value]) => {
    const card = document.createElement("div");
    card.className = "scorecard-item";
    const small = document.createElement("small");
    small.textContent = label;
    const strong = document.createElement("strong");
    strong.textContent = value;
    card.append(small, strong);
    container.append(card);
  });
}

function volumeSignal(data, ticker) {
  const history = data.history;
  const latest = history.at(-1);
  const current = get(latest, ticker, "volume_million_shares");
  const latestFields = verifiedFieldsFor(data, latest);
  if (latest.ky !== "chieu" || !latest.market_date || !latestFields.has("market_date") || !latestFields.has(`${ticker}.volume_million_shares`)) return null;
  const byDate = new Map();
  history.slice(0, -1).forEach((item) => {
    const value = get(item, ticker, "volume_million_shares");
    const fields = verifiedFieldsFor(data, item);
    if (item.ky === "chieu" && item.market_date && Number.isFinite(value) && fields.has("market_date") && fields.has(`${ticker}.volume_million_shares`)) byDate.set(item.market_date, value);
  });
  const past = [...byDate.values()].slice(-20);
  if (!Number.isFinite(current) || !past.length) return null;
  const average = past.reduce((sum, value) => sum + value, 0) / past.length;
  return average ? current / average : null;
}

function renderSignals(data) {
  const container = byId("signals");
  ["vcb", "ctd"].forEach((ticker) => {
    const ratio = volumeSignal(data, ticker);
    addStackItem(
      container,
      `KLGD ${ticker.toUpperCase()}`,
      ratio === null ? "Cần thêm phiên chiều có khối lượng" : `So với bình quân tối đa 20 phiên`,
      ratio === null ? "Chưa đủ dữ liệu" : `${number.format(ratio)}× BQ`,
      ratio >= 1.5 ? "negative" : "",
    );
  });
  const currentFields = new Set((data.decision.verified_sources || []).flatMap((source) => source.fields || []));
  const latestFlow = currentFields.has("foreign_net_ty") ? data.latest.foreign_net_ty : null;
  addStackItem(container, "Khối ngoại", "Chỉ hiện số kỳ hiện tại có nguồn đúng field", fmt(latestFlow, " tỷ"), latestFlow > 0 ? "positive" : latestFlow < 0 ? "negative" : "");
}

function renderHistory(data) {
  const body = byId("history");
  [...data.history].reverse().slice(0, 30).forEach((item) => {
    const fields = verifiedFieldsFor(data, item);
    const verifiedValue = (field, path) => fieldIsVerified(fields, field) ? get(item, ...path) : null;
    const values = [
      `${period(item)} · ${fields.size ? "nguồn một phần" : "legacy"}`,
      fmt(verifiedValue("vnindex.close", ["vnindex", "close"])),
      fmt(verifiedValue("vcb.close", ["vcb", "close"]), " đ"),
      fmt(verifiedValue("ctd.close", ["ctd", "close"]), " đ"),
      fmt(verifiedValue("gold.xauusd", ["gold", "xauusd"]), " $"),
      fmt(verifiedValue("foreign_net_ty", ["foreign_net_ty"]), " tỷ"),
    ];
    const tr = document.createElement("tr");
    values.forEach((value, index) => {
      const td = document.createElement("td");
      td.textContent = value;
      if (index > 0) td.className = "number";
      tr.append(td);
    });
    body.append(tr);
  });
}

function renderRates(data) {
  const container = byId("rates");
  const rates = data.decision.savings.eligible_products || [];
  rates.slice(0, 5).forEach((item) => addStackItem(container, item.bank, `${item.term_months} tháng · ${number.format(item.minimum_amount_vnd)}–${number.format(item.maximum_amount_vnd)} đ`, fmt(item.rate_pct, "%")));
  if (!rates.length) container.textContent = "Chưa có sản phẩm lãi suất đủ điều kiện và nguồn để sử dụng.";
}

function renderRisks(data) {
  const container = byId("risks");
  const labels = { arrest: "Doanh nghiệp", war: "Địa chính trị", trump: "Chính sách Mỹ", fed: "Fed" };
  const risks = Object.entries(data.decision.verified_risks || {}).filter(([, value]) => value);
  risks.forEach(([key, value]) => addStackItem(container, labels[key] || key, String(value), "Theo dõi"));
  if (!risks.length) container.textContent = "Chưa có cờ rủi ro nào đủ provenance để chấm điểm.";
}

async function start() {
  try {
    const response = await fetch("./data.json", { cache: "no-store" });
    if (!response.ok) throw new Error(`Không đọc được data.json (${response.status})`);
    const data = await response.json();
    if (!data.latest || !Array.isArray(data.history)) throw new Error("Dữ liệu dashboard không đúng định dạng");
    applyRuntimeFreshness(data);
    byId("updated").textContent = `Cập nhật theo ${period(data.latest)} · ${data.history.length} bản ghi`;
    renderSummary(data);
    renderDecisions(data);
    renderScenario(data);
    renderScorecard(data.scorecard);
    renderComparison(data);
    renderPortfolio(data);
    renderSignals(data);
    renderHistory(data);
    renderRates(data);
    renderRisks(data);
  } catch (error) {
    const alert = byId("error");
    alert.hidden = false;
    alert.textContent = `${error.message}. Hãy chạy: python scripts/build_dashboard.py`;
    byId("updated").textContent = "Không thể tải dữ liệu";
  }
}

let savedTheme = null;
try { savedTheme = localStorage.getItem("finance-theme"); } catch (_) { /* Trình duyệt chặn lưu cục bộ */ }
if (savedTheme) document.documentElement.dataset.theme = savedTheme;
byId("theme-toggle").addEventListener("click", () => {
  const next = document.documentElement.dataset.theme === "dark" ? "light" : "dark";
  document.documentElement.dataset.theme = next;
  try { localStorage.setItem("finance-theme", next); } catch (_) { /* Không ảnh hưởng chức năng chính */ }
});

start();
