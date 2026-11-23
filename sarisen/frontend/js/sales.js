/* ==================================================================
   Sales page: record a sale, add products, view recent transactions
   ================================================================== */
(function () {
  if (!requireLogin()) return;
  paintChrome();

  const $ = (id) => document.getElementById(id);
  let products = [];
  let selectedId = null;

  /* ---------------- products ---------------- */
  async function loadProducts() {
    try {
      const res = await api("/api/products");
      products = res.products || [];
      renderGrid();
    } catch (e) {
      toast(e.message);
    }
  }

  function renderGrid() {
    const grid = $("prodGrid");
    if (!products.length) {
      grid.innerHTML = `<div class="empty">No products yet. Add your first product above.</div>`;
      return;
    }
    grid.innerHTML = products
      .map(
        (p) => `
        <button type="button" class="prod-btn ${p.id === selectedId ? "selected" : ""}"
                data-id="${p.id}">
          <div class="prod-name">${escapeHtml(p.name)}</div>
          <div class="prod-meta">Stock: ${p.stock}</div>
          <div class="prod-price">${peso(p.sell_price)}</div>
        </button>`
      )
      .join("");

    grid.querySelectorAll(".prod-btn").forEach((btn) => {
      btn.addEventListener("click", () => {
        selectedId = btn.dataset.id;
        renderGrid();
        const p = products.find((x) => x.id === selectedId);
        $("selectedName").textContent = p ? p.name : "Select a product";
        $("sellQty").focus();
      });
    });
  }

  /* ---------------- record sale ---------------- */
  $("saleForm").addEventListener("submit", async (e) => {
    e.preventDefault();
    if (!selectedId) {
      toast("Select a product first.");
      return;
    }
    const qty = parseInt($("sellQty").value || "0", 10);
    if (!qty || qty <= 0) {
      toast("Enter a quantity greater than zero.");
      return;
    }

    const btn = $("sellBtn");
    btn.disabled = true;
    btn.textContent = "Saving…";
    try {
      await api("/api/sales", {
        method: "POST",
        body: { product_id: selectedId, quantity: qty },
      });
      toast(`Recorded ${qty} item(s).`, "success");
      $("sellQty").value = 1;
      await Promise.all([loadProducts(), loadRecent()]);
    } catch (err) {
      toast(err.message);
    } finally {
      btn.disabled = false;
      btn.textContent = "Record sale";
    }
  });

  /* ---------------- add product ---------------- */
  $("productForm").addEventListener("submit", async (e) => {
    e.preventDefault();
    const payload = {
      name: $("pName").value.trim(),
      category: $("pCategory").value.trim() || "General",
      cost_price: parseFloat($("pCost").value || "0"),
      sell_price: parseFloat($("pPrice").value || "0"),
      stock: parseInt($("pStock").value || "0", 10),
      lead_time_days: parseInt($("pLead").value || "3", 10),
    };
    if (payload.name.length < 2) {
      toast("Product name is required.");
      return;
    }
    try {
      await api("/api/products", { method: "POST", body: payload });
      toast("Product added.", "success");
      $("productForm").reset();
      $("pLead").value = 3;
      bootstrap.Modal.getInstance($("productModal")).hide();
      await loadProducts();
    } catch (err) {
      toast(err.message);
    }
  });

  /* ---------------- recent sales ---------------- */
  async function loadRecent() {
    try {
      const res = await api("/api/sales?days=7");
      const rows = res.sales || [];
      const body = $("recentBody");
      if (!rows.length) {
        body.innerHTML = `<tr><td colspan="4"><div class="empty">No sales in the last 7 days.</div></td></tr>`;
        return;
      }
      body.innerHTML = rows
        .slice(0, 15)
        .map(
          (s) => `
          <tr>
            <td>${prettyDate(s.sold_at)}</td>
            <td>${escapeHtml(s.product_name)}</td>
            <td class="num">${s.quantity}</td>
            <td class="num">${peso(s.quantity * s.unit_price)}</td>
          </tr>`
        )
        .join("");
    } catch (e) {
      toast(e.message);
    }
  }

  function escapeHtml(s) {
    return String(s ?? "").replace(/[&<>"']/g, (c) =>
      ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c])
    );
  }

  loadProducts();
  loadRecent();
})();
