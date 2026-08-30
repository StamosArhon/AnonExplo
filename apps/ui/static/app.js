const STORAGE_KEYS = {
  selectedModel: "anonexplo.selectedModel",
  settings: "anonexplo.uiSettings",
  directChats: "anonexplo.directChats",
  activeChatId: "anonexplo.activeChatId",
};

const DEFAULT_SETTINGS = {
  chatSystemPrompt: "",
  groundingSystemPrompt: "",
  groundingSearchLimit: 8,
  groundingFetchLimit: 3,
};

const SOURCE_TOOLTIP_HIDE_DELAY_MS = 120;
const SOURCE_TOOLTIP_EDGE_GAP_PX = 16;
const SOURCE_TOOLTIP_OFFSET_PX = 12;

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

function createMessage(role, content, tone = "default", extra = {}) {
  const createdAt = getIsoTimestamp();
  return {
    id: makeId("msg"),
    role,
    content,
    tone,
    createdAt,
    time: getTimeLabel(createdAt),
    ...extra,
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

function getMessageCountLabel(count) {
  const numericCount = Number(count) || 0;
  return numericCount === 1 ? "1 message" : `${numericCount} messages`;
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
          id: typeof item.id === "string" && item.id.trim() ? item.id.trim() : makeId("msg"),
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

function escapeWithBreaks(value) {
  return escapeHtml(value || "").replaceAll("\n", "<br>");
}

function getSourceStatus(source, fetched, sourceError, contextMode) {
  const usesSnippetFallback = contextMode === "search_snippets" && !fetched && Boolean(source?.snippet);
  if (fetched) {
    return { label: "Fetched", className: "status-fetched" };
  }
  if (usesSnippetFallback) {
    return { label: "Snippet", className: "status-selected" };
  }
  if (sourceError) {
    return { label: "Issue", className: "status-failed" };
  }
  return { label: "Selected", className: "status-selected" };
}

function buildGroundingSourceBundle(payload) {
  const grounding = payload?.grounding || payload || {};
  const summary = grounding.summary || {};
  const fetchedById = new Map((grounding.fetched_sources || []).map((item) => [item.source_id, item]));
  const errorsById = new Map((grounding.errors || []).map((item) => [item.source_id, item]));
  const selectedSources = grounding.selected_sources || [];
  const sources = selectedSources.map((source) => {
    const fetched = fetchedById.get(source.source_id);
    const sourceError = errorsById.get(source.source_id);
    const status = getSourceStatus(source, fetched, sourceError, summary.context_mode);
    const previewText =
      fetched?.excerpt ||
      source.snippet ||
      sourceError?.message ||
      "No source preview is available for this item.";
    const detailText =
      fetched?.context_text ||
      fetched?.excerpt ||
      source.snippet ||
      sourceError?.message ||
      "No additional source detail is available.";

    return {
      sourceId: source.source_id,
      title: fetched?.document_title || source.title || source.source_id,
      url: fetched?.final_url || source.url,
      domain: source.domain,
      snippet: previewText,
      detailText,
      statusLabel: status.label,
      statusClass: status.className,
      retrievalMethod: fetched?.retrieval_method || null,
      contentQuality: fetched?.content_quality || null,
      warnings: Array.isArray(fetched?.warnings) ? fetched.warnings : [],
      errorMessage: sourceError?.message || null,
      errorCode: sourceError?.code || null,
      contextCharsUsed: fetched?.context_chars_used || 0,
      contentCharCount: fetched?.content_char_count || 0,
      wordCount: fetched?.word_count || 0,
    };
  });

  return {
    query: grounding.query || "",
    answerStatus: payload?.answer_status || "unknown",
    contextMode: summary.context_mode || "none",
    sourceCount: sources.length,
    fetchedCount: summary.fetched_sources || 0,
    failedCount: summary.failed_sources || 0,
    searchFailureCount:
      summary.search_failures || (grounding.errors || []).filter((item) => item.stage === "search").length,
    searchErrors: (grounding.errors || []).filter((item) => item.stage === "search"),
    sources,
  };
}

function getContextModeLabel(contextMode) {
  if (contextMode === "fetched_text") {
    return "Fetched article text";
  }
  if (contextMode === "fetched_plus_snippets") {
    return "Fetched text + snippet fallback";
  }
  if (contextMode === "search_snippets") {
    return "Snippet-backed context";
  }
  return "No source context";
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
      const messageCopy = message.sourceBundle
        ? renderGroundedMessageCopy(message)
        : `<div class="message-copy">${escapeWithBreaks(message.content || "")}</div>`;

      return `
        <div class="message-row ${rowClass}">
          <article class="message-card ${userClass} ${toneClass}">
            <div class="message-meta">
              <span class="message-role">${escapeHtml(roleLabel)}</span>
              <span class="message-time">${escapeHtml(message.time || "")}</span>
            </div>
            ${messageCopy}
          </article>
        </div>
      `;
    })
    .join("");

  scrollThreadToBottom(target);
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

function getGroundingMessageById(state, messageId) {
  return state.groundingMessages.find((item) => item.id === messageId) || null;
}

function normalizeCitationMarkup(value) {
  let normalized = String(value || "").replaceAll("\r\n", "\n").trim();
  if (!normalized) {
    return normalized;
  }

  const normalizeCitationGroup = (input) => {
    const sourceIds = [];
    const seenSourceIds = new Set();
    for (const match of input.matchAll(/S\d+/gi)) {
      const sourceId = String(match[0] || "").toUpperCase();
      if (!sourceId || seenSourceIds.has(sourceId)) {
        continue;
      }
      seenSourceIds.add(sourceId);
      sourceIds.push(`[${sourceId}]`);
    }
    return sourceIds.join("");
  };

  normalized = normalized.replace(
    /\[((?:\s*S\d+\s*(?:,|;|\/|\band\b)\s*)+\s*S\d+\s*)\]/gi,
    (_, citationGroup) => normalizeCitationGroup(citationGroup),
  );
  normalized = normalized.replace(
    /\[\s*S\d+\s*\](?:\s*(?:,|;|\/)?\s*(?:and|or)?\s*\[\s*S\d+\s*\])+/gi,
    (citationGroup) => normalizeCitationGroup(citationGroup),
  );
  return normalized;
}

function getTooltipPreviewText(source) {
  const preview = summarizeText(
    source?.detailText || source?.snippet || source?.errorMessage || "No source preview available.",
    220,
  );
  return preview === "No messages yet." ? "No source preview available." : preview;
}

function legacyBuildCitationTooltip(source) {
  return `
    <span class="source-tooltip" role="tooltip">
      <p class="source-tooltip-label">${escapeHtml(source.sourceId)} · ${escapeHtml(source.statusLabel)}</p>
      <a class="source-tooltip-link" href="${escapeHtml(source.url)}" target="_blank" rel="noreferrer">
        ${escapeHtml(source.title)}
      </a>
      <p class="source-tooltip-meta">${escapeHtml(source.domain || "unknown domain")}</p>
      <p class="source-tooltip-copy">${escapeHtml(getTooltipPreviewText(source))}</p>
    </span>
  `;
}

function getSourceReferenceLabel(sourceId) {
  const normalized = String(sourceId || "").trim();
  const match = normalized.match(/^S(.+)$/i);
  return match ? match[1] : normalized;
}

function legacyRenderGroundedMessageCopy(message) {
  const bundle = message?.sourceBundle;
  if (!bundle?.sources?.length) {
    return `<div class="message-copy">${escapeWithBreaks(message.content || "")}</div>`;
  }

  const sourceMap = new Map(bundle.sources.map((item) => [item.sourceId, item]));
  const content = normalizeCitationMarkup(String(message.content || ""));
  const citationPattern = /\[(S\d+)\]/gi;
  let lastIndex = 0;
  let rendered = "";

  for (const match of content.matchAll(citationPattern)) {
    const sourceId = String(match[1] || "").toUpperCase();
    const source = sourceMap.get(sourceId);
    const matchIndex = match.index ?? 0;
    rendered += `<span class="message-text-fragment">${escapeWithBreaks(content.slice(lastIndex, matchIndex))}</span>`;
    if (source) {
      rendered += `
        <sup class="source-chip-wrap">
          <button
            type="button"
            class="source-chip-button"
            data-open-source-drawer="true"
            data-message-id="${escapeHtml(message.id)}"
            data-source-id="${escapeHtml(source.sourceId)}"
            aria-label="Open source ${escapeHtml(source.sourceId)}"
          >
            ${escapeHtml(getSourceReferenceLabel(source.sourceId))}
          </button>
          ${buildCitationTooltip(source)}
        </sup>
      `;
    } else {
      rendered += `<span class="message-text-fragment">${escapeHtml(match[0])}</span>`;
    }
    lastIndex = matchIndex + match[0].length;
  }

  rendered += `<span class="message-text-fragment">${escapeWithBreaks(content.slice(lastIndex))}</span>`;

  const footerNotes = [];
  footerNotes.push(getContextModeLabel(bundle.contextMode));
  if (bundle.failedCount) {
    footerNotes.push(bundle.failedCount === 1 ? "1 source issue" : `${bundle.failedCount} source issues`);
  }
  if (bundle.searchFailureCount) {
    footerNotes.push(bundle.searchFailureCount === 1 ? "1 search issue" : `${bundle.searchFailureCount} search issues`);
  }

  return `
    <div class="message-copy message-copy-rich">${rendered}</div>
    <div class="message-source-footer">
      <button
        type="button"
        class="source-summary-button"
        data-open-source-drawer="true"
        data-message-id="${escapeHtml(message.id)}"
      >
        Sources ${escapeHtml(String(bundle.sourceCount))}
      </button>
      <span class="message-source-note">${escapeHtml(footerNotes.join(" · "))}</span>
    </div>
  `;
}

function buildCitationTooltip(source) {
  const statusLabel = `${source.sourceId} - ${source.statusLabel}`;
  return `
    <div class="source-tooltip" role="tooltip" data-placement="above">
      <p class="source-tooltip-label">${escapeHtml(statusLabel)}</p>
      <a class="source-tooltip-link" href="${escapeHtml(source.url)}" target="_blank" rel="noreferrer">
        ${escapeHtml(source.title)}
      </a>
      <p class="source-tooltip-meta">${escapeHtml(source.domain || "unknown domain")}</p>
      <p class="source-tooltip-copy">${escapeHtml(getTooltipPreviewText(source))}</p>
    </div>
  `;
}

function renderGroundedMessageCopy(message) {
  const bundle = message?.sourceBundle;
  if (!bundle?.sources?.length) {
    return `<div class="message-copy">${escapeWithBreaks(message.content || "")}</div>`;
  }

  const sourceMap = new Map(bundle.sources.map((item) => [item.sourceId, item]));
  const content = normalizeCitationMarkup(String(message.content || ""));
  const citationPattern = /\[(S\d+)\]/gi;
  let lastIndex = 0;
  let rendered = "";

  for (const match of content.matchAll(citationPattern)) {
    const sourceId = String(match[1] || "").toUpperCase();
    const source = sourceMap.get(sourceId);
    const matchIndex = match.index ?? 0;
    rendered += `<span class="message-text-fragment">${escapeWithBreaks(content.slice(lastIndex, matchIndex))}</span>`;
    if (source) {
      rendered += `<sup class="source-chip-wrap"><button type="button" class="source-chip-button" data-source-tooltip-trigger="true" data-open-source-drawer="true" data-message-id="${escapeHtml(message.id)}" data-source-id="${escapeHtml(source.sourceId)}" aria-label="Open source ${escapeHtml(source.sourceId)}">${escapeHtml(getSourceReferenceLabel(source.sourceId))}</button></sup>`;
    } else {
      rendered += `<span class="message-text-fragment">${escapeHtml(match[0])}</span>`;
    }
    lastIndex = matchIndex + match[0].length;
  }

  rendered += `<span class="message-text-fragment">${escapeWithBreaks(content.slice(lastIndex))}</span>`;

  const footerNotes = [getContextModeLabel(bundle.contextMode)];
  if (bundle.failedCount) {
    footerNotes.push(bundle.failedCount === 1 ? "1 source issue" : `${bundle.failedCount} source issues`);
  }
  if (bundle.searchFailureCount) {
    footerNotes.push(bundle.searchFailureCount === 1 ? "1 search issue" : `${bundle.searchFailureCount} search issues`);
  }

  return `
    <div class="message-copy message-copy-rich">${rendered}</div>
    <div class="message-source-footer">
      <button
        type="button"
        class="source-summary-button"
        data-open-source-drawer="true"
        data-message-id="${escapeHtml(message.id)}"
      >
        Sources ${escapeHtml(String(bundle.sourceCount))}
      </button>
      <span class="message-source-note">${escapeHtml(footerNotes.join(" - "))}</span>
    </div>
  `;
}

function buildHistoryRows(state) {
  return state.directChats
    .map((chat) => {
      const hasMessages = chat.messages.length > 0;
      const previewSource = hasMessages
        ? summarizeText(chat.messages[chat.messages.length - 1]?.content || "", 72)
        : "No direct-chat messages yet.";
      const activeClass = chat.id === state.activeChatId ? " active" : "";
      const stateLabel = chat.id === state.activeChatId ? "Current" : hasMessages ? "Saved" : "Empty";
      const stateClass = chat.id === state.activeChatId ? " history-state-active" : hasMessages ? " history-state-saved" : "";
      return `
        <article class="history-card${activeClass}">
          <button type="button" class="history-open" data-chat-id="${escapeHtml(chat.id)}">
            <span class="history-head">
              <span class="history-title">${escapeHtml(chat.title)}</span>
              <span class="history-state${stateClass}">${escapeHtml(stateLabel)}</span>
            </span>
            <span class="history-preview">${escapeHtml(previewSource)}</span>
            <span class="history-footer">
              <span class="history-time">${escapeHtml(getHistoryLabel(chat.updatedAt))}</span>
              <span class="history-count">${escapeHtml(getMessageCountLabel(chat.messages.length))}</span>
            </span>
          </button>
          <button
            type="button"
            class="history-delete"
            data-delete-chat-id="${escapeHtml(chat.id)}"
            aria-label="Delete ${escapeHtml(chat.title)}"
          >
            &times;
          </button>
        </article>
      `;
    })
    .join("");
}

function renderGroundingMeta(state, elements) {
  const latestMessage = [...state.groundingMessages].reverse().find((item) => item.sourceBundle);
  const bundle = latestMessage?.sourceBundle || null;
  const chips = [];

  if (state.groundingStatus.kind === "pending") {
    chips.push(buildChip("Status", "searching and fetching", "warn"));
  }

  if (bundle && bundle.contextMode === "search_snippets") {
    chips.push(
      buildChip(
        "Context",
        "snippet-backed",
        "warn",
      ),
    );
  }

  if (bundle && bundle.contextMode === "fetched_plus_snippets") {
    chips.push(buildChip("Context", "fetched + snippets", "warn"));
  }

  if (bundle && bundle.failedCount) {
    chips.push(buildChip("Issues", String(bundle.failedCount), "warn"));
  }

  if (bundle && bundle.searchFailureCount) {
    chips.push(buildChip("Search issues", String(bundle.searchFailureCount), "warn"));
  }

  if (state.groundingStatus.kind === "error") {
    chips.push(buildChip("Status", "request failed", "error"));
  }

  elements.groundingMeta.hidden = !chips.length;
  elements.groundingMeta.innerHTML = chips.join("");
}

function openSourceDrawer(state, messageId, focusSourceId = "") {
  const message = getGroundingMessageById(state, messageId);
  const bundle = message?.sourceBundle || null;
  if (!bundle?.sources?.length) {
    return false;
  }

  state.sourceDrawer = {
    open: true,
    messageId,
    focusSourceId: focusSourceId || bundle.sources[0].sourceId,
  };
  return true;
}

function closeSourceDrawer(state) {
  state.sourceDrawer = {
    open: false,
    messageId: "",
    focusSourceId: "",
  };
}

function renderSourceDrawer(state, elements) {
  const drawerState = state.sourceDrawer || { open: false, messageId: "", focusSourceId: "" };
  const message = drawerState.messageId ? getGroundingMessageById(state, drawerState.messageId) : null;
  const bundle = message?.sourceBundle || null;
  const activeSourceId = drawerState.focusSourceId || bundle?.sources?.[0]?.sourceId || "";

  if (!drawerState.open || !bundle?.sources?.length) {
    elements.sourceDrawerShell.hidden = true;
    elements.sourceDrawerMeta.innerHTML = "";
    elements.sourceDrawerList.innerHTML = "";
    return;
  }

  elements.sourceDrawerShell.hidden = false;
  elements.sourceDrawerTitle.textContent =
    bundle.contextMode === "search_snippets"
      ? "Current answer sources (snippet-backed)"
      : bundle.contextMode === "fetched_plus_snippets"
        ? "Current answer sources (fetched + snippets)"
        : "Current answer sources";
  elements.sourceDrawerMeta.innerHTML = [
    buildChip("Sources", String(bundle.sourceCount), "muted"),
    buildChip(
      "Context",
      bundle.contextMode === "fetched_text"
        ? "fetched text"
        : bundle.contextMode === "fetched_plus_snippets"
          ? "fetched + snippets"
          : bundle.contextMode === "search_snippets"
            ? "snippets"
            : "none",
      bundle.contextMode === "fetched_text" ? "ok" : "warn",
    ),
    buildChip("Fetched", String(bundle.fetchedCount), bundle.fetchedCount ? "ok" : "warn"),
    buildChip("Issues", String(bundle.failedCount), bundle.failedCount ? "warn" : "muted"),
    buildChip(
      "Search issues",
      String(bundle.searchFailureCount),
      bundle.searchFailureCount ? "warn" : "muted",
    ),
  ].join("");

  elements.sourceDrawerList.innerHTML = bundle.sources
    .map((source) => {
      const activeClass = activeSourceId === source.sourceId ? " active" : "";
      return `
        <article class="drawer-source-card${activeClass}" id="drawer-source-${escapeHtml(source.sourceId)}">
          <div class="status-line">
            <strong>${escapeHtml(source.sourceId)} - ${escapeHtml(source.title)}</strong>
            <span class="status-badge ${escapeHtml(source.statusClass)}">${escapeHtml(source.statusLabel)}</span>
          </div>
          <a class="drawer-source-link" href="${escapeHtml(source.url)}" target="_blank" rel="noreferrer">
            ${escapeHtml(source.title)}
          </a>
          <p class="meta">${escapeHtml(source.domain || "unknown domain")}</p>
          <p class="drawer-source-copy">${escapeHtml(source.snippet || "No source snippet available.")}</p>
          <div class="chip-row">
            ${
              source.retrievalMethod
                ? buildChip("Method", source.retrievalMethod, "muted")
                : ""
            }
            ${
              source.contentQuality
                ? buildChip("Quality", source.contentQuality, source.contentQuality === "usable" ? "ok" : "warn")
                : ""
            }
            ${
              source.contextCharsUsed
                ? buildChip("Context", String(source.contextCharsUsed), "muted")
                : ""
            }
          </div>
          ${
            source.warnings.length
              ? `<p class="meta warn">Warnings: ${escapeHtml(source.warnings.join(" | "))}</p>`
              : ""
          }
          ${
            source.errorMessage
              ? `<p class="meta error">Issue${source.errorCode ? ` (${escapeHtml(source.errorCode)})` : ""}: ${escapeHtml(source.errorMessage)}</p>`
              : ""
          }
        </article>
      `;
    })
    .join("");

  if (bundle.searchErrors?.length) {
    elements.sourceDrawerList.innerHTML += `
      <article class="drawer-source-card">
        <div class="status-line">
          <strong>Search variant issues</strong>
          <span class="status-badge status-failed">${escapeHtml(String(bundle.searchErrors.length))}</span>
        </div>
        ${bundle.searchErrors
          .map(
            (error) =>
              `<p class="meta">${escapeHtml(error.message || "A search variant failed.")}</p>`,
          )
          .join("")}
      </article>
    `;
  }

  const activeCard = elements.sourceDrawerList.querySelector(".drawer-source-card.active");
  if (activeCard) {
    requestAnimationFrame(() => {
      activeCard.scrollIntoView({ block: "nearest" });
    });
  }
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
}

function renderApp(config, state, elements) {
  renderChatHistory(state, elements);
  renderWorkspaceShell(state, elements);
  renderTopbar(config, state, elements);
  renderSettingsForm(state, elements);
  renderStackModal(state, elements);
  renderDirectChat(state, elements);
  renderGroundingWorkspace(state, elements);
  renderSourceDrawer(state, elements);
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
    return normalizeCitationMarkup(payload.answer || "(empty grounded answer)");
  }
  if (payload.answer_status === "insufficient_sources") {
    const searchFailureCount = Number(payload.grounding?.summary?.search_failures || 0);
    const searchNote = searchFailureCount
      ? ` ${searchFailureCount} search variant${searchFailureCount === 1 ? "" : "s"} also failed.`
      : "";
    return `Search finished, but not enough fetched source text was available to answer from derived material only.${searchNote}`;
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
    sourceDrawer: {
      open: false,
      messageId: "",
      focusSourceId: "",
    },
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
    groundingMeta: document.getElementById("grounding-meta"),
    fetchMeta: document.getElementById("fetch-meta"),
    fetchOutput: document.getElementById("fetch-output"),
    mainScroll: document.getElementById("main-scroll"),
    sourceDrawerShell: document.getElementById("source-drawer-shell"),
    sourceDrawerBackdrop: document.getElementById("source-drawer-backdrop"),
    closeSourceDrawerButton: document.getElementById("close-source-drawer"),
    sourceDrawerTitle: document.getElementById("source-drawer-title"),
    sourceDrawerMeta: document.getElementById("source-drawer-meta"),
    sourceDrawerList: document.getElementById("source-drawer-list"),
    sourceTooltipLayer: document.getElementById("source-tooltip-layer"),
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

  let activeTooltipTrigger = null;
  let sourceTooltipHideTimer = null;

  function clearSourceTooltipHideTimer() {
    if (sourceTooltipHideTimer === null) {
      return;
    }
    window.clearTimeout(sourceTooltipHideTimer);
    sourceTooltipHideTimer = null;
  }

  function hideSourceTooltip() {
    clearSourceTooltipHideTimer();
    activeTooltipTrigger = null;
    elements.sourceTooltipLayer.hidden = true;
    elements.sourceTooltipLayer.innerHTML = "";
  }

  function scheduleHideSourceTooltip() {
    clearSourceTooltipHideTimer();
    sourceTooltipHideTimer = window.setTimeout(() => {
      hideSourceTooltip();
    }, SOURCE_TOOLTIP_HIDE_DELAY_MS);
  }

  function resolveTooltipSource(trigger) {
    if (!trigger) {
      return null;
    }

    const messageId = String(trigger.dataset.messageId || "").trim();
    const sourceId = String(trigger.dataset.sourceId || "").trim().toUpperCase();
    if (!messageId || !sourceId) {
      return null;
    }

    const message = getGroundingMessageById(state, messageId);
    const source = message?.sourceBundle?.sources?.find((item) => item.sourceId === sourceId) || null;
    return source ? { source } : null;
  }

  function positionSourceTooltip(trigger) {
    const tooltip = elements.sourceTooltipLayer.firstElementChild;
    if (!trigger || !tooltip) {
      return;
    }

    const triggerRect = trigger.getBoundingClientRect();
    const tooltipRect = tooltip.getBoundingClientRect();
    const viewportWidth = window.innerWidth;
    const viewportHeight = window.innerHeight;

    let placement = "above";
    let top = triggerRect.top - tooltipRect.height - SOURCE_TOOLTIP_OFFSET_PX;
    if (top < SOURCE_TOOLTIP_EDGE_GAP_PX) {
      placement = "below";
      top = triggerRect.bottom + SOURCE_TOOLTIP_OFFSET_PX;
    }

    top = Math.min(
      Math.max(top, SOURCE_TOOLTIP_EDGE_GAP_PX),
      viewportHeight - tooltipRect.height - SOURCE_TOOLTIP_EDGE_GAP_PX,
    );

    let left = triggerRect.left + triggerRect.width / 2 - tooltipRect.width / 2;
    left = Math.min(
      Math.max(left, SOURCE_TOOLTIP_EDGE_GAP_PX),
      viewportWidth - tooltipRect.width - SOURCE_TOOLTIP_EDGE_GAP_PX,
    );

    tooltip.dataset.placement = placement;
    tooltip.style.top = `${Math.round(top)}px`;
    tooltip.style.left = `${Math.round(left)}px`;
  }

  function showSourceTooltip(trigger) {
    const resolved = resolveTooltipSource(trigger);
    if (!resolved) {
      hideSourceTooltip();
      return;
    }

    clearSourceTooltipHideTimer();
    activeTooltipTrigger = trigger;
    elements.sourceTooltipLayer.innerHTML = buildCitationTooltip(resolved.source);
    elements.sourceTooltipLayer.hidden = false;
    positionSourceTooltip(trigger);
  }

  function bindSourceTooltipTriggers() {
    document.querySelectorAll("[data-source-tooltip-trigger='true']").forEach((trigger) => {
      trigger.addEventListener("mouseenter", () => {
        showSourceTooltip(trigger);
      });
      trigger.addEventListener("focus", () => {
        showSourceTooltip(trigger);
      });
      trigger.addEventListener("mouseleave", (event) => {
        if (elements.sourceTooltipLayer.contains(event.relatedTarget)) {
          return;
        }
        scheduleHideSourceTooltip();
      });
      trigger.addEventListener("blur", (event) => {
        if (elements.sourceTooltipLayer.contains(event.relatedTarget)) {
          return;
        }
        scheduleHideSourceTooltip();
      });
    });
  }

  function persistModelSelection() {
    if (state.selectedModel) {
      safeStorageSet(STORAGE_KEYS.selectedModel, state.selectedModel);
      return;
    }
    safeStorageRemove(STORAGE_KEYS.selectedModel);
  }

  function rerender() {
    hideSourceTooltip();
    renderApp(config, state, elements);
    bindSourceTooltipTriggers();
  }

  function activateWorkspace(workspaceId) {
    state.activeWorkspace = workspaceId;
    if (workspaceId !== "workspace-grounding") {
      closeSourceDrawer(state);
    }
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

  [elements.groundingAnswer, elements.groundingMeta].forEach((container) => {
    container.addEventListener("click", (event) => {
      const sourceButton = event.target.closest("[data-open-source-drawer]");
      if (!sourceButton) {
        return;
      }

      const didOpen = openSourceDrawer(
        state,
        sourceButton.dataset.messageId,
        sourceButton.dataset.sourceId || "",
      );
      if (didOpen) {
        rerender();
      }
    });
  });

  elements.closeSourceDrawerButton.addEventListener("click", () => {
    closeSourceDrawer(state);
    rerender();
  });

  elements.sourceDrawerBackdrop.addEventListener("click", () => {
    closeSourceDrawer(state);
    rerender();
  });

  elements.sourceTooltipLayer.addEventListener("mouseenter", () => {
    clearSourceTooltipHideTimer();
  });

  elements.sourceTooltipLayer.addEventListener("mouseleave", (event) => {
    if (activeTooltipTrigger?.contains(event.relatedTarget)) {
      return;
    }
    scheduleHideSourceTooltip();
  });

  elements.mainScroll.addEventListener(
    "scroll",
    () => {
      hideSourceTooltip();
    },
    { passive: true },
  );

  window.addEventListener("resize", () => {
    if (!activeTooltipTrigger || elements.sourceTooltipLayer.hidden || !document.body.contains(activeTooltipTrigger)) {
      hideSourceTooltip();
      return;
    }
    positionSourceTooltip(activeTooltipTrigger);
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
    if (!elements.sourceTooltipLayer.hidden) {
      hideSourceTooltip();
      return;
    }
    if (!elements.sourceDrawerShell.hidden) {
      closeSourceDrawer(state);
      rerender();
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
    closeSourceDrawer(state);
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
      const sourceBundle = buildGroundingSourceBundle(payload);
      state.groundingMessages[state.groundingMessages.length - 1] = createMessage(
        "assistant",
        buildGroundingAssistantText(payload),
        payload.answer_status === "model_error" ? "error" : "default",
        sourceBundle.sources.length || sourceBundle.searchFailureCount ? { sourceBundle } : {},
      );
      state.groundingStatus = { kind: "success", payload };
      rerender();
      await refreshSnapshot();
    } catch (error) {
      state.groundingMessages[state.groundingMessages.length - 1] = createMessage("assistant", error.message, "error");
      state.groundingStatus = { kind: "error", error };
      closeSourceDrawer(state);
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
