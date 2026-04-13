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
  target.innerHTML = `
    <div class="status-card">
      <strong>Status:</strong> <span class="ok">${escapeHtml(payload.status)}</span>
    </div>
    <div class="status-card">
      <strong>Model provider:</strong> ${escapeHtml(payload.providers.model)}
    </div>
    <div class="status-card">
      <strong>Search provider:</strong> ${escapeHtml(payload.providers.search)}
    </div>
    <div class="status-card">
      <strong>Fetch pipeline:</strong> ${escapeHtml(payload.providers.fetch)}
    </div>
  `;
}

function renderGrounding(target, payload) {
  if (!payload.documents.length) {
    target.innerHTML = '<div class="result-card">No documents were fetched.</div>';
    return;
  }

  target.innerHTML = payload.documents
    .map((entry) => {
      const hit = entry.search_hit;
      if (entry.fetch_error) {
        return `
          <div class="result-card">
            <strong>${escapeHtml(hit.title)}</strong>
            <div class="meta">${escapeHtml(hit.url)}</div>
            <p class="error">${escapeHtml(entry.fetch_error)}</p>
          </div>
        `;
      }

      const document = entry.document;
      return `
        <div class="result-card">
          <strong>${escapeHtml(document.title || hit.title)}</strong>
          <div class="meta"><a href="${escapeHtml(hit.url)}" target="_blank" rel="noreferrer">${escapeHtml(hit.url)}</a></div>
          <p>${escapeHtml(document.excerpt)}</p>
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
    groundingOutput.textContent = "Searching and fetching...";
    try {
      const payload = {
        query: document.getElementById("grounding-query").value,
        search_limit: Number(document.getElementById("search-limit").value),
        fetch_limit: Number(document.getElementById("fetch-limit").value),
      };
      const data = await requestJson(`${apiBaseUrl}/grounding/search-fetch`, payload);
      renderGrounding(groundingOutput, data);
    } catch (error) {
      groundingOutput.textContent = error.message;
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
