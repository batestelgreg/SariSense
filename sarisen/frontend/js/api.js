/* ==================================================================
   Shared API client + auth helpers
   ================================================================== */

const API_BASE = (window.SARISENSE_API || "http://127.0.0.1:5000").replace(/\/$/, "");

const Token = {
  get()   { return localStorage.getItem("sarisen_token"); },
  set(t)  { localStorage.setItem("sarisen_token", t); },
  clear() {
    localStorage.removeItem("sarisen_token");
    localStorage.removeItem("sarisen_store");
  },
};

const Store = {
  get()  { try { return JSON.parse(localStorage.getItem("sarisen_store")); } catch { return null; } },
  set(s) { localStorage.setItem("sarisen_store", JSON.stringify(s)); },
};

/** Fetch wrapper: adds the Bearer token, parses JSON, throws readable errors. */
async function api(path, { method = "GET", body = null } = {}) {
  const headers = { "Content-Type": "application/json" };
  const token = Token.get();
  if (token) headers.Authorization = `Bearer ${token}`;

  let res;
  try {
    res = await fetch(API_BASE + path, {
      method,
      headers,
      body: body ? JSON.stringify(body) : undefined,
    });
  } catch {
    throw new Error("Cannot reach the server. Is the backend running?");
  }

  let data = {};
  try { data = await res.json(); } catch { /* empty body */ }

  if (res.status === 401) {
    Token.clear();
    if (!document.getElementById("loginForm")) location.href = "index.html";
    throw new Error("Session expired. Please log in again.");
  }
  if (!res.ok) throw new Error(data.error || `Request failed (${res.status})`);
  return data;
}

/** Redirect to the login page when there is no token. */
function requireLogin() {
  if (!Token.get()) {
    location.href = "index.html";
    return false;
  }
  return true;
}

function logout() {
  Token.clear();
  location.href = "index.html";
}

/* ---------------- formatting helpers ---------------- */
const peso = (n) =>
  "₱" + Number(n || 0).toLocaleString("en-PH", { minimumFractionDigits: 2, maximumFractionDigits: 2 });

const pesoShort = (n) => {
  const v = Number(n || 0);
  if (v >= 1000) return "₱" + (v / 1000).toFixed(1) + "k";
  return "₱" + v.toFixed(0);
};

const prettyDate = (iso) => {
  const d = new Date(iso + (iso.length === 10 ? "T00:00:00" : ""));
  return d.toLocaleDateString("en-PH", { month: "short", day: "numeric" });
};

function toast(message, type = "danger") {
  let box = document.getElementById("toastBox");
  if (!box) {
    box = document.createElement("div");
    box.id = "toastBox";
    box.style.cssText =
      "position:fixed;top:18px;left:50%;transform:translateX(-50%);z-index:9999;" +
      "display:flex;flex-direction:column;gap:8px;align-items:center;pointer-events:none";
    document.body.appendChild(box);
  }
  const el = document.createElement("div");
  el.textContent = message;
  el.style.cssText =
    `background:${type === "success" ? "#15803d" : "#b91c1c"};color:#fff;` +
    "padding:11px 18px;border-radius:10px;font-size:13.5px;font-weight:600;" +
    "box-shadow:0 10px 30px -10px rgba(0,0,0,.5);max-width:90vw";
  box.appendChild(el);
  setTimeout(() => el.remove(), 3800);
}

/** Paint the store name + wire up the logout button on every page. */
function paintChrome() {
  const store = Store.get();
  document.querySelectorAll("[data-store-name]").forEach((el) => {
    el.textContent = store?.name || "My Store";
  });
  document.querySelectorAll("[data-logout]").forEach((el) => {
    el.addEventListener("click", logout);
  });
}
