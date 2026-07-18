"use strict";

const byId = (id) => document.getElementById(id);
const number = new Intl.NumberFormat("vi-VN", { maximumFractionDigits: 2 });
const integer = new Intl.NumberFormat("vi-VN", { maximumFractionDigits: 0 });
const shortDate = new Intl.DateTimeFormat("vi-VN", { day: "2-digit", month: "2-digit", year: "numeric" });
let privatePortfolio = {};

function get(object, ...path) {
  return path.reduce((value, key) => value?.[key], object);
}

function fmt(value, suffix = "") {
  return Number.isFinite(value) ? `${number.format(value)}${suffix}` : "Chưa có";
}

function fmtInteger(value, suffix = "") {
  return Number.isFinite(value) ? `${integer.format(value)}${suffix}` : "Chưa có";
}

function fmtCompact(value, suffix = "") {
  if (!Number.isFinite(value)) return "Chưa có";
  const absolute = Math.abs(value);
  const scaled = absolute >= 1e9 ? [value / 1e9, " tỷ"] : absolute >= 1e6 ? [value / 1e6, " triệu"] : absolute >= 1e3 ? [value / 1e3, " nghìn"] : [value, ""];
  return `${number.format(scaled[0])}${scaled[1]}${suffix}`;
}

function formatIsoDate(value) {
  if (!value) return "Chưa có";
  const parsed = new Date(`${String(value).slice(0, 10)}T00:00:00+07:00`);
  return Number.isNaN(parsed.getTime()) ? String(value) : shortDate.format(parsed);
}

function formatDateTime(value) {
  if (!value) return "Chưa có";
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return String(value);
  return new Intl.DateTimeFormat("vi-VN", { day: "2-digit", month: "2-digit", year: "numeric", hour: "2-digit", minute: "2-digit", timeZone: "Asia/Ho_Chi_Minh" }).format(parsed);
}

function period(snapshot) {
  if (!snapshot) return "Chưa có kỳ trước";
  return `${formatIsoDate(snapshot.date)} · ${snapshot.ky === "sang" ? "kỳ sáng" : "kỳ chiều"}`;
}

function verifiedFieldsFor(data, snapshot) {
  if (!snapshot) return new Set();
  const item = (data.history_provenance || []).find((row) => row.date === snapshot.date && row.ky === snapshot.ky);
  return new Set(item?.verified_fields || []);
}

function fieldIsVerified(fields, field) {
  if (field === "gold.premium_trieu") return ["gold.sjc_sell", "gold.xauusd", "fx_vcb_sell"].every((name) => fields.has(name));
  return fields.has(field);
}

function safePercent(numerator, denominator) {
  return Number.isFinite(numerator) && Number.isFinite(denominator) && denominator !== 0 ? numerator / denominator * 100 : null;
}

function humanizeFieldText(value) {
  const replacements = {
    "gold.observed_at": "thời điểm hiệu lực giá vàng",
    "gold.sjc_buy": "giá mua SJC",
    "gold.sjc_sell": "giá bán SJC",
    "gold.xauusd": "giá vàng quốc tế",
    "fx_vcb_sell": "tỷ giá bán USD tại VCB",
    "vcb.fundamentals": "dữ liệu cơ bản VCB",
    "ctd.fundamentals": "dữ liệu cơ bản CTD",
    "vnindex.change_pct": "% thay đổi VN-Index",
    "vnindex.close": "điểm đóng cửa VN-Index",
    "channel, minimum_amount_vnd, maximum_amount_vnd, conditions, effective_date, payout_method, source_id, source_url, retrieved_at": "kênh gửi, số tiền tối thiểu/tối đa, điều kiện, ngày hiệu lực, cách trả lãi, nguồn và thời điểm lấy",
  };
  const normalized = String(value)
    .replace("Thiếu thời điểm hiệu lực giá vàng (gold.observed_at)", "Thiếu thời điểm hiệu lực giá vàng")
    .replaceAll("premium", "mức chênh lệch");
  return Object.entries(replacements).reduce((text, [field, label]) => text.replaceAll(field, label), normalized);
}

function addMetric(container, { label, value, detail, tone = "muted", verified = false }) {
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
  if (verified) {
    const marker = document.createElement("span");
    marker.className = "metric-source";
    marker.title = "Có nguồn dữ liệu";
    card.append(marker);
  }
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

function setRuntimeState(state) {
  document.body.dataset.state = state;
  const label = byId("runtime-label");
  if (state === "error") label.textContent = "LỖI DỮ LIỆU";
  else if (state === "blocked") label.textContent = "CHƯA ĐỦ ĐIỀU KIỆN HÀNH ĐỘNG";
  else if (state === "ready") label.textContent = "ĐÃ QUA CỔNG DỮ LIỆU VÀ KIỂM CHỨNG";
}

function applyRuntimeFreshness(data) {
  const quality = data.decision.data_quality;
  if (!Array.isArray(quality.warnings)) quality.warnings = [];
  const registry = data.source_registry || {};
  const staleSources = [];
  for (const source of data.decision.verified_sources || []) {
    const retrieved = new Date(source.retrieved_at).getTime();
    const validHours = registry[source.id]?.stale_after_hours;
    if (!Number.isFinite(retrieved) || !Number.isFinite(validHours)) continue;
    const ageHours = Math.max(0, (Date.now() - retrieved) / 3600000);
    if (ageHours > validHours) staleSources.push({ id: source.id, ageHours, validHours });
  }

  const rawTime = data.latest.collected_at || `${data.latest.date}T23:59:59+07:00`;
  const effectiveTime = new Date(rawTime).getTime();
  const ageDays = Number.isFinite(effectiveTime) ? Math.max(0, Math.floor((Date.now() - effectiveTime) / 86400000)) : Number.POSITIVE_INFINITY;
  const globalThreshold = data.decision.profile.stale_after_days ?? 3;
  quality.age_days = ageDays;
  quality.is_stale = ageDays > globalThreshold || staleSources.length > 0;
  const lock = (item) => {
    if (!item) return;
    item.decision_status = "WAIT_DATA";
    item.signal = "Chờ dữ liệu";
    if (!item.hard_blockers) item.hard_blockers = [];
    if (!item.hard_blockers.includes("Nguồn dữ liệu đã quá hạn khi mở dashboard")) item.hard_blockers.unshift("Nguồn dữ liệu đã quá hạn khi mở dashboard");
  };

  const lockAssetClass = (id) => lock(data.decision.asset_classes.find((item) => item.id === id));
  const lockGold = () => { lockAssetClass("gold"); lock(data.decision.gold); };
  const lockSavings = () => { lockAssetClass("savings"); lock(data.decision.savings); };
  const lockAllStocks = () => { lockAssetClass("stocks"); data.decision.stocks.forEach(lock); };
  const lockStock = (symbol) => {
    lockAssetClass("stocks");
    lock(data.decision.stocks.find((item) => item.id === symbol.toLowerCase()));
  };

  const hoseCrosscheck = data.market_history?.quality?.official_hose_crosscheck;
  const auxiliaryTime = new Date(data.market_history?.retrieved_at).getTime();
  const auxiliaryAgeHours = Number.isFinite(auxiliaryTime) ? Math.max(0, (Date.now() - auxiliaryTime) / 3600000) : null;
  data.runtime = {
    staleSources,
    openedAt: new Date().toISOString(),
    auxiliary: {
      ageHours: auxiliaryAgeHours,
      hoseMatched: hoseCrosscheck?.matched === true,
      hoseAvailable: hoseCrosscheck?.available === true,
    },
  };
  if (!quality.is_stale) return;

  quality.score = Math.min(quality.score, 40);
  quality.grade = "Thấp";
  if (ageDays > globalThreshold) quality.warnings.unshift(`Snapshot đã quá hạn ${ageDays} ngày khi mở dashboard`);
  staleSources.forEach((source) => quality.warnings.unshift(`Nguồn ${source.id} đã quá SLA ${source.validHours} giờ`));

  if (ageDays > globalThreshold) {
    data.decision.asset_classes.forEach(lock);
    data.decision.stocks.forEach(lock);
    lock(data.decision.gold);
    lock(data.decision.savings);
  } else {
    staleSources.forEach((source) => {
      const classes = registry[source.id]?.asset_classes || [];
      if (classes.some((value) => ["stock", "index"].includes(value))) lockAllStocks();
      if (classes.includes("stock_fundamental")) {
        if (source.id.startsWith("vcb_")) lockStock("VCB");
        else if (source.id.startsWith("ctd_")) lockStock("CTD");
        else lockAllStocks();
      }
      if (classes.some((value) => ["gold_domestic", "gold_international", "fx"].includes(value))) lockGold();
      if (classes.includes("deposit")) lockSavings();
    });
  }
}

function marketRows(data, symbol) {
  return data.market_history?.daily?.[symbol] || [];
}

function stockStats(data, symbol) {
  const rows = marketRows(data, symbol).slice(-20);
  if (!rows.length) return null;
  const latest = rows.at(-1);
  const prior = rows.slice(0, -1);
  const first = rows[0];
  const averageVolume = rows.length >= 20 ? prior.reduce((sum, row) => sum + row.matched_volume, 0) / prior.length : null;
  const closePosition = safePercent(latest.close_vnd - latest.low_vnd, latest.high_vnd - latest.low_vnd);
  return {
    rows,
    latest,
    returnWindowPct: safePercent(latest.close_vnd - first.close_vnd, first.close_vnd),
    volumeRatio: averageVolume ? latest.matched_volume / averageVolume : null,
    closePosition,
    intraday: data.market_history?.intraday?.[symbol] || null,
  };
}

function renderSystemStatus(data) {
  const quality = data.decision.data_quality;
  const assets = data.decision.asset_classes || [];
  const decisionItems = [...assets, ...(data.decision.stocks || []), data.decision.gold, data.decision.savings].filter(Boolean);
  const dataReady = decisionItems.length > 0 && decisionItems.every((item) => item.decision_status === "READY");
  const requiredModels = ["gold", "vcb", "ctd"];
  const modelValidated = data.scorecard?.status === "READY"
    && requiredModels.every((id) => data.scorecard?.asset_results?.[id]?.status === "READY");
  const actionable = dataReady && modelValidated;
  data.runtime.gates = { dataReady, modelValidated, actionable };
  const gate = byId("system-gate");
  gate.classList.toggle("is-ready", actionable);
  gate.classList.toggle("is-blocked", !actionable);
  byId("gate-title").textContent = actionable
    ? "ĐÃ QUA CỔNG — chỉ dùng như kịch bản tham khảo có điều kiện"
    : dataReady ? "CHỜ KIỂM CHỨNG — mô hình chưa đủ mẫu cho từng tài sản"
      : "CHỜ DỮ LIỆU — chưa mở khóa quyết định tiền thật";
  const blockers = [...new Set(decisionItems.flatMap((item) => item.hard_blockers || []))];
  byId("gate-message").textContent = actionable
    ? "Dữ liệu bắt buộc và tối thiểu 20 kết quả độc lập cho Vàng, VCB, CTD đã đạt; vẫn phải kiểm tra mục tiêu, thanh khoản và rủi ro cá nhân."
    : dataReady ? "Chưa có tối thiểu 20 kết quả độc lập cho từng nhóm Vàng, VCB và CTD; điểm, hành động và số tiền tiếp tục bị ẩn."
      : blockers.length ? blockers.slice(0, 2).map(humanizeFieldText).join(" · ") : "Ít nhất một nhóm tài sản chưa đủ nguồn hoặc dữ liệu bắt buộc.";
  byId("quality-score").textContent = quality.score;
  byId("quality-grade").textContent = quality.grade;
  byId("quality-ring").style.setProperty("--quality", Math.max(0, Math.min(100, quality.score)));
  setRuntimeState(actionable ? "ready" : "blocked");

  const health = byId("data-health");
  health.replaceChildren();
  const hoseCrosscheck = data.market_history?.quality?.official_hose_crosscheck;
  const marketReconciled = hoseCrosscheck?.matched === true;
  const items = [
    [quality.source_count > 0 ? "is-good" : "is-bad", quality.source_count > 0 ? "✓" : "!", "Nguồn snapshot", `${quality.source_count} nguồn đúng registry · phủ ${quality.source_coverage_pct || 0}%`],
    [marketReconciled ? "is-good" : "is-warn", marketReconciled ? "✓" : "!", "Đối chiếu HOSE", marketReconciled ? "Giá tham chiếu/đóng cửa, % và tổng KL khớp 2/2 mã" : hoseCrosscheck?.available ? "Có chênh lệch giữa HOSE và nguồn phụ" : "Chưa đủ điều kiện đối chiếu HOSE"],
    [quality.is_stale ? "is-bad" : "is-good", quality.is_stale ? "!" : "✓", "Độ mới", quality.is_stale ? "Có nguồn quá hạn khi mở trang" : `Snapshot ${quality.age_days === 0 ? "trong ngày" : `${quality.age_days} ngày trước`}`],
    [actionable ? "is-good" : "is-warn", actionable ? "✓" : "…", "Khả năng hành động", actionable ? "Đã qua cổng dữ liệu và scorecard" : dataReady ? "Dữ liệu đạt; scorecard từng tài sản chưa đủ" : `${assets.filter((item) => item.decision_status === "READY").length}/${assets.length} nhóm đạt cổng dữ liệu`],
  ];
  items.forEach(([tone, symbol, title, detail]) => {
    const card = document.createElement("article");
    card.className = `health-item ${tone}`;
    const icon = document.createElement("span");
    icon.className = "health-symbol";
    icon.textContent = symbol;
    const text = document.createElement("div");
    const strong = document.createElement("strong");
    strong.textContent = title;
    const small = document.createElement("small");
    small.textContent = detail;
    text.append(strong, small);
    card.append(icon, text);
    health.append(card);
  });
}

function renderSummary(data) {
  const container = byId("summary");
  container.replaceChildren();
  const currentFields = verifiedFieldsFor(data, data.latest);
  const marketDate = currentFields.has("market_date") ? data.latest.market_date : null;
  const topRate = data.decision.savings?.eligible_products?.[0];
  addMetric(container, {
    label: "VN-Index",
    value: currentFields.has("vnindex.close") ? fmt(data.latest.vnindex?.close) : "Chưa xác minh",
    detail: currentFields.has("vnindex.close") ? fmt(data.latest.vnindex?.change_pct, "% trong phiên") : "Snapshot chưa gắn nguồn đúng field",
    tone: data.latest.vnindex?.change_pct < 0 ? "negative" : "muted",
    verified: currentFields.has("vnindex.close"),
  });
  for (const symbol of ["VCB", "CTD"]) {
    const key = symbol.toLowerCase();
    const snapshot = data.latest[key] || {};
    const hasClose = currentFields.has(`${key}.close`);
    const hasChange = currentFields.has(`${key}.change_pct`);
    const hasVolume = currentFields.has(`${key}.volume_million_shares`);
    addMetric(container, {
      label: `${symbol} · HOSE ${formatIsoDate(marketDate)}`,
      value: hasClose ? fmtInteger(snapshot.close, " đ") : "Chưa xác minh",
      detail: hasChange && hasVolume ? `${snapshot.change_pct >= 0 ? "+" : ""}${number.format(snapshot.change_pct)}% · KL ${fmt(snapshot.volume_million_shares, " triệu cp")}` : "Thiếu giá/khối lượng HOSE đã duyệt",
      tone: snapshot.change_pct < 0 ? "negative" : "positive",
      verified: hasClose && hasChange && hasVolume,
    });
  }
  addMetric(container, {
    label: "Vàng SJC",
    value: currentFields.has("gold.sjc_sell") ? fmt(data.latest.gold?.sjc_sell, " triệu/lượng") : "Chưa xác minh",
    detail: currentFields.has("gold.observed_at") ? `Lúc ${formatDateTime(data.latest.gold?.observed_at)}` : "Thiếu thời điểm và nguồn giá vàng",
    verified: currentFields.has("gold.sjc_sell") && currentFields.has("gold.observed_at"),
  });
  addMetric(container, {
    label: "Lãi suất đủ điều kiện",
    value: topRate && data.decision.savings.decision_status === "READY" ? fmt(topRate.rate_pct, "%/năm") : "Chưa xác minh",
    detail: topRate && data.decision.savings.decision_status === "READY" ? `${topRate.bank} · ${topRate.term_months} tháng` : "Không dùng mức cũ chưa có nguồn để quyết định",
    verified: Boolean(topRate && data.decision.savings.decision_status === "READY"),
  });
}

function stockChartSvg(symbol, rows) {
  const width = 680, height = 230, left = 44, right = 12, top = 12, priceBottom = 155, volumeTop = 170, volumeBottom = 207;
  const prices = rows.map((row) => row.close_vnd);
  const volumes = rows.map((row) => row.matched_volume);
  let min = Math.min(...prices), max = Math.max(...prices);
  const pricePadding = Math.max((max - min) * .12, max * .01);
  min -= pricePadding; max += pricePadding;
  const maxVolume = Math.max(...volumes, 1);
  const x = (index) => left + index * (width - left - right) / Math.max(1, rows.length - 1);
  const y = (value) => top + (max - value) * (priceBottom - top) / Math.max(1, max - min);
  const line = rows.map((row, index) => `${index ? "L" : "M"}${x(index).toFixed(1)},${y(row.close_vnd).toFixed(1)}`).join(" ");
  const area = `${line} L${x(rows.length - 1).toFixed(1)},${priceBottom} L${x(0).toFixed(1)},${priceBottom} Z`;
  const barWidth = Math.max(2, (width - left - right) / rows.length * .58);
  const grid = [0, .5, 1].map((ratio) => {
    const value = max - (max - min) * ratio;
    const yy = y(value);
    return `<line class="chart-grid" x1="${left}" x2="${width - right}" y1="${yy}" y2="${yy}"/><text class="chart-label" x="2" y="${yy + 4}">${number.format(value / 1000)}</text>`;
  }).join("");
  const bars = rows.map((row, index) => {
    const barHeight = row.matched_volume / maxVolume * (volumeBottom - volumeTop);
    return `<rect class="chart-volume" x="${(x(index) - barWidth / 2).toFixed(1)}" y="${(volumeBottom - barHeight).toFixed(1)}" width="${barWidth.toFixed(1)}" height="${barHeight.toFixed(1)}"><title>${formatIsoDate(row.date)} · ${integer.format(row.matched_volume)} cp</title></rect>`;
  }).join("");
  const lastX = x(rows.length - 1), lastY = y(rows.at(-1).close_vnd);
  const xLabels = [0, Math.floor((rows.length - 1) / 2), rows.length - 1].map((index) => `<text class="chart-label" text-anchor="${index === 0 ? "start" : index === rows.length - 1 ? "end" : "middle"}" x="${x(index)}" y="226">${rows[index].date.slice(5).split("-").reverse().join("/")}</text>`).join("");
  return `<svg viewBox="0 0 ${width} ${height}" role="img" aria-labelledby="${symbol}-chart-title ${symbol}-chart-desc">
    <title id="${symbol}-chart-title">Giá và khối lượng ${symbol} trong ${rows.length} phiên</title>
    <desc id="${symbol}-chart-desc">Đường biểu diễn giá đóng cửa; cột biểu diễn khối lượng khớp lệnh theo ngày.</desc>
    <defs><linearGradient id="${symbol}-area" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="var(--brand)" stop-opacity=".42"/><stop offset="1" stop-color="var(--brand)" stop-opacity="0"/></linearGradient></defs>
    ${grid}<path d="${area}" fill="url(#${symbol}-area)"/><path class="chart-line" d="${line}"/>${bars}
    <circle class="chart-dot" cx="${lastX}" cy="${lastY}" r="4.5"><title>${formatIsoDate(rows.at(-1).date)} · ${integer.format(rows.at(-1).close_vnd)} đ</title></circle>${xLabels}
  </svg>`;
}

function renderStockLabs(data) {
  const container = byId("stock-labs");
  container.replaceChildren();
  for (const symbol of ["VCB", "CTD"]) {
    const stats = stockStats(data, symbol);
    const hoseSymbol = data.market_history?.quality?.official_hose_crosscheck?.symbols?.find((item) => item.symbol === symbol);
    const article = document.createElement("article");
    article.className = "stock-lab";
    if (!stats) {
      article.textContent = `${symbol}: chưa có chuỗi lịch sử đủ để vẽ biểu đồ.`;
      container.append(article);
      continue;
    }
    const intraday = stats.intraday;
    const atcPct = intraday ? safePercent(intraday.atc_volume, intraday.total_volume) : null;
    const directional = intraday ? intraday.uptick_volume + intraday.downtick_volume : 0;
    const upPct = directional ? intraday.uptick_volume / directional * 100 : 50;
    const downPct = directional ? 100 - upPct : 50;
    const closeAtLow = Number.isFinite(stats.closePosition) && stats.closePosition <= 5;
    article.innerHTML = `<div class="stock-lab-head">
      <div class="ticker-title"><span class="ticker-badge">${symbol}</span><div><h3>${symbol === "VCB" ? "Vietcombank" : "Coteccons"}</h3><p>Nguồn phụ trợ · ${hoseSymbol?.matched ? "đã khớp giá, % thay đổi và tổng KL HOSE" : "chưa khớp đủ với HOSE"}</p></div></div>
      <div class="stock-price"><strong>${integer.format(stats.latest.close_vnd)} đ</strong><span class="${stats.latest.change_pct < 0 ? "negative" : "positive"}">${stats.latest.change_pct >= 0 ? "+" : ""}${number.format(stats.latest.change_pct)}% trong phiên</span></div>
    </div>
    <div class="chart-shell">${stockChartSvg(symbol, stats.rows)}</div>
    <div class="stock-stats">
      <div class="stock-stat"><small>Biến động chuỗi</small><strong class="${stats.returnWindowPct < 0 ? "negative" : "positive"}">${stats.returnWindowPct >= 0 ? "+" : ""}${number.format(stats.returnWindowPct)}%</strong></div>
      <div class="stock-stat"><small>KL / BQ 19 phiên trước</small><strong>${Number.isFinite(stats.volumeRatio) ? `${number.format(stats.volumeRatio)}×` : "Cần đủ 20 phiên"}</strong></div>
      <div class="stock-stat"><small>ATC / tổng KL</small><strong>${Number.isFinite(atcPct) ? `${number.format(atcPct)}%` : "—"}</strong></div>
      <div class="stock-stat"><small>Vị trí đóng cửa</small><strong>${closeAtLow ? "Sát đáy ngày" : Number.isFinite(stats.closePosition) ? `${number.format(stats.closePosition)}% biên ngày` : "—"}</strong></div>
    </div>
    <div class="pressure">
      <div class="pressure-side"><small>Nến tăng</small><strong>${intraday ? fmtCompact(intraday.uptick_volume, " cp") : "—"}</strong></div>
      <span class="pill pill-neutral">tick rule</span>
      <div class="pressure-side"><small>Nến giảm</small><strong>${intraday ? fmtCompact(intraday.downtick_volume, " cp") : "—"}</strong></div>
      <div class="pressure-track"><span class="pressure-up" style="width:${upPct}%"></span><span class="pressure-down" style="width:${downPct}%"></span></div>
    </div>
    <p class="stock-note">${intraday?.reconciled_with_daily ? "✓ Tổng nến phút khớp tổng khối lượng ngày." : "⚠ Chưa đối soát được tổng khối lượng."} Nến phút không phải từng lệnh và không chứng minh gom/xả.</p>`;
    container.append(article);
  }

  const comparison = byId("market-comparison");
  const vcb = stockStats(data, "VCB"), ctd = stockStats(data, "CTD");
  if (!vcb || !ctd) {
    comparison.textContent = "Chưa đủ dữ liệu so sánh VCB và CTD.";
    return;
  }
  const relativeLabel = vcb.latest.change_pct < 0 && ctd.latest.change_pct < 0 ? "Giảm ít hơn trong phiên" : "Hiệu suất tốt hơn trong phiên";
  comparison.innerHTML = `<div class="panel-heading"><div><p class="eyebrow">ĐỐI CHIẾU NHANH</p><h2>VCB so với CTD</h2></div><span class="pill pill-neutral">Nguồn phụ · ${formatIsoDate(data.market_history.market_date)}</span></div>
    <div class="comparison-grid">
      <div class="comparison-cell"><small>${relativeLabel}</small><strong>${vcb.latest.change_pct > ctd.latest.change_pct ? "VCB" : "CTD"}</strong></div>
      <div class="comparison-cell"><small>VCB · biến động chuỗi</small><strong>${number.format(vcb.returnWindowPct)}%</strong></div>
      <div class="comparison-cell"><small>CTD · biến động chuỗi</small><strong>${number.format(ctd.returnWindowPct)}%</strong></div>
      <div class="comparison-cell"><small>VCB · KL so BQ</small><strong>${number.format(vcb.volumeRatio)}×</strong></div>
      <div class="comparison-cell"><small>CTD · KL so BQ</small><strong>${number.format(ctd.volumeRatio)}×</strong></div>
    </div>`;
}

function decisionCard(item, modelValidated) {
  const dataReady = item.decision_status === "READY";
  const actionable = dataReady && modelValidated;
  const card = document.createElement("article");
  card.className = `decision-card ${actionable ? "is-ready" : "is-wait"}`;
  const blockers = [...(item.hard_blockers || []).map(humanizeFieldText), ...(item.missing_data || []).map((text) => `Thiếu: ${humanizeFieldText(text)}`)];
  if (dataReady && !modelValidated) blockers.unshift("Scorecard chưa đủ 20 kết quả độc lập cho từng nhóm Vàng, VCB và CTD");
  const status = actionable ? item.signal : dataReady ? "Chờ kiểm chứng" : "Chờ dữ liệu";
  const safeAction = actionable
    ? (item.action || "Tiếp tục kiểm tra điều kiện cá nhân trước khi hành động.")
    : dataReady ? "Chưa hành động. Dữ liệu đã đủ nhưng mô hình chưa được kiểm chứng riêng cho từng tài sản."
      : "Chưa hành động. Hoàn thiện các dữ liệu bắt buộc bên dưới trước khi xem xét tài sản này.";
  card.innerHTML = `<div class="decision-top"><div><h3>${item.name}</h3><span class="decision-status">${status}</span></div>${actionable ? `<span class="decision-score">${item.score}<small>/100</small></span>` : ""}</div>
    ${actionable ? `<div class="confidence-row"><span>Độ phủ dữ liệu</span><span>${item.confidence}/100</span></div><div class="confidence-bar"><span style="width:${Math.max(0, Math.min(100, item.confidence))}%"></span></div>` : `<div class="decision-lock">Điểm và độ tin cậy đang bị khóa</div>`}
    <p class="decision-action">${safeAction}</p>`;
  const details = document.createElement("details");
  const summary = document.createElement("summary");
  summary.textContent = actionable ? "Luận điểm, rủi ro và điểm dừng" : `Cách mở khóa · ${blockers.length} mục`;
  const list = document.createElement("ul");
  const rows = actionable
    ? [...(item.reasons || []).map((text) => `Dữ kiện: ${text}`), ...(item.risks || []).map((text) => `Rủi ro: ${text}`), ...(item.invalidation || []).map((text) => `Dừng nếu: ${text}`)]
    : blockers;
  (rows.length ? rows : ["Chưa có hướng dẫn bổ sung dữ liệu."]).forEach((text) => { const li = document.createElement("li"); li.textContent = text; list.append(li); });
  details.append(summary, list);
  card.append(details);
  return card;
}

function renderDecisions(data) {
  const main = byId("asset-decisions");
  const stocks = byId("stock-decisions");
  main.replaceChildren(); stocks.replaceChildren();
  const modelValidated = data.runtime?.gates?.modelValidated === true;
  const stockClass = data.decision.asset_classes.find((item) => item.id === "stocks");
  [data.decision.savings, data.decision.gold, stockClass].forEach((item) => main.append(decisionCard(item, modelValidated)));
  data.decision.stocks.forEach((item) => stocks.append(decisionCard(item, modelValidated)));
}

function normalizedWeights(weights) {
  const total = Object.values(weights).reduce((sum, value) => sum + value, 0);
  return Object.fromEntries(Object.entries(weights).map(([key, value]) => [key, total ? value / total * 100 : 0]));
}

function cappedStockWeights(totalWeight, stocks, cap) {
  const allocations = Object.fromEntries(stocks.map((item) => [item.id, 0]));
  let remaining = Math.max(0, totalWeight);
  let active = [...stocks];
  for (let pass = 0; pass < stocks.length + 2 && remaining > .0001 && active.length; pass += 1) {
    const signalTotal = active.reduce((sum, item) => sum + Math.max(1, item.score || 0), 0);
    let distributed = 0;
    for (const item of active) {
      const capacity = Math.max(0, cap - allocations[item.id]);
      const proposed = remaining * Math.max(1, item.score || 0) / signalTotal;
      const addition = Math.min(capacity, proposed);
      allocations[item.id] += addition;
      distributed += addition;
    }
    remaining -= distributed;
    active = active.filter((item) => allocations[item.id] < cap - .0001);
    if (distributed <= .0001) break;
  }
  return { allocations, unallocated: Math.max(0, remaining) };
}

function renderScenario(data) {
  const form = byId("scenario-form");
  const calculate = () => {
    const capital = Math.max(0, Number(byId("capital").value) || 0);
    const reserveInput = Math.max(0, Number(byId("reserve").value) || 0);
    const reserve = Math.min(capital, reserveInput);
    if (reserveInput > capital) byId("reserve").value = String(capital);
    const investable = Math.max(0, capital - reserve);
    const classes = Object.fromEntries(data.decision.asset_classes.map((item) => [item.id, item]));
    const dataReady = data.runtime?.gates?.dataReady === true;
    const modelValidated = data.runtime?.gates?.modelValidated === true;
    const output = byId("allocation");
    output.replaceChildren();

    if (!dataReady || !modelValidated || investable <= 0) {
      [["Gửi tiết kiệm", "Cần sản phẩm đủ điều kiện"], ["Vàng", "Cần giá đồng thời và mức chênh lệch"], ["Cổ phiếu", "Cần dữ liệu cơ bản và mô hình đủ mẫu"]].forEach(([label, reason]) => {
        const card = document.createElement("div");
        card.className = "allocation-card";
        card.innerHTML = `<strong>${label}</strong><span>Chưa mở khóa</span><small>${reason}</small>`;
        output.append(card);
      });
      byId("allocation-note").textContent = investable <= 0
        ? "Quỹ dự phòng đang bằng tổng vốn; không còn vốn mô phỏng."
        : !dataReady ? "Không hiển thị tỷ trọng hoặc số tiền để tránh tạo điểm neo khi dữ liệu chưa đủ."
          : "Dữ liệu đã đủ nhưng scorecard chưa đạt tối thiểu 20 kết quả riêng cho Vàng, VCB và CTD; chưa hiển thị số tiền.";
      return;
    }

    const goal = byId("goal").value;
    const horizon = Number(byId("horizon").value);
    const liquidity = byId("liquidity").value;
    const bases = { conservative: { savings: 70, gold: 20, stocks: 10 }, balanced: { savings: 50, gold: 20, stocks: 30 }, growth: { savings: 35, gold: 20, stocks: 45 } };
    const weights = { ...bases[goal] };
    if (horizon < 12) { weights.savings += 15; weights.stocks -= 15; }
    if (horizon >= 60) { weights.stocks += 5; weights.savings -= 5; }
    if (liquidity === "high") { weights.savings += 10; weights.stocks -= 10; }
    Object.keys(weights).forEach((id) => { weights[id] = Math.max(0, weights[id] * (.85 + classes[id].score / 200)); });
    const finalWeights = normalizedWeights(weights);
    const maxSingle = data.decision.profile.max_single_stock_pct || 20;
    const stockSplit = cappedStockWeights(finalWeights.stocks, data.decision.stocks, maxSingle);
    finalWeights.savings += stockSplit.unallocated;
    finalWeights.stocks = Object.values(stockSplit.allocations).reduce((sum, value) => sum + value, 0);
    const rows = [
      ["savings", "Gửi tiết kiệm", finalWeights.savings],
      ["gold", "Vàng", finalWeights.gold],
      ...data.decision.stocks.map((item) => [item.id, item.name, stockSplit.allocations[item.id] || 0]),
    ];
    rows.forEach(([id, label, weight]) => {
      const card = document.createElement("div");
      card.className = "allocation-card";
      const capNote = id === "vcb" || id === "ctd" ? `Đã áp trần ${maxSingle}% vốn sau dự phòng/mã` : "Chỉ là kịch bản có điều kiện";
      card.innerHTML = `<strong>${label}</strong><span>${number.format(weight)}% · ${fmtInteger(investable * weight / 100, " đ")}</span><small>${capNote}</small>`;
      output.append(card);
    });
    byId("allocation-note").textContent = `Vốn mô phỏng sau dự phòng: ${fmtInteger(investable, " đ")}. VCB và CTD được tính riêng; không mã nào vượt ${maxSingle}% phần vốn này.`;
  };
  form.addEventListener("submit", (event) => { event.preventDefault(); calculate(); });
  ["capital", "reserve"].forEach((id) => byId(id).addEventListener("blur", () => { const value = Number(byId(id).value); if (Number.isFinite(value)) byId(id).title = `${integer.format(value)} đồng`; }));
  calculate();
}

function renderPortfolio(data) {
  const container = byId("portfolio");
  container.replaceChildren();
  const form = document.createElement("form");
  form.className = "portfolio-form";
  const fields = verifiedFieldsFor(data, data.latest);
  for (const ticker of ["VCB", "CTD"]) {
    const position = privatePortfolio[ticker] || {};
    const price = fields.has(`${ticker.toLowerCase()}.close`) ? get(data.latest, ticker.toLowerCase(), "close") : null;
    const group = document.createElement("fieldset");
    const legend = document.createElement("legend");
    legend.textContent = `${ticker} · giá tham chiếu ${fmtInteger(price, " đ")}`;
    const cost = document.createElement("input");
    cost.type = "number"; cost.min = "0"; cost.step = "100"; cost.placeholder = "Giá vốn"; cost.value = position.avg_cost || ""; cost.dataset.ticker = ticker; cost.dataset.field = "avg_cost"; cost.setAttribute("aria-label", `Giá vốn ${ticker}`);
    const quantity = document.createElement("input");
    quantity.type = "number"; quantity.min = "0"; quantity.step = "1"; quantity.placeholder = "Số lượng"; quantity.value = position.quantity || ""; quantity.dataset.ticker = ticker; quantity.dataset.field = "quantity"; quantity.setAttribute("aria-label", `Số lượng ${ticker}`);
    group.append(legend, cost, quantity); form.append(group);
    if (Number.isFinite(position.avg_cost) && Number.isFinite(position.quantity) && Number.isFinite(price)) {
      const pnl = (price - position.avg_cost) * position.quantity;
      const pct = (price - position.avg_cost) / position.avg_cost * 100;
      addStackItem(container, `${ticker} tạm tính`, "Trước phí, thuế và cổ tức", `${pnl >= 0 ? "+" : "−"}${integer.format(Math.abs(pnl))} đ · ${number.format(pct)}%`, pnl >= 0 ? "positive" : "negative");
    }
  }
  const submit = document.createElement("button"); submit.type = "submit"; submit.textContent = "Tính tạm";
  const clear = document.createElement("button"); clear.type = "button"; clear.textContent = "Xóa";
  form.append(submit, clear);
  form.addEventListener("submit", (event) => {
    event.preventDefault(); privatePortfolio = {};
    for (const ticker of ["VCB", "CTD"]) {
      const avgCost = Number(form.querySelector(`[data-ticker="${ticker}"][data-field="avg_cost"]`).value);
      const quantity = Number(form.querySelector(`[data-ticker="${ticker}"][data-field="quantity"]`).value);
      privatePortfolio[ticker] = { avg_cost: avgCost > 0 ? avgCost : null, quantity: quantity > 0 ? quantity : null };
    }
    renderPortfolio(data);
  });
  clear.addEventListener("click", () => { privatePortfolio = {}; renderPortfolio(data); });
  container.prepend(form);
  const note = document.createElement("p"); note.className = "empty"; note.textContent = "Không lưu lên máy chủ; tải lại trang sẽ xóa toàn bộ."; container.append(note);
}

function renderScorecard(scorecard) {
  const container = byId("scorecard");
  container.replaceChildren();
  const assetLabels = { gold: "Vàng", vcb: "VCB", ctd: "CTD" };
  const items = [["Cổng mô hình", scorecard.status === "READY" ? "Đủ mẫu từng tài sản" : "Chưa đủ mẫu"]];
  for (const assetId of ["gold", "vcb", "ctd"]) {
    const result = scorecard.asset_results?.[assetId];
    items.push([assetLabels[assetId], result ? `${result.assessed}/${result.minimum_assessed} kết quả` : "Chưa có scorecard riêng"]);
  }
  items.forEach(([label, value]) => {
    const card = document.createElement("div"); card.className = "scorecard-item"; const small = document.createElement("small"); small.textContent = label; const strong = document.createElement("strong"); strong.textContent = value; card.append(small, strong); container.append(card);
  });
}

function renderRatesAndRisks(data) {
  const rates = byId("rates"); rates.replaceChildren();
  const products = data.decision.savings.eligible_products || [];
  products.slice(0, 5).forEach((item) => addStackItem(rates, item.bank, `${item.term_months} tháng · ${fmtCompact(item.minimum_amount_vnd)}–${fmtCompact(item.maximum_amount_vnd)}`, fmt(item.rate_pct, "%/năm")));
  if (!products.length) rates.textContent = "Chưa có sản phẩm đủ điều kiện số tiền, kỳ hạn và nguồn để so sánh.";
  const limit = data.decision.profile.deposit_insurance_limit_vnd || 0;
  byId("insurance-note").textContent = `Hạn mức bảo hiểm theo cấu hình: tối đa ${fmtCompact(limit, " đồng/người/tổ chức tham gia")}, gồm cả gốc và lãi. Kiểm tra lại chính sách trước khi gửi.`;

  const risks = byId("risks"); risks.replaceChildren();
  const labels = { arrest: "Doanh nghiệp", war: "Địa chính trị", trump: "Chính sách Mỹ", fed: "Fed" };
  const verified = Object.entries(data.decision.verified_risks || {}).filter(([, value]) => value);
  verified.forEach(([key, value]) => addStackItem(risks, labels[key] || key, String(value), "Theo dõi"));
  if (!verified.length) risks.textContent = "Chưa có cờ rủi ro nào đủ nguồn kiểm chứng để tác động điểm số.";
}

function renderHistory(data) {
  const body = byId("history"); body.replaceChildren();
  [...data.history].reverse().slice(0, 30).forEach((item) => {
    const fields = verifiedFieldsFor(data, item);
    const value = (field, ...path) => fieldIsVerified(fields, field) ? get(item, ...path) : null;
    const values = [`${period(item)} · ${fields.size ? "có nguồn một phần" : "chưa gắn nguồn"}`, fmt(value("vnindex.close", "vnindex", "close")), fmtInteger(value("vcb.close", "vcb", "close"), " đ"), fmtInteger(value("ctd.close", "ctd", "close"), " đ"), fmt(value("gold.xauusd", "gold", "xauusd"), " $"), fmt(value("foreign_net_ty", "foreign_net_ty"), " tỷ")];
    const tr = document.createElement("tr"); values.forEach((text, index) => { const td = document.createElement("td"); td.textContent = text; if (index) td.className = "number"; tr.append(td); }); body.append(tr);
  });
}

function renderMethodology(data) {
  const guardrails = byId("guardrails"); guardrails.replaceChildren();
  data.decision.guardrails.forEach((text) => { const li = document.createElement("li"); li.textContent = text; guardrails.append(li); });
  const sources = byId("sources"); sources.replaceChildren();
  const verified = data.decision.verified_sources || [];
  verified.forEach((source) => {
    const row = document.createElement("div");
    const link = document.createElement("a"); link.href = source.url; link.target = "_blank"; link.rel = "noopener noreferrer"; link.textContent = source.name;
    const detail = document.createElement("small"); detail.textContent = `Mở khóa: ${source.fields.length} trường · lấy ${formatDateTime(source.retrieved_at)}`;
    row.append(link, document.createTextNode(" — "), detail); sources.append(row);
  });
  (data.market_history?.sources || []).forEach((source) => {
    const row = document.createElement("div"); const link = document.createElement("a"); link.href = source.url; link.target = "_blank"; link.rel = "noopener noreferrer"; link.textContent = source.name; const detail = document.createElement("small"); detail.textContent = `Nguồn phụ trợ: ${source.role} · không mở khóa quyết định`; row.append(link, document.createTextNode(" — "), detail); sources.append(row);
  });
  if (!sources.childElementCount) sources.textContent = "Chưa có nguồn được gắn vào snapshot.";
}

function renderHeader(data) {
  const marketDate = data.latest.market_date;
  byId("updated").textContent = `Snapshot đã duyệt ${formatDateTime(data.latest.collected_at)} · kiểm tra lại khi mở ${formatDateTime(new Date().toISOString())}`;
  byId("market-date").textContent = `HOSE ${formatIsoDate(marketDate)}`;
  const hoseCrosscheck = data.market_history?.quality?.official_hose_crosscheck;
  byId("market-reconcile").textContent = hoseCrosscheck?.matched ? "HOSE ↔ nguồn phụ khớp 2/2" : "Nguồn phụ chưa khớp HOSE";
  byId("period-badge").textContent = `HOSE · ${formatIsoDate(marketDate)}`;
}

async function start() {
  try {
    const response = await fetch("./data.json", { cache: "no-store" });
    if (!response.ok) throw new Error(`Không đọc được data.json (${response.status})`);
    const data = await response.json();
    if (!data.latest || !Array.isArray(data.history) || !data.decision || !data.scorecard || !data.source_registry) throw new Error("Dữ liệu dashboard không đúng định dạng");
    applyRuntimeFreshness(data);
    renderHeader(data);
    renderSystemStatus(data);
    renderDecisions(data);
    renderSummary(data);
    renderStockLabs(data);
    renderScenario(data);
    renderPortfolio(data);
    renderScorecard(data.scorecard);
    renderRatesAndRisks(data);
    renderHistory(data);
    renderMethodology(data);
  } catch (error) {
    setRuntimeState("error");
    const alert = byId("error");
    alert.hidden = false;
    alert.textContent = "Dashboard chưa tải được dữ liệu. Vui lòng thử tải lại trang sau ít phút.";
    byId("updated").textContent = "Không thể tải dữ liệu";
    byId("gate-title").textContent = "LỖI DỮ LIỆU — không được dùng dashboard để quyết định";
    byId("gate-message").textContent = "Không thể kiểm tra nguồn và độ mới; mọi mô phỏng phải dừng.";
    document.querySelectorAll("#scenario-form input, #scenario-form select, #scenario-form button").forEach((node) => { node.disabled = true; });
    console.error(error);
  }
}

let savedTheme = null;
try { savedTheme = localStorage.getItem("finance-theme"); } catch (_) { /* Trình duyệt chặn lưu cục bộ */ }
if (savedTheme) document.documentElement.dataset.theme = savedTheme;
byId("theme-toggle").addEventListener("click", () => {
  const next = document.documentElement.dataset.theme === "dark" ? "light" : "dark";
  document.documentElement.dataset.theme = next;
  document.querySelector('meta[name="theme-color"]').content = next === "dark" ? "#0c1511" : "#f5f4ef";
  try { localStorage.setItem("finance-theme", next); } catch (_) { /* Không ảnh hưởng chức năng */ }
});

start();
