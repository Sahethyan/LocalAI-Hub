/**
 * LocalAI Hub — shared UI (theme toggle, used on chat + settings pages).
 */
(function () {
  "use strict";

  const THEME_KEY = "localai-hub-theme";

  function applyTheme(theme) {
    const root = document.getElementById("html-root");
    if (!root) return;
    const isLight = theme === "light";
    root.classList.toggle("theme-dark", !isLight);
    root.classList.toggle("theme-light", isLight);
    const hljsLink = document.getElementById("hljs-theme");
    if (hljsLink) {
      hljsLink.href = isLight
        ? "https://cdn.jsdelivr.net/npm/highlight.js@11.9.0/styles/github.min.css"
        : "https://cdn.jsdelivr.net/npm/highlight.js@11.9.0/styles/github-dark.min.css";
    }
  }

  function initTheme() {
    const saved = localStorage.getItem(THEME_KEY);
    const prefersLight =
      saved === "light" ||
      (saved === null &&
        window.matchMedia("(prefers-color-scheme: light)").matches);
    applyTheme(prefersLight ? "light" : "dark");
    document.getElementById("themeToggle")?.addEventListener("click", () => {
      const root = document.getElementById("html-root");
      const next = root?.classList.contains("theme-light") ? "dark" : "light";
      localStorage.setItem(THEME_KEY, next);
      applyTheme(next);
    });
  }

  window.LocalAIHub = { initTheme, applyTheme, THEME_KEY };

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", initTheme);
  } else {
    initTheme();
  }
})();
