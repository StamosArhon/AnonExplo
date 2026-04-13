const STORAGE_KEYS = {
  selectedModel: "anonexplo.selectedModel",
  settings: "anonexplo.uiSettings",
  directChats: "anonexplo.directChats",
  activeChatId: "anonexplo.activeChatId",
};

const DEFAULT_SETTINGS = {
  chatSystemPrompt: "",
  groundingSystemPrompt: "",
  groundingSearchLimit: 6,
  groundingFetchLimit: 3,
};

const WORKSPACES = {
  "workspace-chat": {
    eyebrow: "Direct Chat",
    title: "Model-only chat",
    copy: "Direct Chat talks only to the selected model. Its saved history stays only in this browser on this device, and it does not call SearXNG, page fetches, or grounded source packaging.",
    modeLabel: "Mode - model only",
    activityLabel: "History - browser local only",
    formId: "chat-form",
    focusId: "prompt-input",
  },
  "workspace-grounding": {
    eyebrow: "Grounded Answer",
    title: "Search, fetch, then answer",
    copy: "Grounded Answer is the workspace that uses SearXNG, page fetches, and the selected model together.",
    modeLabel: "Mode - search + fetch + model",
    activityLabel: "History - transient",
    formId: "grounding-form",
    focusId: "grounding-query",
  },
  "workspace-fetch": {
    eyebrow: "Fetch Inspector",
    title: "Fetch without model synthesis",
    copy: "Fetch Inspector reads and parses article text only. It does not send the result to the model by itself.",
    modeLabel: "Mode - fetch only",
    activityLabel: "Output - transient",
    formId: "fetch-form",
    focusId: "fetch-url",
  },
};

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}

function getConfig() {
  return fetch("/config.json").then(async (response) => {
    if (!response.ok) {
      throw new Error("Could not load UI config.");
    }
    return response.json();
  });
}

async function readJsonResponse(response) {
  try {
    return await response.json();
  } catch (error) {
    return {};
  }
}

function buildRequestError(response, data) {
  const detail = data.detail || null;
  const message =
    typeof detail === "string"
      ? detail
      : detail?.message || data.message || `Request failed with status ${response.status}.`;
  const error = new Error(message);
  error.status = response.status;
  error.detail = detail;
  return error;
}

async function fetchJson(url) {
  const response = await fetch(url);
  const data = await readJsonResponse(response);
  if (!response.ok) {
    throw buildRequestError(response, data);
  }
  return data;
}

async function requestJson(url, payload) {
  const response = await fetch(url, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(payload),
  });
  const data = await readJsonResponse(response);
  if (!response.ok) {
    throw buildRequestError(response, data);
  }
  return data;
}

function safeStorageGet(key, fallback = null) {
  try {
    const rawValue = window.localStorage.getItem(key);
    return rawValue === null ? fallback : rawValue;
  } catch (error) {
    return fallback;
  }
}

function safeStorageSet(key, value) {
  try {
    window.localStorage.setItem(key, value);
  } catch (error) {
    // Ignore browser storage failures in privacy-focused local use.
  }
}

function safeStorageRemove(key) {
  try {
    window.localStorage.removeItem(key);
  } catch (error) {
    // Ignore browser storage failures in privacy-focused local use.
  }
}

function readStoredJson(key, fallback) {
  const rawValue = safeStorageGet(key);
  if (!rawValue) {
    return fallback;
  }
  try {
    return JSON.parse(rawValue);
  } catch (error) {
    return fallback;
  }
}

function clampNumber(value, minimum, maximum, fallback) {
  const numericValue = Number(value);
  if (!Number.isFinite(numericValue)) {
    return fallback;
  }
  return Math.min(maximum, Math.max(minimum, Math.round(numericValue)));
}

function makeId(prefix) {
  if (window.crypto?.randomUUID) {
    return `${prefix}-${window.crypto.randomUUID()}`;
  }
  return `${prefix}-${Date.now()}-${Math.random().toString(16).slice(2, 10)}`;
}

function getIsoTimestamp() {
  return new Date().toISOString();
}

function getTimeLabel(timestamp = new Date()) {
  return new Intl.DateTimeFormat(undefined, {
    hour: "2-digit",
    minute: "2-digit",
  }).format(new Date(timestamp));
}

function getHistoryLabel(timestamp) {
  const date = new Date(timestamp);
  const now = new Date();
  const isSameDay =
    date.getFullYear() === now.getFullYear() &&
    date.getMonth() === now.getMonth() &&
    date.getDate() === now.getDate();

  if (isSameDay) {
    return getTimeLabel(date);
  }

  return new Intl.DateTimeFormat(undefined, {
    month: "short",
    day: "numeric",
  }).format(date);
}

function createMessage(role, content, tone = "default") {
  const createdAt = getIsoTimestamp();
  return {
    role,
    content,
    tone,
    createdAt,
    time: getTimeLabel(createdAt),
  };
}

function deriveChatTitle(prompt) {
  const trimmed = String(prompt || "").trim().replace(/\s+/g, " ");
  if (!trimmed) {
    return "New chat";
  }
  return trimmed.length > 44 ? `${trimmed.slice(0, 41)}...` : trimmed;
}

function summarizeText(value, maximumLength = 72) {
  const normalized = String(value || "").trim().replace(/\s+/g, " ");
  if (!normalized) {
    return "No messages yet.";
  }
  return normalized.length > maximumLength ? `${normalized.slice(0, maximumLength - 3)}...` : normalized;
}

function createChatSession(title = "New chat") {
  const timestamp = getIsoTimestamp();
  return {
    id: makeId("chat"),
    title,
    createdAt: timestamp,
    updatedAt: timestamp,
    messages: [],
  };
}

function normalizeChatSession(candidate) {
  if (!candidate || typeof candidate !== "object") {
    return null;
  }

  const id = typeof candidate.id === "string" && candidate.id.trim() ? candidate.id.trim() : makeId("chat");
  const createdAt = typeof candidate.createdAt === "string" ? candidate.createdAt : getIsoTimestamp();
  const updatedAt = typeof candidate.updatedAt === "string" ? candidate.updatedAt : createdAt;
  const messages = Array.isArray(candidate.messages)
    ? candidate.messages
        .filter((item) => item && typeof item === "object")
        .map((item) => ({
          role: item.role === "user" ? "user" : "assistant",
          content: String(item.content || ""),
          tone: item.tone === "error" || item.tone === "pending" ? item.tone : "default",
          createdAt: typeof item.createdAt === "string" ? item.createdAt : getIsoTimestamp(),
          time: typeof item.time === "string" && item.time.trim() ? item.time : getTimeLabel(),
        }))
    : [];

  return {
    id,
    title: typeof candidate.title === "string" && candidate.title.trim() ? candidate.title.trim() : "New chat",
    createdAt,
    updatedAt,
    messages,
  };
}

function loadSettings() {
  const stored = readStoredJson(STORAGE_KEYS.settings, {});
  return {
    chatSystemPrompt: typeof stored.chatSystemPrompt === "string" ? stored.chatSystemPrompt : DEFAULT_SETTINGS.chatSystemPrompt,
    groundingSystemPrompt:
      typeof stored.groundingSystemPrompt === "string"
        ? stored.groundingSystemPrompt
        : DEFAULT_SETTINGS.groundingSystemPrompt,
    groundingSearchLimit: clampNumber(
      stored.groundingSearchLimit,
      1,
      10,
      DEFAULT_SETTINGS.groundingSearchLimit,
    ),
    groundingFetchLimit: clampNumber(
      stored.groundingFetchLimit,
      1,
      5,
      DEFAULT_SETTINGS.groundingFetchLimit,
    ),
  };
}

function loadDirectChats() {
  const stored = readStoredJson(STORAGE_KEYS.directChats, []);
  if (!Array.isArray(stored)) {
    return [createChatSession()];
  }

  const sessions = stored
    .map(normalizeChatSession)
    .filter(Boolean)
    .sort((left, right) => new Date(right.updatedAt).getTime() - new Date(left.updatedAt).getTime());

  return sessions.length ? sessions : [createChatSession()];
}

function ensureActiveChatId(directChats, activeChatId) {
  if (activeChatId && directChats.some((chat) => chat.id === activeChatId)) {
    return activeChatId;
  }
  return directChats[0]?.id || createChatSession().id;
}

function getActiveChat(state) {
  return state.directChats.find((chat) => chat.id === state.activeChatId) || null;
}

function saveSettings(state) {
  safeStorageSet(STORAGE_KEYS.settings, JSON.stringify(state.settings));
}

function saveDirectChats(state) {
  safeStorageSet(STORAGE_KEYS.directChats, JSON.stringify(state.directChats));
  safeStorageSet(STORAGE_KEYS.activeChatId, state.activeChatId);
}

function normalizeSnapshot(health, providers, modelsPayload) {
  const runtime = modelsPayload.runtime || health.model_runtime || {};
  const configuredModel =
    modelsPayload.configured_model ||
    providers.model?.model_name ||
    health.providers?.model_name ||
    runtime.configured_model ||
    "";

  return {
    health,
    providers,
    runtime,
    configuredModel,
    availableModels: Array.isArray(modelsPayload.models) ? modelsPayload.models : [],
  };
}

function chooseSelectedModel(snapshot, previousSelection) {
  const availableIds = new Set(snapshot.availableModels.map((item) => item.id));
  if (previousSelection && (!availableIds.size || availableIds.has(previousSelection))) {
    return previousSelection;
  }
  if (snapshot.configuredModel && (!availableIds.size || availableIds.has(snapshot.configuredModel))) {
    return snapshot.configuredModel;
  }
  return snapshot.availableModels[0]?.id || snapshot.configuredModel || "";
}

function getStatusVariant(status) {
  if (["ok", "ready", "grounded"].includes(status)) {
    return "ok";
  }
  if (status === "snippet_grounded") {
    return "warn";
  }
  if (["unreachable", "invalid_response", "model_error", "error"].includes(status)) {
    return "error";
  }
  return "warn";
}

function buildChip(label, value, variant = "muted") {
  return `<span class="chip chip-${escapeHtml(variant)}">${escapeHtml(label)} - ${escapeHtml(value)}</span>`;
}

function buildBanner(title, message, variant = "warning", extra = "") {
  return `
    <div class="banner banner-${escapeHtml(variant)}">
      <strong>${escapeHtml(title)}</strong>
      <div>${escapeHtml(message)}</div>
      ${extra}
    </div>
  `;
}

function buildErrorDetailMeta(detail) {
  if (!detail || typeof detail !== "object") {
    return "";
  }

  const chips = [];
  if (detail.code) {
    chips.push(buildChip("Code", detail.code, "warn"));
  }
  if (typeof detail.upstream_status === "number") {
    chips.push(buildChip("Upstream", String(detail.upstream_status), "warn"));
  }
  if (typeof detail.retryable === "boolean") {
    chips.push(buildChip("Retryable", detail.retryable ? "yes" : "no", detail.retryable ? "warn" : "muted"));
  }

  return chips.length ? `<div class="chip-row">${chips.join("")}</div>` : "";
}

function buildGroundingErrorMeta(error) {
  if (!error || typeof error !== "object") {
    return "";
  }

  const chips = [];
  if (error.code) {
    chips.push(buildChip("Code", error.code, "warn"));
  }
  if (typeof error.upstream_status === "number") {
    chips.push(buildChip("Upstream", String(error.upstream_status), "warn"));
  }
  if (typeof error.retryable === "boolean") {
    chips.push(buildChip("Retryable", error.retryable ? "yes" : "no", error.retryable ? "warn" : "muted"));
  }

  return chips.length ? `<div class="chip-row">${chips.join("")}</div>` : "";
}

function setContextChip(element, label, value, variant = "muted") {
  element.className = `context-chip chip-${variant}`;
  element.textContent = `${label} - ${value}`;
}

function getWorkspaceActivityLabel(state, workspaceId) {
  if (workspaceId === "workspace-chat") {
    return getActiveChat(state)?.title || "New chat";
  }
  return WORKSPACES[workspaceId].activityLabel;
}

function scrollThreadToBottom(target) {
  target.scrollTop = target.scrollHeight;
}

function renderConversation(target, messages, emptyText) {
  if (!messages.length) {
    target.innerHTML = `<div class="empty-state">${escapeHtml(emptyText)}</div>`;
    return;
  }

  target.innerHTML = messages
    .map((message) => {
      const roleLabel = message.role === "user" ? "You" : "Assistant";
      const rowClass = message.role === "user" ? "message-row-user" : "message-row-assistant";
      const toneClass =
        message.tone === "pending"
          ? "message-card-pending"
          : message.tone === "error"
            ? "message-card-error"
            : "";
      const userClass = message.role === "user" ? "message-card-user" : "";

      return `
        <div class="message-row ${rowClass}">
          <article class="message-card ${userClass} ${toneClass}">
            <div class="message-meta">
              <span class="message-role">${escapeHtml(roleLabel)}</span>
              <span class="message-time">${escapeHtml(message.time || "")}</span>
            </div>
            <div class="message-copy">${escapeHtml(message.content || "")}</div>
          </article>
        </div>
      `;
    })
    .join("");

  scrollThreadToBottom(target);
}

function buildHistoryRows(state) {
  return state.directChats
    .map((chat) => {
      const previewSource = chat.messages[chat.messages.length - 1]?.content || "";
      const activeClass = chat.id === state.activeChatId ? " active" : "";
      return `
        <div class="history-row">
          <button type="button" class="history-button${activeClass}" data-chat-id="${escapeHtml(chat.id)}">
            <span class="history-title">${escapeHtml(chat.title)}</span>
            <span class="history-preview">${escapeHtml(summarizeText(previewSource, 54))}</span>
            <span class="history-time">${escapeHtml(getHistoryLabel(chat.updatedAt))}</span>
          </button>
          <button type="button" class="history-delete" data-delete-chat-id="${escapeHtml(chat.id)}">Delete</button>
        </div>
      `;
    })
    .join("");
}

function renderChatHistory(state, elements) {
  elements.chatHistoryList.innerHTML = buildHistoryRows(state);
}

function renderWorkspaceShell(state, elements) {
  const workspace = WORKSPACES[state.activeWorkspace];
  elements.workspaceEyebrow.textContent = workspace.eyebrow;
  elements.workspaceTitle.textContent = workspace.title;
  elements.workspaceCopy.textContent = workspace.copy;
  setContextChip(elements.modeChip, "Mode", workspace.modeLabel.replace("Mode - ", ""), "muted");
  setContextChip(
    elements.activeChatChip,
    workspaceIdToChipLabel(state.activeWorkspace),
    getWorkspaceActivityLabel(state, state.activeWorkspace),
    "muted",
  );

  Object.entries(WORKSPACES).forEach(([workspaceId, meta]) => {
    document.getElementById(workspaceId).hidden = workspaceId !== state.activeWorkspace;
    document.getElementById(meta.formId).hidden = workspaceId !== state.activeWorkspace;
  });

  document.querySelectorAll("[data-workspace-target]").forEach((button) => {
    button.classList.toggle("active", button.dataset.workspaceTarget === state.activeWorkspace);
  });
}

function workspaceIdToChipLabel(workspaceId) {
  if (workspaceId === "workspace-chat") {
    return "Chat";
  }
  if (workspaceId === "workspace-grounding") {
    return "History";
  }
  return "Output";
}

function renderTopbar(config, state, elements) {
  const runtimeStatus = state.snapshot?.runtime?.status || "loading";
  const searchProvider = state.snapshot?.providers?.search?.provider || "loading";
  const selectedModel = state.selectedModel || state.snapshot?.configuredModel || "loading";

  setContextChip(elements.environmentChip, "Environment", config.environment || "local", "muted");
  setContextChip(elements.runtimeChip, "Runtime", runtimeStatus, getStatusVariant(runtimeStatus));
  setContextChip(elements.modelChip, "Model", selectedModel, "active");
  setContextChip(elements.searchChip, "Search", searchProvider, "muted");
}

function buildModelOptions(state) {
  const models = state.snapshot?.availableModels || [];
  const fallbackId = state.selectedModel || state.snapshot?.configuredModel || "";

  if (!models.length && fallbackId) {
    return [`<option value="${escapeHtml(fallbackId)}">${escapeHtml(fallbackId)}</option>`].join("");
  }

  return models
    .map((model) => {
      const selected = model.id === state.selectedModel ? " selected" : "";
      return `<option value="${escapeHtml(model.id)}"${selected}>${escapeHtml(model.id)}</option>`;
    })
    .join("");
}

function renderSettingsForm(state, elements) {
  elements.settingsModelSelect.innerHTML = buildModelOptions(state);
  if (state.selectedModel) {
    elements.settingsModelSelect.value = state.selectedModel;
  }
  elements.settingsChatSystem.value = state.settings.chatSystemPrompt;
  elements.settingsGroundingSystem.value = state.settings.groundingSystemPrompt;
  elements.settingsSearchLimit.value = String(state.settings.groundingSearchLimit);
  elements.settingsFetchLimit.value = String(state.settings.groundingFetchLimit);
}

function renderStackModal(state, elements) {
  if (!state.snapshot) {
    elements.configuredModel.textContent = "Loading...";
    elements.runtimeNote.textContent = "Runtime details will appear after the first snapshot refresh.";
    elements.runtimeSummary.innerHTML = '<div class="meta">Loading runtime snapshot...</div>';
    elements.providerSummary.innerHTML = '<div class="meta">Loading provider summary...</div>';
    elements.statusOutput.innerHTML = '<div class="status-card">Loading local snapshot...</div>';
    return;
  }

  const runtime = state.snapshot.runtime || {};
  const providers = state.snapshot.providers || {};
  const advertisedModels = state.snapshot.availableModels || [];

  elements.configuredModel.textContent = state.snapshot.configuredModel || "unknown";
  elements.runtimeNote.textContent =
    runtime.error || "Runtime readiness is checked against the live local model endpoint.";

  elements.runtimeSummary.innerHTML = [
    buildChip("Status", runtime.status || "unknown", getStatusVariant(runtime.status || "unknown")),
    buildChip("Reachable", runtime.reachable ? "yes" : "no", runtime.reachable ? "ok" : "error"),
    buildChip("Advertised", String(advertisedModels.length), advertisedModels.length ? "ok" : "warn"),
    runtime.checked_url ? `<div class="meta">${escapeHtml(runtime.checked_url)}</div>` : "",
  ].join("");

  elements.providerSummary.innerHTML = [
    buildChip("Model provider", providers.model?.provider || "unknown", "muted"),
    buildChip("Search provider", providers.search?.provider || "unknown", "muted"),
    buildChip("Fetch path", providers.fetch?.base_url || "unknown", "muted"),
    buildChip("Runtime profile", providers.model?.runtime_profile || "unknown", "muted"),
  ].join("");

  const statusCards = [
    `<div class="status-card"><strong>Backend</strong><div class="meta">${escapeHtml(
      state.snapshot.health?.status || "unknown",
    )}</div></div>`,
    `<div class="status-card"><strong>Selected model</strong><div class="meta">${escapeHtml(
      state.selectedModel || state.snapshot.configuredModel || "unknown",
    )}</div></div>`,
  ];

  if (advertisedModels.length) {
    statusCards.push(
      `<div class="status-card"><strong>Advertised models</strong><div class="chip-row">${advertisedModels
        .map((item) =>
          buildChip(
            item.id,
            item.id === state.selectedModel ? "selected" : "available",
            item.id === state.selectedModel ? "active" : "muted",
          ),
        )
        .join("")}</div></div>`,
    );
  }

  elements.statusOutput.innerHTML = statusCards.join("");
}

function renderChatMeta(state, elements) {
  const chips = [
    buildChip("Mode", "model only", "muted"),
    buildChip("Search", "off", "muted"),
    buildChip("Model", state.selectedModel || state.snapshot?.configuredModel || "unknown", "active"),
  ];

  if (state.chatStatus.kind === "pending") {
    chips.push(buildChip("Status", "waiting", "warn"));
  }

  if (state.chatStatus.kind === "success") {
    chips.push(
      buildChip("Runtime", state.chatStatus.payload.runtime_status || "unknown", getStatusVariant(state.chatStatus.payload.runtime_status || "unknown")),
    );
    chips.push(
      buildChip("Usage", String(state.chatStatus.payload.usage?.total_tokens || 0), "muted"),
    );
  }

  if (state.chatStatus.kind === "error") {
    const detail = state.chatStatus.error.detail || {};
    const runtimeStatus = detail.runtime?.status;
    if (runtimeStatus) {
      chips.push(buildChip("Runtime", runtimeStatus, getStatusVariant(runtimeStatus)));
    }
    chips.push(buildChip("Status", "request failed", "error"));
  }

  elements.chatMeta.innerHTML = chips.join("");
}

function renderGroundingMeta(state, elements) {
  const searchProvider = state.snapshot?.providers?.search?.provider || "unknown";
  const chips = [
    buildChip("Mode", "search + fetch + model", "muted"),
    buildChip("Search", searchProvider, "muted"),
    buildChip("Model", state.selectedModel || state.snapshot?.configuredModel || "unknown", "active"),
  ];

  if (state.groundingStatus.kind === "pending") {
    chips.push(buildChip("Status", "grounding", "warn"));
  }

    if (state.groundingStatus.kind === "success") {
      chips.push(
        buildChip(
          "Answer",
          state.groundingStatus.payload.answer_status || "unknown",
          getStatusVariant(state.groundingStatus.payload.answer_status || "unknown"),
        ),
      );
      chips.push(
        buildChip(
          "Context",
          state.groundingStatus.payload.grounding?.summary?.context_mode || "none",
          state.groundingStatus.payload.grounding?.summary?.context_mode === "fetched_text" ? "ok" : "warn",
        ),
      );
    }

  if (state.groundingStatus.kind === "error") {
    chips.push(buildChip("Status", "request failed", "error"));
  }

  elements.groundingMeta.innerHTML = chips.join("");
}

function renderFetchMeta(state, elements) {
  const chips = [buildChip("Mode", "fetch only", "muted")];

  if (state.fetchStatus.kind === "pending") {
    chips.push(buildChip("Status", "fetching", "warn"));
  }

  if (state.fetchStatus.kind === "success") {
    chips.push(
      buildChip(
        "Method",
        state.fetchStatus.payload.retrieval_method || "direct_html",
        "muted",
      ),
    );
    chips.push(
      buildChip(
        "Quality",
        state.fetchStatus.payload.content_quality || "unknown",
        state.fetchStatus.payload.content_quality === "usable" ? "ok" : "warn",
      ),
    );
    chips.push(buildChip("Chars", String(state.fetchStatus.payload.content_char_count || 0), "muted"));
    chips.push(buildChip("Words", String(state.fetchStatus.payload.word_count || 0), "muted"));
  }

  if (state.fetchStatus.kind === "error") {
    chips.push(buildChip("Status", "request failed", "error"));
  }

  elements.fetchMeta.innerHTML = chips.join("");
}

function renderGroundingDetails(state, elements) {
  if (state.groundingStatus.kind !== "success") {
    elements.groundingDetails.hidden = true;
    elements.groundingErrors.innerHTML = "";
    elements.groundingSummary.innerHTML = "";
    elements.groundingOutput.innerHTML = "";
    return;
  }

  const payload = state.groundingStatus.payload;
  const grounding = payload.grounding || payload;
  const summary = grounding.summary || {};
  const fetchedById = new Map((grounding.fetched_sources || []).map((item) => [item.source_id, item]));

  elements.groundingDetails.hidden = false;
  elements.groundingDetails.open = true;
  elements.groundingSummary.innerHTML = [
    `<div class="status-card"><strong>Search hits</strong><div class="meta">${escapeHtml(summary.search_results || 0)}</div></div>`,
    `<div class="status-card"><strong>Unique hits</strong><div class="meta">${escapeHtml(summary.unique_search_results || 0)}</div></div>`,
    `<div class="status-card"><strong>Fetched</strong><div class="meta">${escapeHtml(summary.fetched_sources || 0)}</div></div>`,
    `<div class="status-card"><strong>Failures</strong><div class="meta">${escapeHtml(summary.failed_sources || 0)}</div></div>`,
    `<div class="status-card"><strong>Context chars</strong><div class="meta">${escapeHtml(summary.grounding_characters || 0)}</div></div>`,
    `<div class="status-card"><strong>Context mode</strong><div class="meta">${escapeHtml(summary.context_mode || "none")}</div></div>`,
    `<div class="status-card"><strong>Selected / attempted</strong><div class="meta">${escapeHtml(summary.selected_sources || 0)}</div></div>`,
  ].join("");

  const errors = grounding.errors || [];
  elements.groundingErrors.innerHTML = errors
    .map((item) =>
      buildBanner(
        item.source_id ? `Source ${item.source_id} issue` : "Grounding issue",
        item.message || "Unknown grounding error.",
        "warning",
        [
          item.url ? `<div class="meta">${escapeHtml(item.url)}</div>` : "",
          buildGroundingErrorMeta(item),
        ].join(""),
      ),
    )
    .join("");

  const selectedSources = grounding.selected_sources || [];
  if (!selectedSources.length) {
    elements.groundingOutput.innerHTML =
      '<div class="result-card">No sources were selected from the current search results.</div>';
    return;
  }

  elements.groundingOutput.innerHTML = selectedSources
    .map((source) => {
      const fetched = fetchedById.get(source.source_id);
      const sourceError = errors.find((item) => item.source_id === source.source_id);
      const usesSnippetFallback = summary.context_mode === "search_snippets" && !fetched && Boolean(source.snippet);
      const statusLabel = fetched ? "Fetched" : usesSnippetFallback ? "Snippet used" : sourceError ? "Failed" : "Selected";
      const statusClass = fetched
        ? "status-fetched"
        : usesSnippetFallback
          ? "status-selected"
          : sourceError
            ? "status-failed"
            : "status-selected";

      return `
        <div class="result-card">
          <div class="status-line">
            <strong>${escapeHtml(source.title)}</strong>
            <span class="status-badge ${statusClass}">${escapeHtml(statusLabel)}</span>
          </div>
          <div class="meta">
            Rank ${escapeHtml(source.search_rank)} | ${escapeHtml(source.domain)} |
            <a href="${escapeHtml(source.url)}" target="_blank" rel="noreferrer">${escapeHtml(source.url)}</a>
          </div>
          <div class="source-body">
            <p>${escapeHtml(source.snippet || "No search snippet available.")}</p>
            ${
                fetched
                  ? `
                    <div class="chip-row">
                      ${buildChip("Method", fetched.retrieval_method || "direct_html", "muted")}
                      ${buildChip(
                        "Quality",
                        fetched.content_quality || "unknown",
                        fetched.content_quality === "usable" ? "ok" : "warn",
                      )}
                      ${buildChip("Context", String(fetched.context_chars_used || 0), "muted")}
                      ${buildChip("Extracted", String(fetched.content_char_count || 0), "muted")}
                      ${buildChip("Words", String(fetched.word_count || 0), "muted")}
                    </div>
                    ${
                      Array.isArray(fetched.warnings) && fetched.warnings.length
                        ? `<div class="meta">Warnings: ${escapeHtml(fetched.warnings.join(" | "))}</div>`
                        : ""
                    }
                    <div class="source-text">${escapeHtml(
                      fetched.context_text || fetched.excerpt || "No grounded source text available.",
                    )}</div>
                  `
                  : usesSnippetFallback
                    ? `
                      <div class="meta">Article fetch failed, so the grounded answer used the returned search snippet.</div>
                      <div class="source-text">${escapeHtml(source.snippet || "No search snippet available.")}</div>
                    `
                  : sourceError
                    ? `
                      <p class="error">${escapeHtml(sourceError.message)}</p>
                      ${buildGroundingErrorMeta(sourceError)}
                    `
                    : '<p class="meta">Selected for grounding but not fetched.</p>'
            }
          </div>
        </div>
      `;
    })
    .join("");
}

function renderFetchOutput(state, elements) {
  if (state.fetchStatus.kind === "success") {
    const payload = state.fetchStatus.payload;
    elements.fetchOutput.innerHTML = `
      <h3>${escapeHtml(payload.title || "Untitled")}</h3>
      <p class="meta">${escapeHtml(payload.final_url || payload.requested_url || "")}</p>
      <div class="chip-row">
        ${buildChip("Method", payload.retrieval_method || "direct_html", "muted")}
        ${buildChip("Quality", payload.content_quality || "unknown", payload.content_quality === "usable" ? "ok" : "warn")}
        ${buildChip("Chars", String(payload.content_char_count || 0), "muted")}
        ${buildChip("Words", String(payload.word_count || 0), "muted")}
      </div>
      ${
        Array.isArray(payload.warnings) && payload.warnings.length
          ? `<div class="meta">Warnings: ${escapeHtml(payload.warnings.join(" | "))}</div>`
          : ""
      }
      <p>${escapeHtml(payload.excerpt || "No excerpt available.")}</p>
      <div class="source-text">${escapeHtml(payload.content_text || "No readable article text returned.")}</div>
    `;
    return;
  }

  if (state.fetchStatus.kind === "error") {
    elements.fetchOutput.innerHTML = buildBanner(
      "Fetch request failed",
      state.fetchStatus.error.message,
      "error",
      buildErrorDetailMeta(state.fetchStatus.error.detail),
    );
    return;
  }

  if (state.fetchStatus.kind === "pending") {
    elements.fetchOutput.innerHTML = '<div class="empty-state">Fetching and parsing article...</div>';
    return;
  }

  elements.fetchOutput.innerHTML = `
    <div class="empty-state">
      Fetched article text will appear here. This workspace never sends the result to the model by itself.
    </div>
  `;
}

function renderDirectChat(state, elements) {
  const activeChat = getActiveChat(state);
  renderConversation(
    elements.chatOutput,
    activeChat?.messages || [],
    "No direct-chat messages yet. This workspace is model only and never triggers search or fetch.",
  );
  renderChatMeta(state, elements);
}

function renderGroundingWorkspace(state, elements) {
  renderConversation(
    elements.groundingAnswer,
    state.groundingMessages,
    "No grounded requests yet. Use this workspace when you want SearXNG, fetched page text, and sourced answers.",
  );
  renderGroundingMeta(state, elements);
  renderGroundingDetails(state, elements);
}

function renderApp(config, state, elements) {
  renderChatHistory(state, elements);
  renderWorkspaceShell(state, elements);
  renderTopbar(config, state, elements);
  renderSettingsForm(state, elements);
  renderStackModal(state, elements);
  renderDirectChat(state, elements);
  renderGroundingWorkspace(state, elements);
  renderFetchMeta(state, elements);
  renderFetchOutput(state, elements);
}

function openModal(modal) {
  modal.hidden = false;
}

function closeModal(modal) {
  modal.hidden = true;
}

function buildGroundingAssistantText(payload) {
  if (payload.answer_status === "grounded" || payload.answer_status === "snippet_grounded") {
    return payload.answer || "(empty grounded answer)";
  }
  if (payload.answer_status === "insufficient_sources") {
    return "Search finished, but not enough fetched source text was available to answer from derived material only.";
  }
  if (payload.answer_status === "model_error") {
    return payload.model_error || "Source collection finished, but the local model failed while synthesizing an answer.";
  }
  return "Grounding finished without a synthesized answer.";
}

async function main() {
  const config = await getConfig();
  const directChats = loadDirectChats();
  const activeChatId = ensureActiveChatId(
    directChats,
    safeStorageGet(STORAGE_KEYS.activeChatId, directChats[0]?.id || ""),
  );

  const state = {
    snapshot: null,
    selectedModel: safeStorageGet(STORAGE_KEYS.selectedModel, ""),
    settings: loadSettings(),
    directChats,
    activeChatId,
    activeWorkspace: "workspace-chat",
    chatStatus: { kind: "idle" },
    groundingStatus: { kind: "idle" },
    fetchStatus: { kind: "idle" },
    groundingMessages: [],
  };

  const elements = {
    chatHistoryList: document.getElementById("chat-history-list"),
    newChatButton: document.getElementById("new-chat"),
    purgeHistoryButton: document.getElementById("purge-history"),
    openSettingsButtons: [
      document.getElementById("open-settings"),
      document.getElementById("topbar-open-settings"),
      document.getElementById("composer-open-settings"),
      document.getElementById("grounding-open-settings"),
    ].filter(Boolean),
    openStackButtons: [
      document.getElementById("open-stack"),
      document.getElementById("topbar-open-stack"),
    ].filter(Boolean),
    openSearchLink: document.getElementById("open-search-link"),
    stackSearchLink: document.getElementById("stack-search-link"),
    workspaceEyebrow: document.getElementById("workspace-eyebrow"),
    workspaceTitle: document.getElementById("workspace-title"),
    workspaceCopy: document.getElementById("workspace-copy"),
    modeChip: document.getElementById("mode-chip"),
    activeChatChip: document.getElementById("active-chat-chip"),
    environmentChip: document.getElementById("environment-chip"),
    runtimeChip: document.getElementById("runtime-chip"),
    modelChip: document.getElementById("model-chip"),
    searchChip: document.getElementById("search-chip"),
    chatMeta: document.getElementById("chat-meta"),
    chatOutput: document.getElementById("chat-output"),
    groundingAnswer: document.getElementById("grounding-answer"),
    groundingDetails: document.getElementById("grounding-details"),
    groundingMeta: document.getElementById("grounding-meta"),
    groundingErrors: document.getElementById("grounding-errors"),
    groundingSummary: document.getElementById("grounding-summary"),
    groundingOutput: document.getElementById("grounding-output"),
    fetchMeta: document.getElementById("fetch-meta"),
    fetchOutput: document.getElementById("fetch-output"),
    settingsModal: document.getElementById("settings-modal"),
    stackModal: document.getElementById("stack-modal"),
    settingsForm: document.getElementById("settings-form"),
    settingsModelSelect: document.getElementById("settings-model-select"),
    settingsChatSystem: document.getElementById("settings-chat-system"),
    settingsGroundingSystem: document.getElementById("settings-grounding-system"),
    settingsSearchLimit: document.getElementById("settings-search-limit"),
    settingsFetchLimit: document.getElementById("settings-fetch-limit"),
    configuredModel: document.getElementById("configured-model"),
    runtimeNote: document.getElementById("runtime-note"),
    runtimeSummary: document.getElementById("runtime-summary"),
    providerSummary: document.getElementById("provider-summary"),
    statusOutput: document.getElementById("status-output"),
    refreshStatusButton: document.getElementById("refresh-status"),
    chatForm: document.getElementById("chat-form"),
    chatPrompt: document.getElementById("prompt-input"),
    groundingForm: document.getElementById("grounding-form"),
    groundingQuery: document.getElementById("grounding-query"),
    fetchForm: document.getElementById("fetch-form"),
    fetchUrl: document.getElementById("fetch-url"),
  };

  const standaloneSearchUrl =
    config.standaloneSearchUrl ||
    `${window.location.protocol}//${window.location.hostname}:8085`;
  elements.openSearchLink.href = standaloneSearchUrl;
  elements.stackSearchLink.href = standaloneSearchUrl;

  function persistModelSelection() {
    if (state.selectedModel) {
      safeStorageSet(STORAGE_KEYS.selectedModel, state.selectedModel);
      return;
    }
    safeStorageRemove(STORAGE_KEYS.selectedModel);
  }

  function rerender() {
    renderApp(config, state, elements);
  }

  function activateWorkspace(workspaceId) {
    state.activeWorkspace = workspaceId;
    rerender();
    const focusId = WORKSPACES[workspaceId]?.focusId;
    if (focusId) {
      document.getElementById(focusId)?.focus();
    }
  }

  function createAndActivateNewChat() {
    const chat = createChatSession();
    state.directChats = [chat, ...state.directChats];
    state.activeChatId = chat.id;
    state.chatStatus = { kind: "idle" };
    saveDirectChats(state);
    activateWorkspace("workspace-chat");
  }

  function deleteChat(chatId) {
    state.directChats = state.directChats.filter((chat) => chat.id !== chatId);
    if (!state.directChats.length) {
      state.directChats = [createChatSession()];
    }
    state.activeChatId = ensureActiveChatId(state.directChats, state.activeChatId === chatId ? "" : state.activeChatId);
    state.chatStatus = { kind: "idle" };
    saveDirectChats(state);
    rerender();
  }

  function refreshActiveChatAfterMutation(session) {
    session.updatedAt = getIsoTimestamp();
    state.directChats = [session, ...state.directChats.filter((item) => item.id !== session.id)];
    state.activeChatId = session.id;
    saveDirectChats(state);
  }

  async function refreshSnapshot() {
    elements.statusOutput.innerHTML = '<div class="status-card">Refreshing local snapshot...</div>';

    const [health, providers, modelsPayload] = await Promise.all([
      fetchJson(`${config.apiBaseUrl}/health`),
      fetchJson(`${config.apiBaseUrl}/system/providers`),
      fetchJson(`${config.apiBaseUrl}/model/models`),
    ]);

    state.snapshot = normalizeSnapshot(health, providers, modelsPayload);
    state.selectedModel = chooseSelectedModel(state.snapshot, state.selectedModel);
    persistModelSelection();
    rerender();
  }

  document.querySelectorAll("[data-workspace-target]").forEach((button) => {
    button.addEventListener("click", () => activateWorkspace(button.dataset.workspaceTarget));
  });

  elements.newChatButton.addEventListener("click", createAndActivateNewChat);
  elements.purgeHistoryButton.addEventListener("click", () => {
    state.directChats = [createChatSession()];
    state.activeChatId = state.directChats[0].id;
    state.chatStatus = { kind: "idle" };
    saveDirectChats(state);
    activateWorkspace("workspace-chat");
  });

  elements.chatHistoryList.addEventListener("click", (event) => {
    const deleteButton = event.target.closest("[data-delete-chat-id]");
    if (deleteButton) {
      deleteChat(deleteButton.dataset.deleteChatId);
      return;
    }

    const openButton = event.target.closest("[data-chat-id]");
    if (openButton) {
      state.activeChatId = openButton.dataset.chatId;
      state.chatStatus = { kind: "idle" };
      saveDirectChats(state);
      activateWorkspace("workspace-chat");
    }
  });

  elements.openSettingsButtons.forEach((button) => {
    button.addEventListener("click", () => {
      renderSettingsForm(state, elements);
      openModal(elements.settingsModal);
    });
  });

  elements.openStackButtons.forEach((button) => {
    button.addEventListener("click", () => openModal(elements.stackModal));
  });

  document.querySelectorAll("[data-close-modal]").forEach((button) => {
    button.addEventListener("click", () => {
      const modal = document.getElementById(button.dataset.closeModal);
      if (modal) {
        closeModal(modal);
      }
    });
  });

  [elements.settingsModal, elements.stackModal].forEach((modal) => {
    modal.addEventListener("click", (event) => {
      if (event.target === modal) {
        closeModal(modal);
      }
    });
  });

  document.addEventListener("keydown", (event) => {
    if (event.key !== "Escape") {
      return;
    }
    [elements.settingsModal, elements.stackModal].forEach((modal) => {
      if (!modal.hidden) {
        closeModal(modal);
      }
    });
  });

  elements.settingsForm.addEventListener("submit", (event) => {
    event.preventDefault();
    state.selectedModel = elements.settingsModelSelect.value.trim();
    state.settings = {
      chatSystemPrompt: elements.settingsChatSystem.value.trim(),
      groundingSystemPrompt: elements.settingsGroundingSystem.value.trim(),
      groundingSearchLimit: clampNumber(elements.settingsSearchLimit.value, 1, 10, DEFAULT_SETTINGS.groundingSearchLimit),
      groundingFetchLimit: clampNumber(elements.settingsFetchLimit.value, 1, 5, DEFAULT_SETTINGS.groundingFetchLimit),
    };
    persistModelSelection();
    saveSettings(state);
    closeModal(elements.settingsModal);
    rerender();
  });

  elements.refreshStatusButton.addEventListener("click", async () => {
    try {
      await refreshSnapshot();
    } catch (error) {
      state.snapshot = state.snapshot || null;
      elements.statusOutput.innerHTML = buildBanner("Snapshot refresh failed", error.message, "error");
      setContextChip(elements.runtimeChip, "Runtime", "refresh failed", "error");
    }
  });

  elements.chatForm.addEventListener("submit", async (event) => {
    event.preventDefault();
    const prompt = elements.chatPrompt.value.trim();
    if (!prompt) {
      state.chatStatus = { kind: "error", error: new Error("A prompt is required.") };
      rerender();
      return;
    }

    const activeChat = getActiveChat(state) || createChatSession();
    if (!state.directChats.some((chat) => chat.id === activeChat.id)) {
      state.directChats = [activeChat, ...state.directChats];
    }

    if (activeChat.title === "New chat") {
      activeChat.title = deriveChatTitle(prompt);
    }

    activeChat.messages.push(createMessage("user", prompt));
    activeChat.messages.push(createMessage("assistant", "Waiting for the selected local model...", "pending"));
    refreshActiveChatAfterMutation(activeChat);
    state.chatStatus = { kind: "pending" };
    elements.chatPrompt.value = "";
    rerender();

    try {
      const payload = await requestJson(`${config.apiBaseUrl}/model/chat`, {
        prompt,
        system_prompt: state.settings.chatSystemPrompt || null,
        selected_model: state.selectedModel || null,
      });
      const session = getActiveChat(state);
      if (session) {
        session.messages[session.messages.length - 1] = createMessage("assistant", payload.answer || "(empty response)");
        refreshActiveChatAfterMutation(session);
      }
      state.chatStatus = { kind: "success", payload };
      rerender();
      await refreshSnapshot();
    } catch (error) {
      const session = getActiveChat(state);
      if (session) {
        session.messages[session.messages.length - 1] = createMessage("assistant", error.message, "error");
        refreshActiveChatAfterMutation(session);
      }
      state.chatStatus = { kind: "error", error };
      rerender();
    }
  });

  elements.groundingForm.addEventListener("submit", async (event) => {
    event.preventDefault();
    const query = elements.groundingQuery.value.trim();
    if (!query) {
      state.groundingStatus = { kind: "error", error: new Error("A grounded query is required.") };
      rerender();
      return;
    }

    state.groundingMessages.push(createMessage("user", query));
    state.groundingMessages.push(
      createMessage("assistant", "Searching, fetching, and assembling grounded source text...", "pending"),
    );
    state.groundingStatus = { kind: "pending" };
    elements.groundingQuery.value = "";
    rerender();

    try {
      const payload = await requestJson(`${config.apiBaseUrl}/grounding/answer`, {
        query,
        search_limit: state.settings.groundingSearchLimit,
        fetch_limit: state.settings.groundingFetchLimit,
        system_prompt: state.settings.groundingSystemPrompt || null,
        selected_model: state.selectedModel || null,
      });
      state.groundingMessages[state.groundingMessages.length - 1] = createMessage(
        "assistant",
        buildGroundingAssistantText(payload),
        payload.answer_status === "model_error" ? "error" : "default",
      );
      state.groundingStatus = { kind: "success", payload };
      rerender();
      await refreshSnapshot();
    } catch (error) {
      state.groundingMessages[state.groundingMessages.length - 1] = createMessage("assistant", error.message, "error");
      state.groundingStatus = { kind: "error", error };
      rerender();
    }
  });

  elements.fetchForm.addEventListener("submit", async (event) => {
    event.preventDefault();
    const url = elements.fetchUrl.value.trim();
    if (!url) {
      state.fetchStatus = { kind: "error", error: new Error("A URL is required.") };
      rerender();
      return;
    }

    state.fetchStatus = { kind: "pending" };
    rerender();

    try {
      const payload = await requestJson(`${config.apiBaseUrl}/fetch`, { url });
      state.fetchStatus = { kind: "success", payload };
      rerender();
    } catch (error) {
      state.fetchStatus = { kind: "error", error };
      rerender();
    }
  });

  rerender();

  try {
    await refreshSnapshot();
  } catch (error) {
    elements.statusOutput.innerHTML = buildBanner("Initial snapshot failed", error.message, "error");
    setContextChip(elements.runtimeChip, "Runtime", "unavailable", "error");
  }
}

main().catch((error) => {
  const runtimeChip = document.getElementById("runtime-chip");
  if (runtimeChip) {
    runtimeChip.textContent = error.message;
    runtimeChip.className = "context-chip chip-error";
  }
});
