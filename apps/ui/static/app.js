const STORAGE_KEY = "anonexplo.selectedModel";

const WORKSPACES = {
  "workspace-chat": {
    title: "Direct Chat",
    copy: "Prompt the selected local model while the stack details stay present but quieter.",
    focusId: "prompt-input",
  },
  "workspace-grounding": {
    title: "Grounded Answer",
    copy: "Search, fetch, and synthesize from readable source text without losing the sources.",
    focusId: "grounding-query",
  },
  "workspace-fetch": {
    title: "Fetch Inspector",
    copy: "Inspect readable article extraction before you hand anything off to the model.",
    focusId: "fetch-url",
  },
  "workspace-stack": {
    title: "Stack Snapshot",
    copy: "Review runtime readiness, provider routing, and local entrypoints in one place.",
    focusId: "refresh-status",
  },
};

async function getConfig() {
  const response = await fetch("/config.json");
  if (!response.ok) {
    throw new Error("Could not load UI config.");
  }
  return response.json();
}

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;");
}

async function fetchJson(url) {
  const response = await fetch(url);
  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    const error = new Error(
      typeof data.detail === "string" ? data.detail : data.detail?.message || "Request failed.",
    );
    error.detail = data.detail || null;
    error.status = response.status;
    throw error;
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

  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    const error = new Error(
      typeof data.detail === "string" ? data.detail : data.detail?.message || "Request failed.",
    );
    error.detail = data.detail || null;
    error.status = response.status;
    throw error;
  }
  return data;
}

function buildChip(label, value, type = "muted") {
  return `<span class="chip chip-${type}">${escapeHtml(label)}: ${escapeHtml(value)}</span>`;
}

function buildBanner(title, message, type = "warning", extra = "") {
  return `
    <div class="banner banner-${type}">
      <strong>${escapeHtml(title)}</strong>
      <div>${escapeHtml(message)}</div>
      ${extra}
    </div>
  `;
}

function getSelectionStatusClass(status) {
  if (status === "ready" || status === "ok" || status === "grounded") {
    return "ok";
  }
  if (status === "unreachable" || status === "invalid_response" || status === "model_error") {
    return "error";
  }
  return "warn";
}

function normalizeSnapshot(health, providers, modelsPayload) {
  const runtime = modelsPayload.runtime || health.model_runtime || {};
  const configuredModel =
    modelsPayload.configured_model ||
    providers.model?.model_name ||
    health.providers?.model_name ||
    runtime.configured_model ||
    "unknown";

  return {
    health,
    providers,
    runtime,
    configuredModel,
    availableModels: Array.isArray(modelsPayload.models) ? modelsPayload.models : [],
  };
}

function chooseSelectedModel(snapshot, previousSelection) {
  const availableModelIds = new Set(snapshot.availableModels.map((item) => item.id));

  if (previousSelection && (!availableModelIds.size || availableModelIds.has(previousSelection))) {
    return previousSelection;
  }

  if (snapshot.configuredModel && (!availableModelIds.size || availableModelIds.has(snapshot.configuredModel))) {
    return snapshot.configuredModel;
  }

  return snapshot.availableModels[0]?.id || snapshot.configuredModel || "";
}

function getStoredSelectedModel() {
  try {
    return window.localStorage.getItem(STORAGE_KEY) || "";
  } catch (error) {
    return "";
  }
}

function setStoredSelectedModel(value) {
  try {
    window.localStorage.setItem(STORAGE_KEY, value);
  } catch (error) {
    // Ignore localStorage failures in local-only browsers.
  }
}

function getTimestamp() {
  return new Intl.DateTimeFormat(undefined, {
    hour: "2-digit",
    minute: "2-digit",
  }).format(new Date());
}

function createMessage(role, content, tone = "default") {
  return {
    role,
    content,
    tone,
    time: getTimestamp(),
  };
}

function renderConversation(target, messages) {
  if (!messages.length) {
    target.innerHTML = '<div class="empty-state">No messages yet.</div>';
    return;
  }

  target.innerHTML = messages
    .map((message) => {
      const roleLabel = message.role === "user" ? "You" : "Assistant";
      const rowClass = message.role === "user" ? "message-row-user" : "message-row-assistant";
      const cardClass = message.role === "user" ? "message-card-user" : "message-card-assistant";
      const toneClass =
        message.tone === "pending"
          ? "message-pending"
          : message.tone === "error"
            ? "message-error"
            : "";

      return `
        <div class="message-row ${rowClass}">
          <article class="message-card ${cardClass} ${toneClass}">
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
}

function renderModelSelector(selectElement, noteElement, snapshot, selectedModel) {
  const options = [];

  if (!snapshot.availableModels.length) {
    options.push(
      `<option value="${escapeHtml(snapshot.configuredModel)}">${escapeHtml(snapshot.configuredModel)}</option>`,
    );
  } else {
    for (const model of snapshot.availableModels) {
      const selected = model.id === selectedModel ? " selected" : "";
      options.push(`<option value="${escapeHtml(model.id)}"${selected}>${escapeHtml(model.id)}</option>`);
    }
  }

  selectElement.innerHTML = options.join("");
  selectElement.value = selectedModel;
  noteElement.textContent =
    selectedModel === snapshot.configuredModel
      ? "Requests are using the configured default model."
      : "Requests are overriding the configured default model for this browser session.";
}

function renderSidebarSnapshot(runtimeTarget, glanceTarget, snapshot, selectedModel) {
  const runtimeStatus = snapshot.runtime.status || "unknown";
  runtimeTarget.innerHTML = `
    ${buildChip("Runtime", runtimeStatus, getSelectionStatusClass(runtimeStatus))}
    ${buildChip("Search", snapshot.providers.search?.provider || "unknown", "muted")}
  `;

  glanceTarget.innerHTML = `
    <div class="glance-line"><span>Selected model</span><strong>${escapeHtml(selectedModel || snapshot.configuredModel)}</strong></div>
    <div class="glance-line"><span>Configured default</span><strong>${escapeHtml(snapshot.configuredModel)}</strong></div>
    <div class="glance-line"><span>Model provider</span><strong>${escapeHtml(snapshot.providers.model?.provider || "unknown")}</strong></div>
    <div class="glance-line"><span>Fetch path</span><strong>${escapeHtml(snapshot.providers.fetch?.base_url || "unknown")}</strong></div>
  `;
}

function setHeaderChip(element, text, type = "muted") {
  element.textContent = text;
  element.className = `context-chip chip-${type}`;
}

function renderTopbarSnapshot(config, state, elements) {
  setHeaderChip(elements.environmentChip, `Environment · ${config.environment}`, "muted");
  setHeaderChip(
    elements.runtimeChip,
    `Runtime · ${state.snapshot.runtime.status || "unknown"}`,
    getSelectionStatusClass(state.snapshot.runtime.status || "unknown"),
  );
  setHeaderChip(
    elements.modelChip,
    `Model · ${state.selectedModel || state.snapshot.configuredModel}`,
    "active",
  );
  setHeaderChip(
    elements.searchChip,
    `Search · ${state.snapshot.providers.search?.provider || "unknown"}`,
    "muted",
  );
}

function renderRuntimeSummary(target, runtime) {
  const availableModels = Array.isArray(runtime.available_models) ? runtime.available_models : [];
  if (!runtime.status) {
    target.innerHTML = '<div class="meta">Runtime details are not available yet.</div>';
    return;
  }

  target.innerHTML = `
    <div>${buildChip("Status", runtime.status, getSelectionStatusClass(runtime.status))}</div>
    <div>${buildChip("Reachable", runtime.reachable ? "yes" : "no", runtime.reachable ? "ok" : "error")}</div>
    <div>${buildChip("Advertised", availableModels.length, availableModels.length ? "ok" : "warn")}</div>
    <div class="meta">${escapeHtml(runtime.checked_url || "unknown")}</div>
  `;
}

function renderProviderSummary(target, snapshot) {
  target.innerHTML = `
    <div>${buildChip("Model", snapshot.providers.model?.provider || "unknown", "muted")}</div>
    <div>${buildChip("Search", snapshot.providers.search?.provider || "unknown", "muted")}</div>
    <div>${buildChip("Fetch", snapshot.providers.fetch?.base_url || "unknown", "muted")}</div>
    <div>${buildChip("Runtime", snapshot.providers.model?.runtime_profile || "unknown", "muted")}</div>
  `;
}

function renderStatusPanel(target, snapshot, selectedModel) {
  const runtime = snapshot.runtime;
  const backendClass =
    snapshot.health.status === "ok"
      ? "ok"
      : snapshot.health.status === "degraded"
        ? "warn"
        : "error";
  const advertisedModels = snapshot.availableModels
    .map((item) =>
      buildChip(item.id, item.id === selectedModel ? "selected" : "available", item.id === selectedModel ? "active" : "muted"),
    )
    .join("");

  const cards = [
    `<div class="status-card"><strong>Backend status:</strong> <span class="${backendClass}">${escapeHtml(snapshot.health.status)}</span></div>`,
    `<div class="status-card"><strong>Configured default:</strong> ${escapeHtml(snapshot.configuredModel)}</div>`,
    `<div class="status-card"><strong>Selected for requests:</strong> ${escapeHtml(selectedModel || snapshot.configuredModel)}</div>`,
  ];

  if (runtime.error) {
    cards.push(buildBanner("Runtime note", runtime.error, "warning"));
  }

  if (advertisedModels) {
    cards.push(`<div class="status-card"><strong>Advertised models</strong><div class="chip-row">${advertisedModels}</div></div>`);
  }

  target.innerHTML = cards.join("");
}

function renderChatSuccess(metaTarget, payload) {
  metaTarget.innerHTML = `
    ${buildChip("Selected", payload.selection.selected_model, "active")}
    ${buildChip("Configured", payload.selection.configured_model, "muted")}
    ${buildChip("Runtime", payload.runtime_status, getSelectionStatusClass(payload.runtime_status))}
    ${buildChip("Usage", payload.usage.total_tokens || 0, "muted")}
  `;
}

function renderChatError(metaTarget, error) {
  const detail = error.detail || {};
  const selection = detail.selection || {};
  const runtime = detail.runtime || {};
  metaTarget.innerHTML = `
    ${selection.selected_model ? buildChip("Selected", selection.selected_model, "warn") : ""}
    ${selection.configured_model ? buildChip("Configured", selection.configured_model, "muted") : ""}
    ${runtime.status ? buildChip("Runtime", runtime.status, getSelectionStatusClass(runtime.status)) : ""}
  `;
}

function renderFetchSuccess(target, metaTarget, payload) {
  metaTarget.innerHTML = `
    ${buildChip("Title", payload.title || "Untitled", "muted")}
    ${buildChip("Chars", payload.content_char_count || 0, "muted")}
    ${buildChip("Words", payload.word_count || 0, "muted")}
  `;

  target.innerHTML = `
    <h3>${escapeHtml(payload.title || "Untitled")}</h3>
    <p class="meta">${escapeHtml(payload.final_url || payload.requested_url || "")}</p>
    <p>${escapeHtml(payload.excerpt || "No excerpt available.")}</p>
    <div class="source-text">${escapeHtml(payload.content_text || "No article text returned.")}</div>
  `;
}

function renderFetchError(target, metaTarget, error) {
  metaTarget.innerHTML = "";
  target.innerHTML = buildBanner("Fetch request failed", error.message, "error");
}

function renderGroundingSuccess(metaTarget, summaryTarget, errorsTarget, sourcesTarget, payload) {
  const grounding = payload.grounding || payload;
  const fetchedById = new Map((grounding.fetched_sources || []).map((item) => [item.source_id, item]));
  const groupedErrors = grounding.errors || [];

  metaTarget.innerHTML = `
    ${payload.selection ? buildChip("Selected", payload.selection.selected_model, "active") : ""}
    ${payload.selection ? buildChip("Configured", payload.selection.configured_model, "muted") : ""}
    ${payload.runtime_status ? buildChip("Runtime", payload.runtime_status, getSelectionStatusClass(payload.runtime_status)) : ""}
    ${buildChip("Answer state", payload.answer_status || "preview", getSelectionStatusClass(payload.answer_status || "preview"))}
  `;

  summaryTarget.innerHTML = `
    <div class="status-card"><strong>Search hits:</strong> ${escapeHtml(grounding.summary.search_results)}</div>
    <div class="status-card"><strong>Unique hits:</strong> ${escapeHtml(grounding.summary.unique_search_results)}</div>
    <div class="status-card"><strong>Selected:</strong> ${escapeHtml(grounding.summary.selected_sources)}</div>
    <div class="status-card"><strong>Fetched:</strong> ${escapeHtml(grounding.summary.fetched_sources)}</div>
    <div class="status-card"><strong>Failures:</strong> ${escapeHtml(grounding.summary.failed_sources)}</div>
    <div class="status-card"><strong>Context chars:</strong> ${escapeHtml(grounding.summary.grounding_characters)}</div>
  `;

  if (groupedErrors.length) {
    errorsTarget.innerHTML = groupedErrors
      .map((item) =>
        buildBanner(
          item.source_id ? `Source ${item.source_id} failed` : "Grounding issue",
          item.message || "Unknown grounding error.",
          "warning",
          item.url ? `<div class="meta">${escapeHtml(item.url)}</div>` : "",
        ),
      )
      .join("");
  } else {
    errorsTarget.innerHTML = "";
  }

  if (!(grounding.selected_sources || []).length) {
    sourcesTarget.innerHTML = '<div class="result-card">No sources were selected from the search results.</div>';
    return;
  }

  sourcesTarget.innerHTML = grounding.selected_sources
    .map((source) => {
      const fetched = fetchedById.get(source.source_id);
      const error = groupedErrors.find((item) => item.source_id === source.source_id);
      const statusClass = fetched ? "status-fetched" : error ? "status-failed" : "status-selected";
      const statusLabel = fetched ? "Fetched" : error ? "Failed" : "Selected";

      return `
        <div class="result-card">
          <div class="status-line">
            <strong>${escapeHtml(source.title)}</strong>
            <span class="status-badge ${statusClass}">${escapeHtml(statusLabel)}</span>
          </div>
          <div class="meta">
            Rank ${escapeHtml(source.search_rank)} &middot; ${escapeHtml(source.domain)} &middot;
            <a href="${escapeHtml(source.url)}" target="_blank" rel="noreferrer">${escapeHtml(source.url)}</a>
          </div>
          <div class="source-body">
            <p>${escapeHtml(source.snippet || "No search snippet available.")}</p>
            ${
              fetched
                ? `
                  <div class="meta">Context used: ${escapeHtml(fetched.context_chars_used)} chars &middot; Extracted: ${escapeHtml(fetched.content_char_count)} chars &middot; ${escapeHtml(fetched.word_count)} words</div>
                  <div class="source-text">${escapeHtml(fetched.context_text || fetched.excerpt || "No source text available.")}</div>
                `
                : error
                  ? `<p class="error">${escapeHtml(error.message)}</p>`
                  : `<p class="meta">Selected for grounding but not fetched.</p>`
            }
          </div>
        </div>
      `;
    })
    .join("");
}

function renderGroundingError(metaTarget, summaryTarget, errorsTarget, sourcesTarget, error) {
  const detail = error.detail || {};
  const selection = detail.selection || {};
  const runtime = detail.runtime || {};

  metaTarget.innerHTML = `
    ${selection.selected_model ? buildChip("Selected", selection.selected_model, "warn") : ""}
    ${selection.configured_model ? buildChip("Configured", selection.configured_model, "muted") : ""}
    ${runtime.status ? buildChip("Runtime", runtime.status, getSelectionStatusClass(runtime.status)) : ""}
  `;
  summaryTarget.innerHTML = "";
  errorsTarget.innerHTML = buildBanner("Grounded answer failed", error.message, "error");
  sourcesTarget.innerHTML = "";
}

function buildGroundingAssistantText(payload) {
  if (payload.answer_status === "grounded") {
    return payload.answer || "(empty grounded answer)";
  }
  if (payload.answer_status === "insufficient_sources") {
    return "Search finished, but no fetched source text was available for model synthesis.";
  }
  if (payload.answer_status === "model_error") {
    return payload.model_error || "The sources were fetched, but model synthesis failed.";
  }
  return "Grounding preview generated without model synthesis.";
}

function setActiveWorkspace(state, workspaceId, elements) {
  state.activeWorkspace = workspaceId;

  for (const [id] of Object.entries(WORKSPACES)) {
    const section = document.getElementById(id);
    section.hidden = id !== workspaceId;
  }

  for (const button of document.querySelectorAll("[data-workspace-target]")) {
    button.classList.toggle("active", button.dataset.workspaceTarget === workspaceId);
  }

  elements.workspaceTitle.textContent = WORKSPACES[workspaceId].title;
  elements.workspaceCopy.textContent = WORKSPACES[workspaceId].copy;
}

function focusActiveWorkspace(state) {
  const focusId = WORKSPACES[state.activeWorkspace]?.focusId;
  if (!focusId) {
    return;
  }
  const focusTarget = document.getElementById(focusId);
  if (focusTarget) {
    focusTarget.focus();
  }
}

async function main() {
  const config = await getConfig();
  const apiBaseUrl = config.apiBaseUrl;
  const state = {
    snapshot: null,
    selectedModel: getStoredSelectedModel(),
    activeWorkspace: "workspace-chat",
    messages: {
      chat: [
        createMessage(
          "assistant",
          "Prompt the selected local model from here. Switch models from the sidebar and keep the rest of the stack quiet until you need it.",
        ),
      ],
      grounding: [
        createMessage(
          "assistant",
          "Use grounded answers when you want search, readable page fetches, and source inspection to stay attached to the answer.",
        ),
      ],
    },
  };

  const elements = {
    environmentChip: document.getElementById("environment-chip"),
    runtimeChip: document.getElementById("runtime-chip"),
    modelChip: document.getElementById("model-chip"),
    searchChip: document.getElementById("search-chip"),
    workspaceTitle: document.getElementById("active-workspace-title"),
    workspaceCopy: document.getElementById("active-workspace-copy"),
    modelSelect: document.getElementById("model-select"),
    modelSelectionNote: document.getElementById("model-selection-note"),
    sidebarRuntimeStatus: document.getElementById("sidebar-runtime-status"),
    sidebarStackGlance: document.getElementById("sidebar-stack-glance"),
    configuredModel: document.getElementById("configured-model"),
    runtimeNote: document.getElementById("runtime-note"),
    runtimeSummary: document.getElementById("runtime-summary"),
    providerSummary: document.getElementById("provider-summary"),
    statusOutput: document.getElementById("status-output"),
    chatMeta: document.getElementById("chat-meta"),
    chatOutput: document.getElementById("chat-output"),
    fetchMeta: document.getElementById("fetch-meta"),
    fetchOutput: document.getElementById("fetch-output"),
    groundingMeta: document.getElementById("grounding-meta"),
    groundingAnswer: document.getElementById("grounding-answer"),
    groundingErrors: document.getElementById("grounding-errors"),
    groundingSummary: document.getElementById("grounding-summary"),
    groundingOutput: document.getElementById("grounding-output"),
    openSearchLink: document.getElementById("open-search-link"),
    stackSearchLink: document.getElementById("stack-search-link"),
  };

  const standaloneSearchUrl =
    config.standaloneSearchUrl ||
    `${window.location.protocol}//${window.location.hostname}:8085`;
  elements.openSearchLink.href = standaloneSearchUrl;
  elements.stackSearchLink.href = standaloneSearchUrl;
  elements.environmentChip.textContent = `Environment · ${config.environment}`;

  renderConversation(elements.chatOutput, state.messages.chat);
  renderConversation(elements.groundingAnswer, state.messages.grounding);
  setActiveWorkspace(state, state.activeWorkspace, elements);

  async function refreshSnapshot() {
    elements.statusOutput.innerHTML = '<div class="status-card">Refreshing local workbench snapshot...</div>';

    const [health, providers, modelsPayload] = await Promise.all([
      fetchJson(`${apiBaseUrl}/health`),
      fetchJson(`${apiBaseUrl}/system/providers`),
      fetchJson(`${apiBaseUrl}/model/models`),
    ]);

    state.snapshot = normalizeSnapshot(health, providers, modelsPayload);
    state.selectedModel = chooseSelectedModel(state.snapshot, state.selectedModel);
    setStoredSelectedModel(state.selectedModel);

    renderModelSelector(elements.modelSelect, elements.modelSelectionNote, state.snapshot, state.selectedModel);
    renderSidebarSnapshot(
      elements.sidebarRuntimeStatus,
      elements.sidebarStackGlance,
      state.snapshot,
      state.selectedModel,
    );
    renderTopbarSnapshot(config, state, elements);
    elements.configuredModel.textContent = state.snapshot.configuredModel;
    elements.runtimeNote.textContent =
      state.snapshot.runtime.error || "Runtime readiness is checked against the live model endpoint.";
    renderRuntimeSummary(elements.runtimeSummary, state.snapshot.runtime);
    renderProviderSummary(elements.providerSummary, state.snapshot);
    renderStatusPanel(elements.statusOutput, state.snapshot, state.selectedModel);
  }

  elements.modelSelect.addEventListener("change", () => {
    state.selectedModel = elements.modelSelect.value;
    setStoredSelectedModel(state.selectedModel);
    if (state.snapshot) {
      renderModelSelector(elements.modelSelect, elements.modelSelectionNote, state.snapshot, state.selectedModel);
      renderSidebarSnapshot(
        elements.sidebarRuntimeStatus,
        elements.sidebarStackGlance,
        state.snapshot,
        state.selectedModel,
      );
      renderTopbarSnapshot(config, state, elements);
      renderStatusPanel(elements.statusOutput, state.snapshot, state.selectedModel);
    }
  });

  document.getElementById("refresh-status").addEventListener("click", async () => {
    try {
      await refreshSnapshot();
    } catch (error) {
      elements.statusOutput.innerHTML = buildBanner("Snapshot refresh failed", error.message, "error");
      setHeaderChip(elements.runtimeChip, "Runtime · refresh failed", "error");
      elements.sidebarRuntimeStatus.innerHTML = buildChip("Runtime", "refresh failed", "error");
    }
  });

  document.getElementById("focus-composer").addEventListener("click", () => {
    focusActiveWorkspace(state);
  });

  for (const button of document.querySelectorAll("[data-workspace-target]")) {
    button.addEventListener("click", () => {
      setActiveWorkspace(state, button.dataset.workspaceTarget, elements);
      focusActiveWorkspace(state);
    });
  }

  document.getElementById("chat-form").addEventListener("submit", async (event) => {
    event.preventDefault();
    const promptInput = document.getElementById("prompt-input");
    const prompt = promptInput.value.trim();
    if (!prompt) {
      elements.chatMeta.innerHTML = buildChip("Prompt", "required", "warn");
      return;
    }

    state.messages.chat.push(createMessage("user", prompt), createMessage("assistant", "Waiting for the local model...", "pending"));
    renderConversation(elements.chatOutput, state.messages.chat);
    elements.chatMeta.innerHTML = "";
    promptInput.value = "";

    try {
      const payload = {
        prompt,
        system_prompt: document.getElementById("system-input").value || null,
        selected_model: state.selectedModel || null,
      };
      const data = await requestJson(`${apiBaseUrl}/model/chat`, payload);
      state.messages.chat[state.messages.chat.length - 1] = createMessage(
        "assistant",
        data.answer || "(empty response)",
      );
      renderConversation(elements.chatOutput, state.messages.chat);
      renderChatSuccess(elements.chatMeta, data);
      await refreshSnapshot();
    } catch (error) {
      state.messages.chat[state.messages.chat.length - 1] = createMessage("assistant", error.message, "error");
      renderConversation(elements.chatOutput, state.messages.chat);
      renderChatError(elements.chatMeta, error);
    }
  });

  document.getElementById("fetch-form").addEventListener("submit", async (event) => {
    event.preventDefault();
    const urlInput = document.getElementById("fetch-url");
    const url = urlInput.value.trim();
    if (!url) {
      elements.fetchMeta.innerHTML = buildChip("URL", "required", "warn");
      return;
    }

    elements.fetchMeta.innerHTML = "";
    elements.fetchOutput.innerHTML = '<div class="empty-state">Fetching and parsing article...</div>';

    try {
      const data = await requestJson(`${apiBaseUrl}/fetch`, { url });
      renderFetchSuccess(elements.fetchOutput, elements.fetchMeta, data);
    } catch (error) {
      renderFetchError(elements.fetchOutput, elements.fetchMeta, error);
    }
  });

  document.getElementById("grounding-form").addEventListener("submit", async (event) => {
    event.preventDefault();
    const queryInput = document.getElementById("grounding-query");
    const query = queryInput.value.trim();
    if (!query) {
      elements.groundingMeta.innerHTML = buildChip("Query", "required", "warn");
      return;
    }

    state.messages.grounding.push(
      createMessage("user", query),
      createMessage("assistant", "Searching, fetching, and assembling readable source context...", "pending"),
    );
    renderConversation(elements.groundingAnswer, state.messages.grounding);
    elements.groundingMeta.innerHTML = "";
    elements.groundingErrors.innerHTML = "";
    elements.groundingSummary.innerHTML = "";
    elements.groundingOutput.innerHTML = "";
    queryInput.value = "";

    try {
      const payload = {
        query,
        search_limit: Number(document.getElementById("search-limit").value),
        fetch_limit: Number(document.getElementById("fetch-limit").value),
        selected_model: state.selectedModel || null,
      };
      const data = await requestJson(`${apiBaseUrl}/grounding/answer`, payload);
      state.messages.grounding[state.messages.grounding.length - 1] = createMessage(
        "assistant",
        buildGroundingAssistantText(data),
        data.answer_status === "model_error" ? "error" : "default",
      );
      renderConversation(elements.groundingAnswer, state.messages.grounding);
      renderGroundingSuccess(
        elements.groundingMeta,
        elements.groundingSummary,
        elements.groundingErrors,
        elements.groundingOutput,
        data,
      );
      await refreshSnapshot();
    } catch (error) {
      state.messages.grounding[state.messages.grounding.length - 1] = createMessage(
        "assistant",
        error.message,
        "error",
      );
      renderConversation(elements.groundingAnswer, state.messages.grounding);
      renderGroundingError(
        elements.groundingMeta,
        elements.groundingSummary,
        elements.groundingErrors,
        elements.groundingOutput,
        error,
      );
    }
  });

  try {
    await refreshSnapshot();
  } catch (error) {
    elements.statusOutput.innerHTML = buildBanner("Initial snapshot failed", error.message, "error");
    setHeaderChip(elements.runtimeChip, "Runtime · unavailable", "error");
    elements.sidebarRuntimeStatus.innerHTML = buildChip("Runtime", "unavailable", "error");
  }
}

main().catch((error) => {
  document.getElementById("environment-chip").textContent = error.message;
});
