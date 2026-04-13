from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from app.grounding import build_grounded_model_request, build_grounding_bundle
from app.config import Settings, get_settings
from app.providers import (
    FetcherClient,
    ModelRuntimeStatus,
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
        probe_timeout_seconds=settings.model_probe_timeout_seconds,
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
        model_provider = build_model_provider(current_settings)
        runtime_status = await model_provider.probe_runtime()
        return {
            "status": "ok" if runtime_status.ready else "degraded",
            "app": current_settings.app_name,
            "providers": {
                "model": current_settings.model_provider,
                "model_name": current_settings.model_name,
                "model_runtime_profile": current_settings.model_runtime_profile,
                "search": current_settings.search_provider,
                "fetch": "internal-fetcher",
            },
            "model_runtime": runtime_status.model_dump(),
        }

    @app.get(f"{settings.api_prefix}/system/providers")
    async def providers(current_settings: Annotated[Settings, Depends(get_settings)]) -> dict[str, object]:
        return {
            "model": {
                "provider": current_settings.model_provider,
                "base_url": current_settings.model_base_url,
                "model_name": current_settings.model_name,
                "runtime_profile": current_settings.model_runtime_profile,
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
        runtime = await provider.probe_runtime()
        models = await provider.list_models(runtime_status=runtime)
        return {
            "models": [item.model_dump() for item in models],
            "runtime": runtime.model_dump(),
        }

    @app.get(f"{settings.api_prefix}/model/runtime", response_model=ModelRuntimeStatus)
    async def model_runtime(current_settings: Annotated[Settings, Depends(get_settings)]) -> ModelRuntimeStatus:
        provider = build_model_provider(current_settings)
        return await provider.probe_runtime()

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
            grounding, _ = await build_grounding_bundle(
                query=payload.query,
                search_provider=search_provider,
                fetcher_client=fetch_client,
                search_limit=payload.search_limit,
                fetch_limit=payload.fetch_limit,
                source_char_limit=current_settings.grounding_source_char_limit,
                total_context_chars=current_settings.grounding_total_context_chars,
                preview_chars=current_settings.grounding_preview_chars,
            )
        except ProviderError as exc:
            raise HTTPException(status_code=502, detail=str(exc)) from exc

        return grounding.model_dump()

    @app.post(f"{settings.api_prefix}/grounding/answer")
    async def grounded_answer(
        payload: GroundingRequest,
        current_settings: Annotated[Settings, Depends(get_settings)],
    ) -> dict[str, object]:
        search_provider = build_search_provider(current_settings)
        fetch_client = build_fetcher_client(current_settings)
        model_provider = build_model_provider(current_settings)

        try:
            grounding, grounding_context = await build_grounding_bundle(
                query=payload.query,
                search_provider=search_provider,
                fetcher_client=fetch_client,
                search_limit=payload.search_limit,
                fetch_limit=payload.fetch_limit,
                source_char_limit=current_settings.grounding_source_char_limit,
                total_context_chars=current_settings.grounding_total_context_chars,
                preview_chars=current_settings.grounding_preview_chars,
            )
        except ProviderError as exc:
            raise HTTPException(status_code=502, detail=str(exc)) from exc

        if not grounding.fetched_sources or not grounding_context.strip():
            return {
                "answer_status": "insufficient_sources",
                "answer": None,
                "model": None,
                "usage": {},
                "model_error": None,
                "grounding": grounding.model_dump(),
            }

        grounded_request = build_grounded_model_request(
            query=payload.query,
            grounding_context=grounding_context,
            temperature=current_settings.grounding_model_temperature,
        )

        try:
            answer = await model_provider.chat(
                prompt=grounded_request.prompt,
                system_prompt=grounded_request.system_prompt,
                temperature=grounded_request.temperature,
            )
            return {
                "answer_status": "grounded",
                "answer": answer["answer"],
                "model": answer["model"],
                "usage": answer["usage"],
                "model_error": None,
                "grounding": grounding.model_dump(),
            }
        except ProviderError as exc:
            return {
                "answer_status": "model_error",
                "answer": None,
                "model": current_settings.model_name,
                "usage": {},
                "model_error": str(exc),
                "grounding": grounding.model_dump(),
            }

    return app


app = create_app()
