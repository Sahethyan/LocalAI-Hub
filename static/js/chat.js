/**
 * LocalAI Hub — stateless chat UI
 * POST /api/v1/generate (NDJSON stream), GET /api/v1/status (5s poll)
 */
(function () {
  "use strict";

  const API = {
    generate: "/api/v1/generate",
    models: "/api/v1/models",
    status: "/api/v1/status",
  };

  const STATUS_POLL_MS = 5000;

  const $ = (id) => document.getElementById(id);

  const state = {
    model: "",
    ollamaOnline: false,
    messages: [],
    streaming: false,
    abortController: null,
  };

  function configureMarked() {
    if (typeof marked === "undefined") return;
    marked.setOptions({
      gfm: true,
      breaks: true,
      highlight: (code, lang) => {
        if (typeof hljs === "undefined") return code;
        const language = lang && hljs.getLanguage(lang) ? lang : "plaintext";
        try {
          return hljs.highlight(code, { language }).value;
        } catch {
          return hljs.highlightAuto(code).value;
        }
      },
    });
  }

  function renderMarkdown(text) {
    if (typeof marked === "undefined") return escapeHtml(text);
    return marked.parse(text);
  }

  function highlightCodeBlocks(root) {
    if (typeof hljs === "undefined" || !root) return;
    root.querySelectorAll("pre code").forEach((block) => hljs.highlightElement(block));
  }

  function escapeHtml(str) {
    return str
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  function scrollToBottom() {
    const wrap = $("messagesWrap");
    if (wrap) wrap.scrollTop = wrap.scrollHeight;
  }

  function setEmptyVisible(visible) {
    const el = $("messagesEmpty");
    if (el) el.hidden = !visible;
  }

  function appendMessageRow(role, content, options = {}) {
    setEmptyVisible(false);
    const container = $("messages");
    const row = document.createElement("div");
    row.className = `message-row ${role}`;
    const bubble = document.createElement("div");
    bubble.className = "message-bubble";
    if (options.streaming) bubble.classList.add("streaming");
    if (options.error) bubble.classList.add("error");

    if (options.markdown) {
      bubble.innerHTML = renderMarkdown(content);
      highlightCodeBlocks(bubble);
    } else {
      bubble.textContent = content;
    }

    row.appendChild(bubble);
    container.appendChild(row);
    scrollToBottom();
    return bubble;
  }

  function showLoading() {
    setEmptyVisible(false);
    const container = $("messages");
    const row = document.createElement("div");
    row.className = "loading-row";
    row.id = "loadingRow";
    const spinner = document.createElement("div");
    spinner.className = "loading-spinner";
    spinner.setAttribute("role", "status");
    spinner.setAttribute("aria-label", "Waiting");
    row.appendChild(spinner);
    container.appendChild(row);
    scrollToBottom();
  }

  function hideLoading() {
    $("loadingRow")?.remove();
  }

  function updateSendEnabled() {
    const input = $("promptInput");
    const canSend =
      state.ollamaOnline &&
      state.model &&
      !state.streaming &&
      input?.value.trim();
    $("sendBtn").disabled = !canSend;
  }

  function setStatus(online) {
    state.ollamaOnline = online;
    const dot = $("statusDot");
    if (dot) {
      dot.dataset.status = online ? "online" : "offline";
      dot.title = online ? "Ollama online" : "Ollama offline";
    }
    updateSendEnabled();
  }

  async function fetchJson(url, options) {
    const res = await fetch(url, options);
    if (!res.ok) {
      let detail = `HTTP ${res.status}`;
      try {
        const body = await res.json();
        if (body.detail) {
          detail = typeof body.detail === "string" ? body.detail : JSON.stringify(body.detail);
        }
      } catch {
        /* ignore */
      }
      throw new Error(detail);
    }
    return res.json();
  }

  async function loadModels() {
    const sel = $("modelSelect");
    if (!sel) return;
    try {
      const data = await fetchJson(API.models);
      sel.innerHTML = "";
      const models = data.models || [];
      for (const m of models) {
        const opt = document.createElement("option");
        opt.value = m.name;
        opt.textContent = m.name;
        sel.appendChild(opt);
      }
      if (models.length) {
        state.model = sel.value;
      } else {
        sel.innerHTML = '<option value="">No models</option>';
        state.model = "";
      }
    } catch {
      sel.innerHTML = '<option value="">Unavailable</option>';
      state.model = "";
    }
    updateSendEnabled();
  }

  async function pollStatus() {
    const wasOnline = state.ollamaOnline;
    try {
      const data = await fetchJson(API.status);
      const online = data.ollama === "online";
      setStatus(online);
      if (online && !wasOnline) await loadModels();
    } catch {
      setStatus(false);
    }
  }

  async function* streamGenerate(messages) {
    const ac = new AbortController();
    state.abortController = ac;

    const res = await fetch(API.generate, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        model: state.model,
        messages,
        stream: true,
      }),
      signal: ac.signal,
    });

    if (!res.ok) {
      let detail = `HTTP ${res.status}`;
      try {
        const err = await res.json();
        if (err.detail) detail = typeof err.detail === "string" ? err.detail : JSON.stringify(err.detail);
      } catch {
        /* ignore */
      }
      throw new Error(detail);
    }

    const reader = res.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split("\n");
      buffer = lines.pop() || "";
      for (const line of lines) {
        const stripped = line.trim();
        if (!stripped) continue;
        let chunk;
        try {
          chunk = JSON.parse(stripped);
        } catch {
          continue;
        }
        if (chunk.error) {
          yield { type: "error", detail: chunk.error };
          return;
        }
        const token = chunk.message?.content;
        if (token) yield { type: "token", content: token };
        if (chunk.done) yield { type: "done" };
      }
    }
  }

  async function handleSend() {
    const content = $("promptInput").value.trim();
    if (!content || state.streaming || !state.model || !state.ollamaOnline) return;

    $("promptInput").value = "";
    autoResizeTextarea();
    updateSendEnabled();

    state.messages.push({ role: "user", content });
    appendMessageRow("user", content);

    showLoading();
    state.streaming = true;
    updateSendEnabled();

    let assistantBubble = null;
    let accumulated = "";

    try {
      for await (const chunk of streamGenerate(state.messages)) {
        if (chunk.type === "token") {
          if (!assistantBubble) {
            hideLoading();
            assistantBubble = appendMessageRow("assistant", "", { streaming: true });
          }
          accumulated += chunk.content;
          assistantBubble.textContent = accumulated;
          scrollToBottom();
        } else if (chunk.type === "done") {
          hideLoading();
          if (assistantBubble) {
            assistantBubble.classList.remove("streaming");
            assistantBubble.innerHTML = renderMarkdown(accumulated);
            highlightCodeBlocks(assistantBubble);
          }
          state.messages.push({ role: "assistant", content: accumulated });
          break;
        } else if (chunk.type === "error") {
          hideLoading();
          const msg = chunk.detail || "Generation failed";
          if (assistantBubble) {
            assistantBubble.classList.remove("streaming");
            assistantBubble.classList.add("error");
            assistantBubble.textContent = msg;
          } else {
            appendMessageRow("assistant", msg, { error: true });
          }
          break;
        }
      }
    } catch (e) {
      hideLoading();
      if (e.name === "AbortError") return;
      appendMessageRow("assistant", e.message || "Request failed", { error: true });
    } finally {
      state.streaming = false;
      state.abortController = null;
      updateSendEnabled();
      scrollToBottom();
    }
  }

  function autoResizeTextarea() {
    const ta = $("promptInput");
    if (!ta) return;
    ta.style.height = "auto";
    ta.style.height = `${Math.min(ta.scrollHeight, 12 * 24)}px`;
  }

  function bindEvents() {
    $("composer")?.addEventListener("submit", (e) => {
      e.preventDefault();
      handleSend();
    });

    $("promptInput")?.addEventListener("input", () => {
      autoResizeTextarea();
      updateSendEnabled();
    });

    $("promptInput")?.addEventListener("keydown", (e) => {
      if (e.key === "Enter" && !e.shiftKey) {
        e.preventDefault();
        handleSend();
      }
    });

    $("modelSelect")?.addEventListener("change", (e) => {
      state.model = e.target.value;
      updateSendEnabled();
    });
  }

  async function init() {
    configureMarked();
    bindEvents();
    autoResizeTextarea();
    await pollStatus();
    setInterval(pollStatus, STATUS_POLL_MS);
    if (state.ollamaOnline) await loadModels();
    else {
      const sel = $("modelSelect");
      if (sel) sel.innerHTML = '<option value="">Offline</option>';
    }
    updateSendEnabled();
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
