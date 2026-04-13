import json
from typing import Any

import httpx
from pydantic import BaseModel


class ProviderError(RuntimeError):
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
    content_type: str | None = None


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


class OpenAICompatibleModelProvider:
    def __init__(self, base_url: str, model_name: str, timeout_seconds: float) -> None:
        self.base_url = base_url.rstrip("/")
        self.model_name = model_name
        self.timeout_seconds = timeout_seconds

    async def list_models(self) -> list[ModelDescriptor]:
        try:
            async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
                response = await client.get(f"{self.base_url}/models")
                response.raise_for_status()
            payload = response.json()
        except (httpx.HTTPError, ValueError):
            return [ModelDescriptor(id=self.model_name, owned_by="configured-default")]

        models = payload.get("data", [])
        parsed = [ModelDescriptor(id=item["id"], owned_by=item.get("owned_by")) for item in models if "id" in item]
        return parsed or [ModelDescriptor(id=self.model_name, owned_by="configured-default")]

    async def chat(self, prompt: str, system_prompt: str | None, temperature: float) -> dict[str, Any]:
        messages: list[dict[str, Any]] = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        payload = {
            "model": self.model_name,
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
            "model": data.get("model", self.model_name),
            "answer": answer,
            "usage": data.get("usage", {}),
        }


class SearxngSearchProvider:
    def __init__(self, base_url: str, timeout_seconds: float) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds

    async def search(self, query: str, limit: int) -> list[SearchHit]:
        params = {
            "q": query,
            "format": "json",
            "categories": "general",
            "language": "auto",
        }
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
                snippet=item.get("content") or "",
                engine=item.get("engine"),
            )
            for item in items[:limit]
            if item.get("url")
        ]


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
