document.addEventListener("DOMContentLoaded", () => {
  const themeToggle = document.getElementById("themeToggle");
  const themeIcon = themeToggle?.querySelector(".theme-icon");
  const themeLabel = themeToggle?.querySelector(".theme-label");
  const applyTheme = (theme) => {
    document.body.dataset.theme = theme;
    const light = theme === "light";
    if (themeIcon) themeIcon.textContent = light ? "☾" : "☀";
    if (themeLabel) themeLabel.textContent = light ? "Dark mode" : "Light mode";
    if (themeToggle) themeToggle.setAttribute("aria-label", light ? "Switch to dark mode" : "Switch to light mode");
    document.querySelector('meta[name="theme-color"]')?.setAttribute("content", light ? "#f3f6fc" : "#080d18");
  };
  let savedTheme = "dark";
  try { savedTheme = localStorage.getItem("smart-delivery-theme") || "dark"; } catch (_) {}
  applyTheme(savedTheme);
  themeToggle?.addEventListener("click", () => {
    const next = document.body.dataset.theme === "light" ? "dark" : "light";
    applyTheme(next);
    try { localStorage.setItem("smart-delivery-theme", next); } catch (_) {}
  });
  document.querySelectorAll(".flash").forEach((el) => {
    setTimeout(() => { el.style.opacity = "0"; el.style.transform = "translateY(-6px)"; }, 4200);
    setTimeout(() => el.remove(), 4700);
  });
  document.querySelectorAll("[data-confirm]").forEach((el) => {
    el.addEventListener("click", (event) => {
      if (!confirm(el.dataset.confirm)) event.preventDefault();
    });
  });
});
