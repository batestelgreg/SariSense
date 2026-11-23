/* ==================================================================
   Dashboard: KPIs, trend chart, top products, restock list, assistant
   ================================================================== */
(function () {
  if (!requireLogin()) return;
  paintChrome();

  const $ = (id) => document.getElementById(id);
  let trendChart = null;

  /* ---------------- data ---------------- */
  async function load() {
    try {
      const [dash, restock] = await Promise.all([
        api("/api/dashboard"),
        api("/api/restock?days=" + ($("horizon")?.value || 7)),
      ]);
      renderKpis(dash);
      renderTrend(dash.trend);
      renderTop(dash.top_products);
      renderRestock(restock);
      renderModel(dash.model);
      $("alertBadge").textContent = dash.unverified_alerts || 0;
      $("alertBadge").style.display = dash.unverified_alerts ? "inline-block" : "none";
    } catch (e) {
      toast(e.message);
    }
  }

  /* ---------------- KPIs ---------------- */
  function renderKpis(d) {
    $("kpiRevenue").textContent = peso(d.today.revenue);
    $("kpiRevenueFoot").textContent = `${d.today.transactions} transaction(s) today`;

    $("kpiUnits").textContent = d.today.units;
    $("kpiUnitsFoot").textContent = "items sold today";

    $("kpiWeek").textContent = pesoShort(d.week.revenue);
    $("kpiWeekFoot").textContent = `${d.week.units} items in the last 7 days`;

    $("kpiCapital").textContent = pesoShort(d.restock.total_capital);
    $("kpiCapitalFoot").textContent =
      `${d.restock.critical_count} critical · ${d.restock.high_count} high`;
  }

  /* ---------------- trend chart ---------------- */
  function renderTrend(trend) {
    const ctx = $("trendChart");
    if (!ctx) return;
    const labels = trend.map((t) => prettyDate(t.date));
    const units = trend.map((t) => t.units);
    const revenue = trend.map((t) => t.revenue);

    if (trendChart) trendChart.destroy();

    trendChart = new Chart(ctx, {
      type: "line",
      data: {
        labels,
        datasets: [
          {
            label: "Units sold",
            data: units,
            borderColor: "#0e9f9f",
            backgroundColor: "rgba(14,159,159,.12)",
            fill: true,
            tension: 0.35,
            borderWidth: 2.5,
            pointRadius: 3,
            pointBackgroundColor: "#0e9f9f",
            yAxisID: "y",
          },
          {
            label: "Revenue (₱)",
            data: revenue,
            borderColor: "#1F3864",
            backgroundColor: "transparent",
            borderDash: [5, 4],
            tension: 0.35,
            borderWidth: 2,
            pointRadius: 0,
            yAxisID: "y1",
          },
        ],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        interaction: { mode: "index", intersect: false },
        plugins: {
          legend: { position: "bottom", labels: { boxWidth: 12, font: { size: 12 } } },
          tooltip: {
            callbacks: {
              label: (c) =>
                c.datasetIndex === 1
                  ? `Revenue: ${peso(c.parsed.y)}`
                  : `Units: ${c.parsed.y}`,
            },
          },
        },
        scales: {
          x: { grid: { display: false }, ticks: { font: { size: 11 } } },
          y: { beginAtZero: true, grid: { color: "#eef1f7" }, ticks: { font: { size: 11 } } },
          y1: {
            position: "right",
            beginAtZero: true,
            grid: { display: false },
            ticks: { font: { size: 11 }, callback: (v) => "₱" + v },
          },
        },
      },
    });
  }

  /* ---------------- top products ---------------- */
  function renderTop(products) {
    const body = $("topBody");
    if (!products || !products.length) {
      body.innerHTML = `<tr><td colspan="3"><div class="empty">No sales recorded yet.</div></td></tr>`;
      return;
    }
    body.innerHTML = products
      .map(
        (p, i) => `
        <tr>
          <td><span class="badge-x bg-info-x">${i + 1}</span></td>
          <td><strong>${escapeHtml(p.name)}</strong></td>
          <td class="num text-end">${p.units}</td>
        </tr>`
      )
      .join("");
  }

  /* ---------------- restock list ---------------- */
  function renderRestock(payload) {
    const body = $("restockBody");
    const items = payload.items.slice(0, 10);

    if (!items.length) {
      body.innerHTML = `<tr><td colspan="7"><div class="empty">Add products and record sales to get recommendations.</div></td></tr>`;
      return;
    }

    body.innerHTML = items
      .map((i) => {
        const days = i.days_until_stockout;
        const daysText = days === null ? "—" : `${days} d`;
        return `
        <tr>
          <td><strong>${escapeHtml(i.name)}</strong><div class="prod-meta">${escapeHtml(i.category || "")}</div></td>
          <td class="num">${i.stock}</td>
          <td class="num">${i.predicted_demand}</td>
          <td class="num">${daysText}</td>
          <td><span class="badge-x bg-${i.urgency}">${i.urgency}</span></td>
          <td class="num"><strong>${i.suggested_quantity}</strong></td>
          <td class="num">${peso(i.capital_needed)}</td>
        </tr>`;
      })
      .join("");

    $("restockTotal").textContent = peso(payload.summary.total_capital);
  }

  function renderModel(model) {
    const el = $("modelInfo");
    if (!el) return;
    if (!model?.loaded) {
      el.textContent = "Model: naive fallback (run python -m ml.train)";
      return;
    }
    el.textContent = `Model: ${model.model} · MAPE ${model.mape}% · trained ${model.trained_at?.slice(0, 10)}`;
  }

  /* ---------------- assistant ---------------- */
  const chat = $("chatBox");
  const input = $("chatInput");

  function bubble(text, who) {
    const el = document.createElement("div");
    el.className = "msg " + who;
    el.textContent = text;
    chat.appendChild(el);
    chat.scrollTop = chat.scrollHeight;
    return el;
  }

  async function ask(question) {
    bubble(question, "user");
    const typing = bubble("SariSense is thinking…", "bot typing");
    try {
      const res = await api("/api/assistant", { method: "POST", body: { question } });
      typing.remove();
      bubble(res.answer, "bot");
    } catch (e) {
      typing.remove();
      bubble("Sorry, something went wrong: " + e.message, "bot");
    }
  }

  $("chatForm").addEventListener("submit", (e) => {
    e.preventDefault();
    const q = input.value.trim();
    if (!q) return;
    input.value = "";
    ask(q);
  });

  document.querySelectorAll("[data-quick]").forEach((btn) => {
    btn.addEventListener("click", () => ask(btn.dataset.quick));
  });

  $("horizon")?.addEventListener("change", load);
  $("refreshBtn")?.addEventListener("click", load);

  function escapeHtml(s) {
    return String(s ?? "").replace(/[&<>"']/g, (c) =>
      ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c])
    );
  }

  load();
})();
