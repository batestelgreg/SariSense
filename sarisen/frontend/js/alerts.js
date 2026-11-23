/* ==================================================================
   Alerts page: anomaly detection results
   ================================================================== */
(function () {
  if (!requireLogin()) return;
  paintChrome();

  const $ = (id) => document.getElementById(id);

  async function load() {
    $("alertList").innerHTML = `<div class="empty">Running anomaly detection…</div>`;
    try {
      const res = await api("/api/alerts");
      render(res.alerts || []);
    } catch (e) {
      $("alertList").innerHTML = `<div class="empty">${e.message}</div>`;
    }
  }

  function render(alerts) {
    const list = $("alertList");
    if (!alerts.length) {
      list.innerHTML = `<div class="empty">No anomalies detected. Your sales look normal.</div>`;
      return;
    }

    list.innerHTML = alerts
      .map(
        (a) => `
        <div class="alert-item sev-${a.severity}">
          <div class="alert-icon">${a.severity === "high" ? "🔴" : "🟠"}</div>
          <div class="flex-grow-1">
            <div class="alert-title">${escapeHtml(a.message)}</div>
            <div class="alert-meta">
              ${escapeHtml(a.product_name || "")} · ${prettyDate(a.alert_date)}
              ${a.is_verified ? ' · <span class="badge-x bg-low">verified</span>' : ""}
            </div>
          </div>
          ${
            a.is_verified
              ? ""
              : `<button class="btn-x btn-ghost-x btn-sm-x" data-verify="${a.id}">Mark reviewed</button>`
          }
        </div>`
      )
      .join("");

    list.querySelectorAll("[data-verify]").forEach((btn) => {
      btn.addEventListener("click", async () => {
        btn.disabled = true;
        try {
          await api(`/api/alerts/${btn.dataset.verify}/verify`, { method: "POST" });
          btn.closest(".alert-item").querySelector(".alert-meta").innerHTML +=
            ' · <span class="badge-x bg-low">verified</span>';
          btn.remove();
        } catch (e) {
          toast(e.message);
          btn.disabled = false;
        }
      });
    });
  }

  function escapeHtml(s) {
    return String(s ?? "").replace(/[&<>"']/g, (c) =>
      ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c])
    );
  }

  $("refreshBtn").addEventListener("click", load);
  load();
})();
