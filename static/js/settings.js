/**
 * LocalAI Hub — settings page (Phase 6).
 */
(function () {
  "use strict";

  const API_SETTINGS = "/api/v1/settings";

  const $ = (id) => document.getElementById(id);

  async function fetchJson(url, options) {
    const res = await fetch(url, options);
    if (!res.ok) {
      let detail = `HTTP ${res.status}`;
      try {
        const body = await res.json();
        if (body.detail) {
          detail =
            typeof body.detail === "string"
              ? body.detail
              : JSON.stringify(body.detail);
        }
      } catch {
        /* ignore */
      }
      throw new Error(detail);
    }
    return res.json();
  }

  function showStatus(message, type) {
    const el = $("settingsStatus");
    if (!el) return;
    el.textContent = message;
    el.className = `settings-status ${type || ""}`;
    el.hidden = !message;
  }

  async function loadSettings() {
    const data = await fetchJson(API_SETTINGS);
    $("ollamaHost").value = data.ollama_host || "";
    $("ollamaPort").value = String(data.ollama_port ?? 11434);
    $("contextMessages").value = String(data.chat_context_messages ?? 40);
    const preview = $("ollamaUrlPreview");
    if (preview) {
      preview.textContent = data.ollama_base_url || "";
    }
  }

  async function saveSettings(e) {
    e.preventDefault();
    const btn = $("saveSettingsBtn");
    btn.disabled = true;
    showStatus("Saving…", "pending");

    try {
      const body = {
        ollama_host: $("ollamaHost").value.trim(),
        ollama_port: parseInt($("ollamaPort").value, 10),
        chat_context_messages: parseInt($("contextMessages").value, 10),
      };
      const data = await fetchJson(API_SETTINGS, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      $("ollamaUrlPreview").textContent = data.ollama_base_url;
      showStatus("Settings saved. Ollama URL updated without restart.", "success");
    } catch (err) {
      showStatus(err.message || "Failed to save settings", "error");
    } finally {
      btn.disabled = false;
    }
  }

  function bindPreview() {
    const update = () => {
      const host = $("ollamaHost")?.value.trim() || "…";
      const port = $("ollamaPort")?.value || "11434";
      $("ollamaUrlPreview").textContent = `http://${host}:${port}`;
    };
    $("ollamaHost")?.addEventListener("input", update);
    $("ollamaPort")?.addEventListener("input", update);
  }

  async function init() {
    bindPreview();
    $("settingsForm")?.addEventListener("submit", saveSettings);
    try {
      await loadSettings();
      showStatus("", "");
    } catch (err) {
      showStatus(err.message || "Could not load settings", "error");
    }
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
