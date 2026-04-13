from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from app.config import Settings, get_settings
from app.providers import (
    FetcherClient,
    OpenAICompatibleModelProvider,
    ProviderError,
    SearxngSearchProvider,
)


class ChatRequest(BaseModel):
    prompt: str = Field(min_length=1)
    system_prompt: str | None = None
    temperature: float = Field(default=0.2, ge=0.0, le=2.0)


class SearchRequest(BaseModel):
    query: str = Field(min_length=1)
    limit: int = Field(default=5, ge=1, le=10)


class FetchRequest(BaseModel):
    url: str = Field(min_length=1)


class GroundingRequest(BaseModel):
    query: str = Field(min_length=1)
    search_limit: int = Field(default=5, ge=1, le=10)
    fetch_limit: int = Field(default=3, ge=1, le=5)


def build_model_provider(settings: Settings) -> OpenAICompatibleModelProvider:
    return OpenAICompatibleModelProvider(
        base_url=settings.model_base_url,
        model_name=settings.model_name,
        timeout_seconds=settings.model_request_timeout_seconds,
    )


def build_search_provider(settings: Settings) -> SearxngSearchProvider:
    return SearxngSearchProvider(
        base_url=settings.search_base_url,
        timeout_seconds=settings.search_request_timeout_seconds,
    )


def build_fetcher_client(settings: Settings) -> FetcherClient:
    return FetcherClient(
        base_url=settings.fetch_base_url,
        timeout_seconds=settings.fetch_request_timeout_seconds,
    )


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title=settings.app_name,
        version="0.1.0",
        docs_url=f"{settings.api_prefix}/docs",
        openapi_url=f"{settings.api_prefix}/openapi.json",
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=False,
        allow_methods=["GET", "POST"],
        allow_headers=["*"],
    )

    @app.get(f"{settings.api_prefix}/health")
    async def health(current_settings: Annotated[Settings, Depends(get_settings)]) -> dict[str, object]:
        return {
            "status": "ok",
            "app": current_settings.app_name,
            "providers": {
                "model": current_settings.model_provider,
                "search": current_settings.search_provider,
                "fetch": "internal-fetcher",
            },
        }

    @app.get(f"{settings.api_prefix}/system/providers")
    async def providers(current_settings: Annotated[Settings, Depends(get_settings)]) -> dict[str, object]:
        return {
            "model": {
                "provider": current_settings.model_provider,
                "base_url": current_settings.model_base_url,
                "model_name": current_settings.model_name,
            },
            "search": {
                "provider": current_settings.search_provider,
                "base_url": current_settings.search_base_url,
                "default_limit": current_settings.search_result_limit,
            },
            "fetch": {
                "base_url": current_settings.fetch_base_url,
            },
        }

    @app.get(f"{settings.api_prefix}/model/models")
    async def list_models(current_settings: Annotated[Settings, Depends(get_settings)]) -> dict[str, object]:
        provider = build_model_provider(current_settings)
        models = await provider.list_models()
        return {"models": [item.model_dump() for item in models]}

    @app.post(f"{settings.api_prefix}/model/chat")
    async def chat(
        payload: ChatRequest,
        current_settings: Annotated[Settings, Depends(get_settings)],
    ) -> dict[str, object]:
        provider = build_model_provider(current_settings)
        try:
            return await provider.chat(
                prompt=payload.prompt,
                system_prompt=payload.system_prompt,
                temperature=payload.temperature,
            )
        except ProviderError as exc:
            raise HTTPException(status_code=502, detail=str(exc)) from exc

    @app.post(f"{settings.api_prefix}/search")
    async def search(
        payload: SearchRequest,
        current_settings: Annotated[Settings, Depends(get_settings)],
    ) -> dict[str, object]:
        provider = build_search_provider(current_settings)
        try:
            results = await provider.search(payload.query, payload.limit)
        except ProviderError as exc:
            raise HTTPException(status_code=502, detail=str(exc)) from exc
        return {"results": [item.model_dump() for item in results]}

    @app.post(f"{settings.api_prefix}/fetch")
    async def fetch(
        payload: FetchRequest,
        current_settings: Annotated[Settings, Depends(get_settings)],
    ) -> dict[str, object]:
        client = build_fetcher_client(current_settings)
        try:
            document = await client.fetch(payload.url)
        except ProviderError as exc:
            raise HTTPException(status_code=502, detail=str(exc)) from exc
        return document.model_dump()

    @app.post(f"{settings.api_prefix}/grounding/search-fetch")
    async def search_fetch(
        payload: GroundingRequest,
        current_settings: Annotated[Settings, Depends(get_settings)],
    ) -> dict[str, object]:
        search_provider = build_search_provider(current_settings)
        fetch_client = build_fetcher_client(current_settings)

        try:
            hits = await search_provider.search(payload.query, payload.search_limit)
        except ProviderError as exc:
            raise HTTPException(status_code=502, detail=str(exc)) from exc

        documents: list[dict[str, object]] = []
        for hit in hits[: payload.fetch_limit]:
            try:
                document = await fetch_client.fetch(hit.url)
                documents.append({"search_hit": hit.model_dump(), "document": document.model_dump()})
            except ProviderError as exc:
                documents.append({"search_hit": hit.model_dump(), "fetch_error": str(exc)})

        return {
            "query": payload.query,
            "search_results": [item.model_dump() for item in hits],
            "documents": documents,
        }

    return app


app = create_app()
