import json
from typing import Any, Protocol

import httpx
from pydantic import BaseModel, Field


class ProviderError(RuntimeError):
    pass


class UnsupportedModelError(ProviderError):
    pass


class ModelDescriptor(BaseModel):
    id: str
    owned_by: str | None = None


class SearchHit(BaseModel):
    title: str
    url: str
    snippet: str = ""
    engine: str | None = None


class FetchDocument(BaseModel):
    requested_url: str
    final_url: str
    title: str | None = None
    excerpt: str
    content_text: str
    content_char_count: int = 0
    word_count: int = 0
    content_type: str | None = None


class GroundedModelRequest(BaseModel):
    prompt: str
    system_prompt: str
    temperature: float


class ModelRuntimeStatus(BaseModel):
    ready: bool
    reachable: bool
    status: str
    configured_model: str
    checked_url: str
    available_models: list[ModelDescriptor] = Field(default_factory=list)
    error: str | None = None


class ModelSelection(BaseModel):
    configured_model: str
    selected_model: str
    requested_model: str | None = None
    selection_source: str


class ModelProvider(Protocol):
    async def probe_runtime(self) -> ModelRuntimeStatus: ...
    def select_model(
        self,
        requested_model: str | None,
        runtime_status: ModelRuntimeStatus | None = None,
    ) -> ModelSelection: ...
    async def list_models(self, runtime_status: ModelRuntimeStatus | None = None) -> list[ModelDescriptor]: ...
    async def chat(
        self,
        prompt: str,
        system_prompt: str | None,
        temperature: float,
        model_name: str | None = None,
    ) -> dict[str, Any]: ...


class SearchProvider(Protocol):
    async def search(self, query: str, limit: int) -> list[SearchHit]: ...


def _normalize_message_content(content: Any) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            if isinstance(item, dict):
                text = item.get("text")
                if isinstance(text, str):
                    parts.append(text)
        return "\n".join(parts).strip()
    return json.dumps(content, ensure_ascii=True)


def _normalize_requested_model(requested_model: str | None) -> str | None:
    if not isinstance(requested_model, str):
        return None
    normalized = requested_model.strip()
    return normalized or None


def _normalize_search_snippet(content: Any) -> str:
    if isinstance(content, str):
        return content
    if content is None:
        return ""
    return json.dumps(content, ensure_ascii=True)


def _build_runtime_status(
    *,
    configured_model: str,
    endpoint: str,
    available_models: list[ModelDescriptor],
) -> ModelRuntimeStatus:
    available_model_ids = {item.id for item in available_models}

    if not available_models:
        return ModelRuntimeStatus(
            ready=False,
            reachable=True,
            status="no_models_reported",
            configured_model=configured_model,
            checked_url=endpoint,
            available_models=[],
            error="Model runtime responded without any advertised models.",
        )

    if configured_model not in available_model_ids:
        return ModelRuntimeStatus(
            ready=False,
            reachable=True,
            status="configured_model_missing",
            configured_model=configured_model,
            checked_url=endpoint,
            available_models=available_models,
            error=f"Configured model '{configured_model}' is not advertised by the runtime.",
        )

    return ModelRuntimeStatus(
        ready=True,
        reachable=True,
        status="ready",
        configured_model=configured_model,
        checked_url=endpoint,
        available_models=available_models,
        error=None,
    )


def _select_model(
    *,
    configured_model: str,
    requested_model: str | None,
    runtime_status: ModelRuntimeStatus | None = None,
) -> ModelSelection:
    normalized_requested_model = _normalize_requested_model(requested_model)
    selected_model = normalized_requested_model or configured_model
    selection_source = "request_override" if normalized_requested_model else "configured_default"

    if runtime_status and runtime_status.available_models:
        available_model_ids = {item.id for item in runtime_status.available_models}
        if selected_model not in available_model_ids:
            raise UnsupportedModelError(
                f"Requested model '{selected_model}' is not advertised by the runtime."
            )

    return ModelSelection(
        configured_model=configured_model,
        selected_model=selected_model,
        requested_model=normalized_requested_model,
        selection_source=selection_source,
    )


def _build_usage(
    *,
    prompt_tokens: Any = None,
    completion_tokens: Any = None,
) -> dict[str, int]:
    usage: dict[str, int] = {}
    if isinstance(prompt_tokens, int):
        usage["prompt_tokens"] = prompt_tokens
    if isinstance(completion_tokens, int):
        usage["completion_tokens"] = completion_tokens
    if usage:
        usage["total_tokens"] = usage.get("prompt_tokens", 0) + usage.get("completion_tokens", 0)
    return usage


class OpenAICompatibleModelProvider:
    def __init__(
        self,
        base_url: str,
        model_name: str,
        timeout_seconds: float,
        probe_timeout_seconds: float,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.model_name = model_name
        self.timeout_seconds = timeout_seconds
        self.probe_timeout_seconds = probe_timeout_seconds

    async def probe_runtime(self) -> ModelRuntimeStatus:
        endpoint = f"{self.base_url}/models"
        try:
            async with httpx.AsyncClient(timeout=self.probe_timeout_seconds) as client:
                response = await client.get(endpoint)
                response.raise_for_status()
        except httpx.HTTPError as exc:
            return ModelRuntimeStatus(
                ready=False,
                reachable=False,
                status="unreachable",
                configured_model=self.model_name,
                checked_url=endpoint,
                error=f"Model runtime request failed: {exc}",
            )

        try:
            payload = response.json()
        except ValueError as exc:
            return ModelRuntimeStatus(
                ready=False,
                reachable=True,
                status="invalid_response",
                configured_model=self.model_name,
                checked_url=endpoint,
                error=f"Model runtime returned invalid JSON: {exc}",
            )

        models = payload.get("data", [])
        available_models = [
            ModelDescriptor(id=item["id"], owned_by=item.get("owned_by")) for item in models if "id" in item
        ]
        return _build_runtime_status(
            configured_model=self.model_name,
            endpoint=endpoint,
            available_models=available_models,
        )

    def select_model(
        self,
        requested_model: str | None,
        runtime_status: ModelRuntimeStatus | None = None,
    ) -> ModelSelection:
        return _select_model(
            configured_model=self.model_name,
            requested_model=requested_model,
            runtime_status=runtime_status,
        )

    async def list_models(self, runtime_status: ModelRuntimeStatus | None = None) -> list[ModelDescriptor]:
        runtime_status = runtime_status or await self.probe_runtime()
        return runtime_status.available_models or [ModelDescriptor(id=self.model_name, owned_by="configured-default")]

    async def chat(
        self,
        prompt: str,
        system_prompt: str | None,
        temperature: float,
        model_name: str | None = None,
    ) -> dict[str, Any]:
        messages: list[dict[str, Any]] = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        resolved_model_name = _normalize_requested_model(model_name) or self.model_name
        payload = {
            "model": resolved_model_name,
            "messages": messages,
            "temperature": temperature,
        }

        try:
            async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
                response = await client.post(f"{self.base_url}/chat/completions", json=payload)
                response.raise_for_status()
            data = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise ProviderError(f"Model request failed: {exc}") from exc

        choice = (data.get("choices") or [{}])[0]
        message = choice.get("message", {})
        answer = _normalize_message_content(message.get("content", ""))
        return {
            "model": data.get("model", resolved_model_name),
            "answer": answer,
            "usage": data.get("usage", {}),
            "selected_model": resolved_model_name,
        }


class OllamaModelProvider:
    def __init__(
        self,
        base_url: str,
        model_name: str,
        timeout_seconds: float,
        probe_timeout_seconds: float,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.model_name = model_name
        self.timeout_seconds = timeout_seconds
        self.probe_timeout_seconds = probe_timeout_seconds

    async def probe_runtime(self) -> ModelRuntimeStatus:
        endpoint = f"{self.base_url}/tags"
        try:
            async with httpx.AsyncClient(timeout=self.probe_timeout_seconds) as client:
                response = await client.get(endpoint)
                response.raise_for_status()
        except httpx.HTTPError as exc:
            return ModelRuntimeStatus(
                ready=False,
                reachable=False,
                status="unreachable",
                configured_model=self.model_name,
                checked_url=endpoint,
                error=f"Model runtime request failed: {exc}",
            )

        try:
            payload = response.json()
        except ValueError as exc:
            return ModelRuntimeStatus(
                ready=False,
                reachable=True,
                status="invalid_response",
                configured_model=self.model_name,
                checked_url=endpoint,
                error=f"Model runtime returned invalid JSON: {exc}",
            )

        models = payload.get("models", [])
        available_models = [
            ModelDescriptor(
                id=item.get("model") or item.get("name"),
                owned_by="ollama",
            )
            for item in models
            if item.get("model") or item.get("name")
        ]
        return _build_runtime_status(
            configured_model=self.model_name,
            endpoint=endpoint,
            available_models=available_models,
        )

    def select_model(
        self,
        requested_model: str | None,
        runtime_status: ModelRuntimeStatus | None = None,
    ) -> ModelSelection:
        return _select_model(
            configured_model=self.model_name,
            requested_model=requested_model,
            runtime_status=runtime_status,
        )

    async def list_models(self, runtime_status: ModelRuntimeStatus | None = None) -> list[ModelDescriptor]:
        runtime_status = runtime_status or await self.probe_runtime()
        return runtime_status.available_models or [ModelDescriptor(id=self.model_name, owned_by="ollama")]

    async def chat(
        self,
        prompt: str,
        system_prompt: str | None,
        temperature: float,
        model_name: str | None = None,
    ) -> dict[str, Any]:
        messages: list[dict[str, Any]] = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        resolved_model_name = _normalize_requested_model(model_name) or self.model_name
        payload = {
            "model": resolved_model_name,
            "messages": messages,
            "stream": False,
            "options": {
                "temperature": temperature,
            },
        }

        try:
            async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
                response = await client.post(f"{self.base_url}/chat", json=payload)
                response.raise_for_status()
            data = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise ProviderError(f"Model request failed: {exc}") from exc

        message = data.get("message", {})
        answer = _normalize_message_content(message.get("content", ""))
        return {
            "model": data.get("model", resolved_model_name),
            "answer": answer,
            "usage": _build_usage(
                prompt_tokens=data.get("prompt_eval_count"),
                completion_tokens=data.get("eval_count"),
            ),
            "selected_model": resolved_model_name,
        }


class SearxngSearchProvider:
    def __init__(
        self,
        base_url: str,
        timeout_seconds: float,
        *,
        categories: str = "general,news",
        language: str = "all",
        time_range: str = "",
        engines: str = "",
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds
        self.categories = categories.strip()
        self.language = language.strip()
        self.time_range = time_range.strip()
        self.engines = engines.strip()

    async def search(self, query: str, limit: int) -> list[SearchHit]:
        params = {
            "q": query,
            "format": "json",
            "pageno": 1,
        }
        if self.categories:
            params["categories"] = self.categories
        if self.language:
            params["language"] = self.language
        if self.time_range:
            params["time_range"] = self.time_range
        if self.engines:
            params["engines"] = self.engines
        try:
            async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
                response = await client.get(f"{self.base_url}/search", params=params)
                response.raise_for_status()
            data = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise ProviderError(f"Search request failed: {exc}") from exc

        items = data.get("results", [])
        return [
            SearchHit(
                title=item.get("title") or item.get("url") or "Untitled result",
                url=item["url"],
                snippet=_normalize_search_snippet(item.get("content")),
                engine=item.get("engine"),
            )
            for item in items[:limit]
            if item.get("url")
        ]


class YacySearchProvider:
    def __init__(self, base_url: str, timeout_seconds: float) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds

    async def search(self, query: str, limit: int) -> list[SearchHit]:
        params = {
            "query": query,
            "resource": "global",
            "verify": "false",
            "maximumRecords": limit,
        }
        try:
            async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
                response = await client.get(f"{self.base_url}/yacysearch.json", params=params)
                response.raise_for_status()
            data = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise ProviderError(f"Search request failed: {exc}") from exc

        items: list[dict[str, Any]] = []
        for channel in data.get("channels", []):
            if isinstance(channel, dict):
                channel_items = channel.get("items", [])
                if isinstance(channel_items, list):
                    items.extend(item for item in channel_items if isinstance(item, dict))

        results: list[SearchHit] = []
        for item in items:
            url = item.get("link") or item.get("url")
            if not url:
                continue

            results.append(
                SearchHit(
                    title=item.get("title") or url or "Untitled result",
                    url=url,
                    snippet=_normalize_search_snippet(
                        item.get("description") or item.get("snippet") or item.get("content")
                    ),
                    engine="yacy",
                )
            )
            if len(results) >= limit:
                break

        return results


class FetcherClient:
    def __init__(self, base_url: str, timeout_seconds: float) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds

    async def fetch(self, url: str) -> FetchDocument:
        payload = {"url": url}
        try:
            async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
                response = await client.post(f"{self.base_url}/api/v1/fetch", json=payload)
                response.raise_for_status()
            data = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise ProviderError(f"Fetch request failed: {exc}") from exc

        return FetchDocument.model_validate(data)
