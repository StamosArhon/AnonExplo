const STORAGE_KEY = "anonexplo.selectedModel";

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
  if (status === "ready") {
    return "ok";
  }
  if (status === "unreachable" || status === "invalid_response") {
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

function renderModelSelector(selectElement, noteElement, snapshot, selectedModel) {
  const options = [];
  if (!snapshot.availableModels.length) {
    options.push(`<option value="${escapeHtml(snapshot.configuredModel)}">${escapeHtml(snapshot.configuredModel)}</option>`);
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
  const advertisedModels = snapshot.availableModels
    .map((item) =>
      buildChip(item.id, item.id === selectedModel ? "selected" : "available", item.id === selectedModel ? "active" : "muted"),
    )
    .join("");

  const cards = [
    `<div class="status-card"><strong>Backend status:</strong> <span class="${snapshot.health.status === "ok" ? "ok" : "error"}">${escapeHtml(snapshot.health.status)}</span></div>`,
    `<div class="status-card"><strong>Configured default:</strong> ${escapeHtml(snapshot.configuredModel)}</div>`,
    `<div class="status-card"><strong>Selected for requests:</strong> ${escapeHtml(selectedModel || snapshot.configuredModel)}</div>`,
    `<div class="status-card"><strong>Runtime checked at:</strong> ${escapeHtml(runtime.checked_url || "unknown")}</div>`,
  ];

  if (runtime.error) {
    cards.push(buildBanner("Runtime note", runtime.error, "warning"));
  }

  if (advertisedModels) {
    cards.push(`<div class="status-card"><strong>Advertised models</strong><div class="chip-row">${advertisedModels}</div></div>`);
  }

  target.innerHTML = cards.join("");
}

function renderChatSuccess(target, metaTarget, payload) {
  metaTarget.innerHTML = `
    ${buildChip("Selected", payload.selection.selected_model, "active")}
    ${buildChip("Configured", payload.selection.configured_model, "muted")}
    ${buildChip("Runtime", payload.runtime_status, getSelectionStatusClass(payload.runtime_status))}
    ${buildChip("Usage", payload.usage.total_tokens || 0, "muted")}
  `;
  target.textContent = payload.answer || "(empty response)";
}

function renderChatError(target, metaTarget, error) {
  const detail = error.detail || {};
  const selection = detail.selection || {};
  const runtime = detail.runtime || {};
  metaTarget.innerHTML = `
    ${selection.selected_model ? buildChip("Selected", selection.selected_model, "warn") : ""}
    ${selection.configured_model ? buildChip("Configured", selection.configured_model, "muted") : ""}
    ${runtime.status ? buildChip("Runtime", runtime.status, getSelectionStatusClass(runtime.status)) : ""}
  `;
  target.innerHTML = buildBanner("Chat request failed", error.message, "error");
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

function renderGrounding(summaryTarget, metaTarget, answerTarget, errorsTarget, sourcesTarget, payload) {
  const grounding = payload.grounding || payload;
  const fetchedById = new Map((grounding.fetched_sources || []).map((item) => [item.source_id, item]));
  const groupedErrors = grounding.errors || [];

  metaTarget.innerHTML = `
    ${payload.selection ? buildChip("Selected", payload.selection.selected_model, "active") : ""}
    ${payload.selection ? buildChip("Configured", payload.selection.configured_model, "muted") : ""}
    ${payload.runtime_status ? buildChip("Runtime", payload.runtime_status, getSelectionStatusClass(payload.runtime_status)) : ""}
    ${buildChip("Answer state", payload.answer_status || "preview", payload.answer_status === "grounded" ? "ok" : payload.answer_status === "model_error" ? "error" : "warn")}
  `;

  summaryTarget.innerHTML = `
    <div class="status-card"><strong>Search hits:</strong> ${escapeHtml(grounding.summary.search_results)}</div>
    <div class="status-card"><strong>Unique hits:</strong> ${escapeHtml(grounding.summary.unique_search_results)}</div>
    <div class="status-card"><strong>Selected:</strong> ${escapeHtml(grounding.summary.selected_sources)}</div>
    <div class="status-card"><strong>Fetched:</strong> ${escapeHtml(grounding.summary.fetched_sources)}</div>
    <div class="status-card"><strong>Failures:</strong> ${escapeHtml(grounding.summary.failed_sources)}</div>
    <div class="status-card"><strong>Context chars:</strong> ${escapeHtml(grounding.summary.grounding_characters)}</div>
  `;

  if (payload.answer_status === "grounded") {
    answerTarget.textContent = payload.answer || "(empty grounded answer)";
  } else if (payload.answer_status === "insufficient_sources") {
    answerTarget.innerHTML = buildBanner(
      "No grounded answer yet",
      "The search completed, but no fetched source text was available for model synthesis.",
      "warning",
    );
  } else if (payload.answer_status === "model_error") {
    answerTarget.innerHTML = buildBanner(
      "Model synthesis failed",
      payload.model_error || "The sources were fetched, but the model request failed.",
      "error",
    );
  } else {
    answerTarget.textContent = "Grounding preview generated without model synthesis.";
  }

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

function renderGroundingError(answerTarget, metaTarget, errorsTarget, summaryTarget, sourcesTarget, error) {
  const detail = error.detail || {};
  const selection = detail.selection || {};
  const runtime = detail.runtime || {};

  metaTarget.innerHTML = `
    ${selection.selected_model ? buildChip("Selected", selection.selected_model, "warn") : ""}
    ${selection.configured_model ? buildChip("Configured", selection.configured_model, "muted") : ""}
    ${runtime.status ? buildChip("Runtime", runtime.status, getSelectionStatusClass(runtime.status)) : ""}
  `;
  answerTarget.innerHTML = buildBanner("Grounded answer failed", error.message, "error");
  errorsTarget.innerHTML = "";
  summaryTarget.innerHTML = "";
  sourcesTarget.innerHTML = "";
}

async function main() {
  const config = await getConfig();
  const apiBaseUrl = config.apiBaseUrl;
  const state = {
    snapshot: null,
    selectedModel: getStoredSelectedModel(),
  };

  const environmentChip = document.getElementById("environment-chip");
  const runtimeChip = document.getElementById("runtime-chip");
  const modelSelect = document.getElementById("model-select");
  const modelSelectionNote = document.getElementById("model-selection-note");
  const configuredModel = document.getElementById("configured-model");
  const runtimeNote = document.getElementById("runtime-note");
  const runtimeSummary = document.getElementById("runtime-summary");
  const providerSummary = document.getElementById("provider-summary");
  const statusOutput = document.getElementById("status-output");

  const chatMeta = document.getElementById("chat-meta");
  const chatOutput = document.getElementById("chat-output");

  const fetchMeta = document.getElementById("fetch-meta");
  const fetchOutput = document.getElementById("fetch-output");

  const groundingMeta = document.getElementById("grounding-meta");
  const groundingAnswer = document.getElementById("grounding-answer");
  const groundingErrors = document.getElementById("grounding-errors");
  const groundingSummary = document.getElementById("grounding-summary");
  const groundingOutput = document.getElementById("grounding-output");

  environmentChip.textContent = `Environment: ${config.environment}`;

  async function refreshSnapshot() {
    statusOutput.innerHTML = '<div class="status-card">Refreshing local workbench snapshot...</div>';

    const [health, providers, modelsPayload] = await Promise.all([
      fetchJson(`${apiBaseUrl}/health`),
      fetchJson(`${apiBaseUrl}/system/providers`),
      fetchJson(`${apiBaseUrl}/model/models`),
    ]);

    state.snapshot = normalizeSnapshot(health, providers, modelsPayload);
    state.selectedModel = chooseSelectedModel(state.snapshot, state.selectedModel);
    setStoredSelectedModel(state.selectedModel);

    renderModelSelector(modelSelect, modelSelectionNote, state.snapshot, state.selectedModel);
    configuredModel.textContent = state.snapshot.configuredModel;
    runtimeChip.textContent = `Runtime: ${state.snapshot.runtime.status || "unknown"}`;
    runtimeChip.className = `hero-meta hero-meta-secondary chip-${getSelectionStatusClass(state.snapshot.runtime.status || "unknown")}`;
    runtimeNote.textContent = state.snapshot.runtime.error || "Runtime readiness is checked against the live model endpoint.";
    renderRuntimeSummary(runtimeSummary, state.snapshot.runtime);
    renderProviderSummary(providerSummary, state.snapshot);
    renderStatusPanel(statusOutput, state.snapshot, state.selectedModel);
  }

  modelSelect.addEventListener("change", () => {
    state.selectedModel = modelSelect.value;
    setStoredSelectedModel(state.selectedModel);
    if (state.snapshot) {
      renderModelSelector(modelSelect, modelSelectionNote, state.snapshot, state.selectedModel);
      renderStatusPanel(statusOutput, state.snapshot, state.selectedModel);
    }
  });

  document.getElementById("refresh-status").addEventListener("click", async () => {
    try {
      await refreshSnapshot();
    } catch (error) {
      statusOutput.innerHTML = buildBanner("Snapshot refresh failed", error.message, "error");
      runtimeChip.textContent = "Runtime: refresh failed";
    }
  });

  document.getElementById("chat-form").addEventListener("submit", async (event) => {
    event.preventDefault();
    chatMeta.innerHTML = "";
    chatOutput.textContent = "Waiting for the local model...";

    try {
      const payload = {
        prompt: document.getElementById("prompt-input").value,
        system_prompt: document.getElementById("system-input").value || null,
        selected_model: state.selectedModel || null,
      };
      const data = await requestJson(`${apiBaseUrl}/model/chat`, payload);
      renderChatSuccess(chatOutput, chatMeta, data);
      await refreshSnapshot();
    } catch (error) {
      renderChatError(chatOutput, chatMeta, error);
    }
  });

  document.getElementById("fetch-form").addEventListener("submit", async (event) => {
    event.preventDefault();
    fetchMeta.innerHTML = "";
    fetchOutput.textContent = "Fetching and parsing article...";

    try {
      const payload = {
        url: document.getElementById("fetch-url").value,
      };
      const data = await requestJson(`${apiBaseUrl}/fetch`, payload);
      renderFetchSuccess(fetchOutput, fetchMeta, data);
    } catch (error) {
      renderFetchError(fetchOutput, fetchMeta, error);
    }
  });

  document.getElementById("grounding-form").addEventListener("submit", async (event) => {
    event.preventDefault();
    groundingMeta.innerHTML = "";
    groundingErrors.innerHTML = "";
    groundingSummary.innerHTML = "";
    groundingOutput.innerHTML = "";
    groundingAnswer.textContent = "Generating grounded answer...";

    try {
      const payload = {
        query: document.getElementById("grounding-query").value,
        search_limit: Number(document.getElementById("search-limit").value),
        fetch_limit: Number(document.getElementById("fetch-limit").value),
        selected_model: state.selectedModel || null,
      };
      const data = await requestJson(`${apiBaseUrl}/grounding/answer`, payload);
      renderGrounding(groundingSummary, groundingMeta, groundingAnswer, groundingErrors, groundingOutput, data);
      await refreshSnapshot();
    } catch (error) {
      renderGroundingError(groundingAnswer, groundingMeta, groundingErrors, groundingSummary, groundingOutput, error);
    }
  });

  try {
    await refreshSnapshot();
  } catch (error) {
    statusOutput.innerHTML = buildBanner("Initial snapshot failed", error.message, "error");
    runtimeChip.textContent = "Runtime: unavailable";
  }
}

main().catch((error) => {
  document.getElementById("environment-chip").textContent = error.message;
});
