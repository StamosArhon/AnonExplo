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

function renderStatus(target, payload) {
  const runtime = payload.model_runtime || {};
  const overallClass = payload.status === "ok" ? "ok" : "error";
  const availableModels = Array.isArray(runtime.available_models) ? runtime.available_models.length : 0;

  target.innerHTML = `
    <div class="status-card">
      <strong>Status:</strong> <span class="${overallClass}">${escapeHtml(payload.status)}</span>
    </div>
    <div class="status-card">
      <strong>Model provider:</strong> ${escapeHtml(payload.providers.model)}
    </div>
    <div class="status-card">
      <strong>Model name:</strong> ${escapeHtml(payload.providers.model_name || "unknown")}
    </div>
    <div class="status-card">
      <strong>Runtime profile:</strong> ${escapeHtml(payload.providers.model_runtime_profile || "unknown")}
    </div>
    <div class="status-card">
      <strong>Runtime status:</strong> ${escapeHtml(runtime.status || "unknown")}
    </div>
    <div class="status-card">
      <strong>Advertised models:</strong> ${escapeHtml(availableModels)}
    </div>
    <div class="status-card">
      <strong>Search provider:</strong> ${escapeHtml(payload.providers.search)}
    </div>
    <div class="status-card">
      <strong>Fetch pipeline:</strong> ${escapeHtml(payload.providers.fetch)}
    </div>
    ${
      runtime.error
        ? `<div class="status-card error"><strong>Model runtime note:</strong> ${escapeHtml(runtime.error)}</div>`
        : ""
    }
  `;
}

function renderGrounding(summaryTarget, answerTarget, sourcesTarget, payload) {
  const grounding = payload.grounding || payload;
  const fetchedById = new Map((grounding.fetched_sources || []).map((item) => [item.source_id, item]));
  const errorsById = new Map((grounding.errors || []).map((item) => [item.source_id || item.url || item.stage, item]));

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
    answerTarget.textContent = "No grounded answer was generated because no fetched source text was available.";
  } else if (payload.answer_status === "model_error") {
    answerTarget.textContent = `The sources were fetched, but the model request failed.\n\n${payload.model_error || "Unknown model error."}`;
  } else {
    answerTarget.textContent = "Grounding preview generated without model synthesis.";
  }

  if (!(grounding.selected_sources || []).length) {
    sourcesTarget.innerHTML = '<div class="result-card">No sources were selected from the search results.</div>';
    return;
  }

  sourcesTarget.innerHTML = grounding.selected_sources
    .map((source) => {
      const fetched = fetchedById.get(source.source_id);
      const error = errorsById.get(source.source_id);
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
    throw new Error(data.detail || "Request failed.");
  }
  return data;
}

async function main() {
  const config = await getConfig();
  const apiBaseUrl = config.apiBaseUrl;
  document.getElementById("environment-chip").textContent = `Environment: ${config.environment}`;

  const statusOutput = document.getElementById("status-output");
  const chatOutput = document.getElementById("chat-output");
  const fetchOutput = document.getElementById("fetch-output");
  const groundingAnswer = document.getElementById("grounding-answer");
  const groundingSummary = document.getElementById("grounding-summary");
  const groundingOutput = document.getElementById("grounding-output");

  async function refreshStatus() {
    statusOutput.textContent = "Checking local services...";
    try {
      const status = await fetch(`${apiBaseUrl}/health`).then((response) => response.json());
      renderStatus(statusOutput, status);
    } catch (error) {
      statusOutput.innerHTML = `<div class="status-card error">${escapeHtml(error.message)}</div>`;
    }
  }

  document.getElementById("refresh-status").addEventListener("click", refreshStatus);

  document.getElementById("chat-form").addEventListener("submit", async (event) => {
    event.preventDefault();
    chatOutput.textContent = "Waiting for the model...";
    try {
      const payload = {
        prompt: document.getElementById("prompt-input").value,
        system_prompt: document.getElementById("system-input").value || null,
      };
      const data = await requestJson(`${apiBaseUrl}/model/chat`, payload);
      chatOutput.textContent = data.answer || "(empty response)";
    } catch (error) {
      chatOutput.textContent = error.message;
    }
  });

  document.getElementById("grounding-form").addEventListener("submit", async (event) => {
    event.preventDefault();
    groundingAnswer.textContent = "Generating grounded answer...";
    groundingSummary.innerHTML = "";
    groundingOutput.textContent = "";
    try {
      const payload = {
        query: document.getElementById("grounding-query").value,
        search_limit: Number(document.getElementById("search-limit").value),
        fetch_limit: Number(document.getElementById("fetch-limit").value),
      };
      const data = await requestJson(`${apiBaseUrl}/grounding/answer`, payload);
      renderGrounding(groundingSummary, groundingAnswer, groundingOutput, data);
    } catch (error) {
      groundingAnswer.textContent = error.message;
    }
  });

  document.getElementById("fetch-form").addEventListener("submit", async (event) => {
    event.preventDefault();
    fetchOutput.textContent = "Fetching and parsing article...";
    try {
      const payload = {
        url: document.getElementById("fetch-url").value,
      };
      const data = await requestJson(`${apiBaseUrl}/fetch`, payload);
      fetchOutput.textContent = `${data.title || "Untitled"}\n\n${data.content_text}`;
    } catch (error) {
      fetchOutput.textContent = error.message;
    }
  });

  await refreshStatus();
}

main().catch((error) => {
  document.getElementById("environment-chip").textContent = error.message;
});
