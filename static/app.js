const chartData = {
  revenue: {
    eyebrow: "財務成效",
    headline: "營收成長提供背景，但不能直接等同於數位轉型成效",
    body:
      "2024 年與 2025 年營收皆維持約 7% 年增，代表整體經營表現良好。不過，展店、店型改裝、商品結構與自有品牌也會影響營收，因此更適合作為轉型背景，而不是單一歸因證據。",
    labels: ["2024", "2025"],
    bars: [
      { label: "營收", values: [236.28, 253.2], unit: "億元", color: "#c84f7a" },
      { label: "年增率", values: [7.02, 7.16], unit: "%", color: "#2b8d8b" },
    ],
    notes: ["2025 年營收 253.20 億元，年增 7.16%。", "2024 年營收 236.28 億元，年增 7.02%。"],
  },
  commerce: {
    eyebrow: "全通路成效",
    headline: "電商占比小，真正價值在把線上流量導回門市",
    body:
      "電商營收占比約 2.2%，目前還不是主要營收來源；但電商年增近五成，且線上訂單約五成選擇門市取貨，代表數位通路能延長接觸時間並創造到店加購機會。",
    labels: ["電商占比", "門市取貨", "電商年增"],
    bars: [
      { label: "比例", values: [2.2, 50, 48], unit: "%", color: "#7a5aa6" },
    ],
    notes: ["電商占整體營收約 2.2%。", "線上訂單約五成選擇門市取貨。", "電商營收年增近五成。"],
  },
  member: {
    eyebrow: "會員成效",
    headline: "金卡會員人數占比不高，卻貢獻接近四成營收",
    body:
      "金卡會員約占會員數 11%，卻貢獻接近 40% 營收。這組落差說明數位會員制度的價值，不只是註冊人數，而是辨識高價值顧客並推動回購。",
    labels: ["金卡會員占比", "金卡營收貢獻"],
    bars: [
      { label: "比例", values: [11, 40], unit: "%", color: "#b8862f" },
    ],
    notes: ["金卡會員約占會員數 11%。", "金卡會員貢獻營收接近 40%。"],
  },
};

const journeyData = {
  digital: [
    ["認識品牌", "APP 推播、社群、線上 DM、線上活動讓品牌在顧客進店前就出現。"],
    ["搜尋商品", "顧客可先查優惠、看線上商品、領券，縮短到店決策時間。"],
    ["購買決策", "線上比價、活動資訊與優惠券讓導購不只發生在貨架前。"],
    ["付款結帳", "POYA Pay、自助結帳與會員點數累積讓交易更完整可識別。"],
    ["購後回饋", "APP 點數、優惠券、生日禮與會員日把購後互動留在同一個入口。"],
    ["再次回購", "APP 推播、分眾優惠、線上買與門市取貨，把顧客帶回下一次消費。"],
  ],
  traditional: [
    ["認識品牌", "看到門市、紙本 DM 或廣告，接觸點多半由地點與促銷決定。"],
    ["搜尋商品", "到店後才知道商品、庫存與優惠，購買前資訊相對有限。"],
    ["購買決策", "主要靠現場比較價格、包裝與促銷陳列。"],
    ["付款結帳", "櫃台排隊、現金或卡片交易，會員識別與交易資料較分散。"],
    ["購後回饋", "紙本發票、實體會員卡與單次促銷，後續接觸較弱。"],
    ["再次回購", "靠門市距離與下一次促銷吸引，較難主動經營個別顧客。"],
  ],
};

const simulatorPresets = {
  base: { member: 82, gold: 88, omo: 78, commerce: 34, experience: 58, risk: 42 },
  member: { member: 94, gold: 96, omo: 84, commerce: 28, experience: 70, risk: 36 },
  ecommerce: { member: 48, gold: 46, omo: 42, commerce: 82, experience: 44, risk: 58 },
};

const simulatorLabels = {
  member: "會員資料",
  gold: "金卡會員",
  omo: "OMO 導流",
  commerce: "電商營收",
  experience: "APP 體驗",
  risk: "促銷風險",
};

const canvas = document.getElementById("insightChart");
const insightPanel = document.getElementById("chartInsight");
const chartButtons = document.querySelectorAll("[data-chart]");
const journeyButtons = document.querySelectorAll("[data-journey]");
const journeyTrack = document.getElementById("journeyTrack");
const simulatorInputs = document.querySelectorAll("[data-driver]");
const presetButtons = document.querySelectorAll("[data-preset]");
const simulatorScore = document.getElementById("simulatorScore");
const simulatorVerdict = document.getElementById("simulatorVerdict");
const simulatorSummary = document.getElementById("simulatorSummary");
const driverStack = document.getElementById("driverStack");

function formatValue(value, unit) {
  const digits = value < 10 && value % 1 !== 0 ? 2 : value % 1 === 0 ? 0 : 1;
  return `${value.toLocaleString("zh-TW", { maximumFractionDigits: digits, minimumFractionDigits: digits })}${unit}`;
}

function setCanvasSize(ctx) {
  const ratio = window.devicePixelRatio || 1;
  const width = canvas.clientWidth;
  const height = canvas.clientHeight;
  canvas.width = Math.floor(width * ratio);
  canvas.height = Math.floor(height * ratio);
  ctx.setTransform(ratio, 0, 0, ratio, 0, 0);
  return { width, height };
}

function drawChart(key) {
  const data = chartData[key];
  const ctx = canvas.getContext("2d");
  const { width, height } = setCanvasSize(ctx);
  ctx.clearRect(0, 0, width, height);

  const pad = {
    left: width < 560 ? 44 : 70,
    right: width < 560 ? 18 : 34,
    top: 36,
    bottom: width < 560 ? 70 : 54,
  };
  const plotWidth = width - pad.left - pad.right;
  const plotHeight = height - pad.top - pad.bottom;
  const allValues = data.bars.flatMap((series) => series.values);
  const max = Math.max(...allValues) * 1.18;

  ctx.strokeStyle = "#eadfe5";
  ctx.lineWidth = 1;
  ctx.fillStyle = "#6d6269";
  ctx.font = "13px Microsoft JhengHei, sans-serif";

  for (let i = 0; i <= 4; i += 1) {
    const y = pad.top + plotHeight - (plotHeight * i) / 4;
    ctx.beginPath();
    ctx.moveTo(pad.left, y);
    ctx.lineTo(width - pad.right, y);
    ctx.stroke();
    ctx.fillText(Math.round((max * i) / 4).toString(), 8, y + 4);
  }

  const groupWidth = plotWidth / data.labels.length;
  const barGap = data.bars.length > 1 ? 8 : 0;
  const barWidth = Math.min(58, Math.max(28, (groupWidth - 36) / data.bars.length - barGap));

  data.labels.forEach((label, labelIndex) => {
    const groupCenter = pad.left + groupWidth * labelIndex + groupWidth / 2;
    const groupStart = groupCenter - ((barWidth + barGap) * data.bars.length - barGap) / 2;

    data.bars.forEach((series, seriesIndex) => {
      const value = series.values[labelIndex];
      const x = groupStart + seriesIndex * (barWidth + barGap);
      const barHeight = (value / max) * plotHeight;
      const y = pad.top + plotHeight - barHeight;

      const gradient = ctx.createLinearGradient(0, y, 0, pad.top + plotHeight);
      gradient.addColorStop(0, series.color);
      gradient.addColorStop(1, "#f8dce8");
      ctx.fillStyle = gradient;
      ctx.beginPath();
      ctx.roundRect(x, y, barWidth, barHeight, 6);
      ctx.fill();

      ctx.fillStyle = "#221a20";
      ctx.textAlign = "center";
      ctx.font = "700 13px Microsoft JhengHei, sans-serif";
      ctx.fillText(formatValue(value, series.unit), x + barWidth / 2, y - 10);
    });

    ctx.fillStyle = "#6d6269";
    ctx.font = "700 13px Microsoft JhengHei, sans-serif";
    ctx.fillText(label, groupCenter, height - 24);
  });

  if (data.bars.length > 1) {
    let legendX = pad.left;
    data.bars.forEach((series) => {
      ctx.fillStyle = series.color;
      ctx.fillRect(legendX, 14, 12, 12);
      ctx.fillStyle = "#6d6269";
      ctx.textAlign = "left";
      ctx.font = "13px Microsoft JhengHei, sans-serif";
      ctx.fillText(series.label, legendX + 18, 25);
      legendX += 86;
    });
  }

  insightPanel.innerHTML = `
    <span>${data.eyebrow}</span>
    <strong>${data.headline}</strong>
    <p>${data.body}</p>
    <ul>${data.notes.map((note) => `<li>${note}</li>`).join("")}</ul>
  `;
}

function setActiveButton(buttons, activeButton, attr) {
  buttons.forEach((button) => {
    const active = button === activeButton;
    button.classList.toggle("active", active);
    button.setAttribute("aria-selected", active ? "true" : "false");
    button.setAttribute("tabindex", active ? "0" : "-1");
  });
  return activeButton.dataset[attr];
}

function renderJourney(mode) {
  journeyTrack.innerHTML = journeyData[mode]
    .map(
      ([title, description], index) => `
        <article class="journey-node">
          <span>${String(index + 1).padStart(2, "0")}</span>
          <h3>${title}</h3>
          <p>${description}</p>
        </article>
      `,
    )
    .join("");
}

function readSimulatorValues() {
  return [...simulatorInputs].reduce((values, input) => {
    values[input.dataset.driver] = Number(input.value);
    return values;
  }, {});
}

function setSimulatorValues(values) {
  simulatorInputs.forEach((input) => {
    input.value = values[input.dataset.driver];
  });
  updateSimulator();
}

function scoreSimulator(values) {
  const score =
    values.member * 0.22 +
    values.gold * 0.24 +
    values.omo * 0.22 +
    values.commerce * 0.1 +
    values.experience * 0.16 -
    values.risk * 0.1 +
    14;
  return Math.max(0, Math.min(100, Math.round(score)));
}

function updateSimulator() {
  if (!simulatorScore) return;

  const values = readSimulatorValues();
  const score = scoreSimulator(values);
  const relationshipValue = Math.round((values.member + values.gold + values.omo + values.experience) / 4);
  const ecommerceGap = Math.max(0, relationshipValue - values.commerce);

  simulatorScore.textContent = score;
  document.querySelector(".score-ring")?.style.setProperty("--score", score);

  if (score >= 72) {
    simulatorVerdict.textContent = "顧客經營價值明確成立";
    simulatorSummary.textContent = "會員資料、金卡會員與 OMO 導流的權重大於純電商占比。";
  } else if (score >= 56) {
    simulatorVerdict.textContent = "有價值，但仍需要改善體驗與歸因";
    simulatorSummary.textContent = "轉型已帶來接觸與導流效果，但 APP 體驗、個人化與風險管理會影響說服力。";
  } else {
    simulatorVerdict.textContent = "若只看電商，結論會偏保守";
    simulatorSummary.textContent = "當評估焦點集中在電商營收占比，寶雅目前的 2.2% 較難支持強結論。";
  }

  driverStack.innerHTML = Object.entries(values)
    .map(([key, value]) => {
      const adjusted = key === "risk" ? Math.max(0, 100 - value) : value;
      const label = key === "risk" ? `${simulatorLabels[key]}控制` : simulatorLabels[key];
      return `
        <div class="driver-row">
          <span>${label} ${key === "commerce" && ecommerceGap > 30 ? "不是唯一重點" : ""}</span>
          <div class="driver-bar"><i style="width:${adjusted}%"></i></div>
        </div>
      `;
    })
    .join("");
}

chartButtons.forEach((button) => {
  button.addEventListener("click", () => {
    const key = setActiveButton(chartButtons, button, "chart");
    drawChart(key);
  });
});

journeyButtons.forEach((button) => {
  button.addEventListener("click", () => {
    const mode = setActiveButton(journeyButtons, button, "journey");
    renderJourney(mode);
  });
});

simulatorInputs.forEach((input) => {
  input.addEventListener("input", updateSimulator);
});

presetButtons.forEach((button) => {
  button.addEventListener("click", () => {
    setSimulatorValues(simulatorPresets[button.dataset.preset]);
  });
});

const observer = new IntersectionObserver(
  (entries) => {
    entries.forEach((entry) => {
      if (entry.isIntersecting) {
        entry.target.classList.add("visible");
        observer.unobserve(entry.target);
      }
    });
  },
  { threshold: 0.16 },
);

document.querySelectorAll(".reveal").forEach((element) => observer.observe(element));

const resizeObserver = new ResizeObserver(() => {
  const active = document.querySelector("[data-chart].active")?.dataset.chart || "revenue";
  drawChart(active);
});
resizeObserver.observe(canvas);

renderJourney("digital");
drawChart("revenue");
updateSimulator();
