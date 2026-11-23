/* ==================================================================
   Login / Register
   ================================================================== */
(function () {
  if (Token.get()) { location.href = "dashboard.html"; return; }

  const tabs = document.querySelectorAll(".auth-tab");
  const loginForm = document.getElementById("loginForm");
  const registerForm = document.getElementById("registerForm");
  const errBox = document.getElementById("authError");

  function showTab(name) {
    tabs.forEach((t) => t.classList.toggle("active", t.dataset.tab === name));
    loginForm.style.display = name === "login" ? "block" : "none";
    registerForm.style.display = name === "register" ? "block" : "none";
    errBox.textContent = "";
  }
  tabs.forEach((t) => t.addEventListener("click", () => showTab(t.dataset.tab)));

  function fail(message) {
    errBox.textContent = message;
    errBox.style.display = "block";
  }

  async function submit(payload, path, button) {
    errBox.style.display = "none";
    button.disabled = true;
    const original = button.textContent;
    button.textContent = "Please wait…";
    try {
      const res = await api(path, { method: "POST", body: payload });
      Token.set(res.token);
      Store.set(res.store);
      location.href = "dashboard.html";
    } catch (e) {
      fail(e.message);
      button.disabled = false;
      button.textContent = original;
    }
  }

  loginForm.addEventListener("submit", (e) => {
    e.preventDefault();
    submit(
      {
        email: document.getElementById("loginEmail").value.trim(),
        password: document.getElementById("loginPassword").value,
      },
      "/api/auth/login",
      loginForm.querySelector("button[type=submit]")
    );
  });

  registerForm.addEventListener("submit", (e) => {
    e.preventDefault();
    submit(
      {
        store_name: document.getElementById("regStore").value.trim(),
        owner_name: document.getElementById("regOwner").value.trim(),
        email: document.getElementById("regEmail").value.trim(),
        password: document.getElementById("regPassword").value,
        language: document.getElementById("regLanguage").value,
      },
      "/api/auth/register",
      registerForm.querySelector("button[type=submit]")
    );
  });

  document.getElementById("useDemo").addEventListener("click", () => {
    showTab("login");
    document.getElementById("loginEmail").value = "demo@sarisen.app";
    document.getElementById("loginPassword").value = "demo1234";
  });
})();
