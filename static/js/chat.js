/**
 * LocalAI Hub — Phase 5 chat UI
 * SSE via POST /api/v1/chats/{id}/messages?stream=true
 * Adapted for deferred user persistence and error events (never HTTP 500 on Ollama fail).
 */
(function () {
  "use strict";

  const API = {
    models: "/api/v1/models",
    chats: "/api/v1/chats",
    chat: "/api/v1/chat",
    ollamaStatus: "/api/v1/ollama/status",
  };

  const SEND_DEBOUNCE_MS = 400;
  const STATUS_POLL_MS = 12_000;

  const $ = (id) => document.getElementById(id);

  const state = {
    chatId: null,
    chats: [],
    model: "",
    streaming: false,
    abortController: null,
    sendTimer: null,
    lastSendAt: 0,
  };

  /* ——— Markdown ——— */

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
    root.querySelectorAll("pre code").forEach((block) => {
      hljs.highlightElement(block);
    });
  }

  function escapeHtml(str) {
    return str
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  /* ——— SSE ——— */

  function parseSseBlock(block) {
    let event = "message";
    let data = "";
    for (const line of block.split("\n")) {
      if (line.startsWith("event:")) {
        event = line.slice(6).trim();
      } else if (line.startsWith("data:")) {
        data += line.slice(5).trim();
      }
    }
    let payload = {};
    if (data) {
      try {
        payload = JSON.parse(data);
      } catch {
        payload = { detail: data };
      }
    }
    return { event, data: payload };
  }

  async function streamMessage(chatId, content, model) {
    const ac = new AbortController();
    state.abortController = ac;

    const res = await fetch(
      `${API.chats}/${chatId}/messages?stream=true`,
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          content,
          model: model || undefined,
        }),
        signal: ac.signal,
      }
    );

    if (!res.ok) {
      let detail = `HTTP ${res.status}`;
      try {
        const err = await res.json();
        if (err.detail) {
          detail =
            typeof err.detail === "string"
              ? err.detail
              : JSON.stringify(err.detail);
        }
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
      const blocks = buffer.split("\n\n");
      buffer = blocks.pop() || "";
      for (const block of blocks) {
        if (!block.trim()) continue;
        const { event, data } = parseSseBlock(block);
        if (event === "token" && data.content) {
          yield { type: "token", content: data.content };
        } else if (event === "done") {
          yield { type: "done", data };
        } else if (event === "error") {
          yield {
            type: "error",
            detail: data.detail || "Stream error",
          };
        }
      }
    }
  }

  /* ——— DOM helpers ——— */

  function scrollToBottom() {
    const wrap = $("messagesWrap");
    if (wrap) wrap.scrollTop = wrap.scrollHeight;
  }

  function setEmptyVisible(visible) {
    const el = $("messagesEmpty");
    if (el) el.hidden = !visible;
  }

  function clearMessages() {
    const container = $("messages");
    if (!container) return;
    container.querySelectorAll(".message-row, .loading-row").forEach((n) =>
      n.remove()
    );
    setEmptyVisible(true);
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

    if (options.html) {
      bubble.innerHTML = content;
    } else if (role === "assistant" && options.markdown) {
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
    spinner.setAttribute("aria-label", "Waiting for response");
    row.appendChild(spinner);
    container.appendChild(row);
    scrollToBottom();
  }

  function hideLoading() {
    $("loadingRow")?.remove();
  }

  function autoResizeTextarea() {
    const ta = $("promptInput");
    if (!ta) return;
    ta.style.height = "auto";
    ta.style.height = `${Math.min(ta.scrollHeight, 12 * 24)}px`;
  }

  function updateSendEnabled() {
    const hasModel = Boolean(state.model);
    const hasChat = state.chatId != null;
    const canSend =
      hasModel && hasChat && !state.streaming && $("promptInput")?.value.trim();
    $("sendBtn").disabled = !canSend;
    $("composerHint").hidden = hasModel;
  }

  /* ——— API ——— */

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
    if (res.status === 204) return null;
    return res.json();
  }

  async function loadModels() {
    const sel = $("modelSelect");
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
      if (!models.length) {
        sel.innerHTML = '<option value="">No models available</option>';
        state.model = "";
      } else {
        state.model = sel.value;
      }
    } catch (e) {
      sel.innerHTML = '<option value="">Models unavailable</option>';
      state.model = "";
      console.warn("Models:", e.message);
    }
    updateSendEnabled();
  }

  async function pollConnection() {
    const badge = $("connectionBadge");
    const label = $("connectionLabel");
    try {
      const data = await fetchJson(API.ollamaStatus);
      const status = data.status || "offline";
      badge.dataset.status = status;
      const labels = {
        online: "Connected",
        offline: "Offline",
        degraded: "Degraded",
      };
      label.textContent = labels[status] || status;
      badge.title = data.message || data.ollama_base_url || "";
    } catch {
      badge.dataset.status = "offline";
      label.textContent = "Offline";
    }
  }

  async function loadChatList() {
    try {
      state.chats = await fetchJson(API.chats);
    } catch {
      state.chats = [];
    }
    renderChatList();
  }

  function resetChatUi() {
    state.chatId = null;
    $("chatTitle").textContent = "New chat";
    clearMessages();
    setActiveChatInList(-1);
    updateSendEnabled();
  }

  async function createChat() {
    if (!state.model) {
      $("composerHint").hidden = false;
      $("composerHint").textContent = "Select a model before starting a chat.";
      return null;
    }
    const chat = await fetchJson(API.chat, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ model: state.model }),
    });
    state.chatId = chat.id;
    $("chatTitle").textContent = chat.title || "New chat";
    clearMessages();
    await loadChatList();
    setActiveChatInList(chat.id);
    closeSidebarMobile();
    updateSendEnabled();
    return chat;
  }

  async function deleteChat(chatId, event) {
    event?.preventDefault();
    event?.stopPropagation();
    if (state.streaming) return;
    if (!window.confirm("Delete this chat? This cannot be undone.")) return;

    try {
      await fetch(`${API.chats}/${chatId}`, { method: "DELETE" });
    } catch (e) {
      console.warn("Delete chat:", e.message);
      return;
    }

    state.chats = state.chats.filter((c) => c.id !== chatId);
    if (state.chatId === chatId) {
      state.abortController?.abort();
      resetChatUi();
      if (state.chats.length > 0) {
        await loadChat(state.chats[0].id);
      }
    }
    renderChatList();
  }

  async function loadChat(chatId) {
    if (state.streaming) return;
    state.abortController?.abort();
    const detail = await fetchJson(`${API.chats}/${chatId}`);
    state.chatId = detail.id;
    $("chatTitle").textContent = detail.title;
    if (detail.model) {
      state.model = detail.model;
      const sel = $("modelSelect");
      if (sel && [...sel.options].some((o) => o.value === detail.model)) {
        sel.value = detail.model;
      }
    }
    clearMessages();
    for (const msg of detail.messages || []) {
      appendMessageRow(msg.role, msg.content, {
        markdown: msg.role === "assistant",
      });
    }
    setActiveChatInList(chatId);
    closeSidebarMobile();
    updateSendEnabled();
  }

  function renderChatList() {
    const list = $("chatList");
    if (!list) return;
    list.innerHTML = "";
    for (const chat of state.chats) {
      const li = document.createElement("li");
      li.className = "chat-list-item";

      const row = document.createElement("div");
      row.className = "chat-list-row";

      const btn = document.createElement("button");
      btn.type = "button";
      btn.className = "chat-list-btn";
      btn.dataset.chatId = String(chat.id);
      btn.textContent = chat.title || `Chat #${chat.id}`;
      if (chat.id === state.chatId) btn.classList.add("active");
      btn.addEventListener("click", () => loadChat(chat.id));

      const del = document.createElement("button");
      del.type = "button";
      del.className = "chat-list-delete";
      del.setAttribute("aria-label", `Delete ${chat.title || "chat"}`);
      del.title = "Delete chat";
      del.innerHTML = '<span aria-hidden="true">&times;</span>';
      del.addEventListener("click", (e) => deleteChat(chat.id, e));

      row.appendChild(btn);
      row.appendChild(del);
      li.appendChild(row);
      list.appendChild(li);
    }
  }

  function setActiveChatInList(chatId) {
    document.querySelectorAll(".chat-list-btn").forEach((btn) => {
      btn.classList.toggle(
        "active",
        Number(btn.dataset.chatId) === chatId
      );
    });
  }

  /* ——— Send flow ——— */

  async function ensureChat() {
    if (state.chatId != null) return state.chatId;
    const chat = await createChat();
    return chat?.id ?? null;
  }

  async function handleSend() {
    const content = $("promptInput").value.trim();
    if (!content || state.streaming || !state.model) return;

    const now = Date.now();
    if (now - state.lastSendAt < SEND_DEBOUNCE_MS) return;
    state.lastSendAt = now;

    const chatId = await ensureChat();
    if (!chatId) return;

    $("promptInput").value = "";
    autoResizeTextarea();
    updateSendEnabled();

    appendMessageRow("user", content);
    showLoading();

    state.streaming = true;
    updateSendEnabled();

    let assistantBubble = null;
    let accumulated = "";

    try {
      for await (const chunk of streamMessage(
        chatId,
        content,
        state.model
      )) {
        if (chunk.type === "token") {
          if (!assistantBubble) {
            hideLoading();
            assistantBubble = appendMessageRow("assistant", "", {
              streaming: true,
            });
          }
          accumulated += chunk.content;
          assistantBubble.textContent = accumulated;
          scrollToBottom();
        } else if (chunk.type === "done") {
          hideLoading();
          if (assistantBubble) {
            assistantBubble.classList.remove("streaming");
            assistantBubble.innerHTML = renderMarkdown(
              chunk.data.content || accumulated
            );
            highlightCodeBlocks(assistantBubble);
          } else if (accumulated) {
            appendMessageRow("assistant", accumulated, { markdown: true });
          }
          await loadChatList();
          break;
        } else if (chunk.type === "error") {
          hideLoading();
          if (assistantBubble) {
            assistantBubble.classList.remove("streaming");
            assistantBubble.classList.add("error");
            assistantBubble.textContent = chunk.detail;
          } else {
            appendMessageRow("assistant", chunk.detail, { error: true });
          }
          break;
        }
      }
    } catch (e) {
      hideLoading();
      if (e.name === "AbortError") return;
      appendMessageRow(
        "assistant",
        e.message || "Request failed",
        { error: true }
      );
    } finally {
      state.streaming = false;
      state.abortController = null;
      updateSendEnabled();
      scrollToBottom();
    }
  }

  function debouncedSend() {
    if (state.streaming) return;
    if (state.sendTimer) clearTimeout(state.sendTimer);
    const elapsed = Date.now() - state.lastSendAt;
    const delay = elapsed < SEND_DEBOUNCE_MS ? SEND_DEBOUNCE_MS - elapsed : 0;
    state.sendTimer = setTimeout(() => {
      state.sendTimer = null;
      handleSend();
    }, delay);
  }

  /* ——— Sidebar mobile ——— */

  function openSidebarMobile() {
    $("sidebar")?.classList.add("open");
    $("sidebarBackdrop")?.removeAttribute("hidden");
    $("menuBtn")?.setAttribute("aria-expanded", "true");
  }

  function closeSidebarMobile() {
    $("sidebar")?.classList.remove("open");
    $("sidebarBackdrop")?.setAttribute("hidden", "");
    $("menuBtn")?.setAttribute("aria-expanded", "false");
  }

  /* ——— Init ——— */

  function bindEvents() {
    $("composer")?.addEventListener("submit", (e) => {
      e.preventDefault();
      debouncedSend();
    });

    $("promptInput")?.addEventListener("input", () => {
      autoResizeTextarea();
      updateSendEnabled();
    });

    $("promptInput")?.addEventListener("keydown", (e) => {
      if (e.key === "Enter" && !e.shiftKey) {
        e.preventDefault();
        debouncedSend();
      }
    });

    $("modelSelect")?.addEventListener("change", (e) => {
      state.model = e.target.value;
      updateSendEnabled();
    });

    $("newChatBtn")?.addEventListener("click", async () => {
      if (state.streaming) return;
      state.abortController?.abort();
      resetChatUi();
      closeSidebarMobile();
      await createChat();
    });

    $("menuBtn")?.addEventListener("click", openSidebarMobile);
    $("sidebarClose")?.addEventListener("click", closeSidebarMobile);
    $("sidebarBackdrop")?.addEventListener("click", closeSidebarMobile);
  }

  async function init() {
    configureMarked();
    bindEvents();
    autoResizeTextarea();
    await loadModels();
    await pollConnection();
    setInterval(pollConnection, STATUS_POLL_MS);
    await loadChatList();

    if (state.chats.length > 0 && state.chatId == null) {
      await loadChat(state.chats[0].id);
    }

    updateSendEnabled();
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
