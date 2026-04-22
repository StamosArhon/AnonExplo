from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from app.config import Settings, get_settings
from app.grounding import build_grounded_model_request, build_grounding_bundle, normalize_grounded_answer
from app.providers import (
    FetcherClient,
    ModelProvider,
    ModelRuntimeStatus,
    ModelSelection,
    OpenAICompatibleModelProvider,
    OllamaModelProvider,
    ProviderError,
    SearchProvider,
    SearxngSearchProvider,
    UnsupportedModelError,
    YacySearchProvider,
)


class ChatRequest(BaseModel):
    prompt: str = Field(min_length=1)
    system_prompt: str | None = None
    temperature: float = Field(default=0.2, ge=0.0, le=2.0)
    selected_model: str | None = Field(default=None, min_length=1)


class SearchRequest(BaseModel):
    query: str = Field(min_length=1)
    limit: int = Field(default=8, ge=1, le=10)


class FetchRequest(BaseModel):
    url: str = Field(min_length=1)


class GroundingRequest(BaseModel):
    query: str = Field(min_length=1)
    search_limit: int = Field(default=6, ge=1, le=10)
    fetch_limit: int = Field(default=3, ge=1, le=5)
    system_prompt: str | None = None
    selected_model: str | None = Field(default=None, min_length=1)


def build_model_provider(settings: Settings) -> ModelProvider:
    if settings.model_provider == "openai_compatible":
        return OpenAICompatibleModelProvider(
            base_url=settings.model_base_url,
            model_name=settings.model_name,
            timeout_seconds=settings.model_request_timeout_seconds,
            probe_timeout_seconds=settings.model_probe_timeout_seconds,
        )

    if settings.model_provider == "ollama":
        return OllamaModelProvider(
            base_url=settings.model_base_url,
            model_name=settings.model_name,
            timeout_seconds=settings.model_request_timeout_seconds,
            probe_timeout_seconds=settings.model_probe_timeout_seconds,
        )

    raise ValueError(f"Unsupported model provider: {settings.model_provider}")


def build_search_provider(settings: Settings) -> SearchProvider:
    if settings.search_provider == "searxng":
        return SearxngSearchProvider(
            base_url=settings.search_base_url,
            timeout_seconds=settings.search_request_timeout_seconds,
            categories=settings.search_categories,
            language=settings.search_language,
            time_range=settings.search_time_range,
            engines=settings.search_engines,
        )

    if settings.search_provider == "yacy":
        return YacySearchProvider(
            base_url=settings.search_base_url,
            timeout_seconds=settings.search_request_timeout_seconds,
        )

    raise ValueError(f"Unsupported search provider: {settings.search_provider}")


def build_fetcher_client(settings: Settings) -> FetcherClient:
    return FetcherClient(
        base_url=settings.fetch_base_url,
        timeout_seconds=settings.fetcher_client_timeout_seconds,
    )


def build_model_error_detail(
    message: str,
    selection: ModelSelection,
    runtime: ModelRuntimeStatus,
) -> dict[str, object]:
    return {
        "message": message,
        "selection": selection.model_dump(),
        "runtime": runtime.model_dump(),
    }


def build_model_selection_preview(
    configured_model: str,
    requested_model: str | None,
) -> ModelSelection:
    normalized_requested_model = requested_model.strip() if isinstance(requested_model, str) else ""
    normalized_requested_model = normalized_requested_model or None
    return ModelSelection(
        configured_model=configured_model,
        selected_model=normalized_requested_model or configured_model,
        requested_model=normalized_requested_model,
        selection_source="request_override" if normalized_requested_model else "configured_default",
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
                "categories": current_settings.search_categories,
                "language": current_settings.search_language or "instance-default",
                "time_range": current_settings.search_time_range or "none",
                "engines": current_settings.search_engines or "instance-default",
                "preferred_domains": current_settings.search_preferred_domains or "none",
                "preferred_domain_boost": current_settings.search_preferred_domain_boost,
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
            "configured_model": current_settings.model_name,
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
        runtime = await provider.probe_runtime()
        try:
            selection = provider.select_model(requested_model=payload.selected_model, runtime_status=runtime)
        except UnsupportedModelError as exc:
            raise HTTPException(
                status_code=400,
                detail=build_model_error_detail(
                    str(exc),
                    build_model_selection_preview(current_settings.model_name, payload.selected_model),
                    runtime,
                ),
            ) from exc

        try:
            answer = await provider.chat(
                prompt=payload.prompt,
                system_prompt=payload.system_prompt,
                temperature=payload.temperature,
                model_name=selection.selected_model,
            )
        except ProviderError as exc:
            raise HTTPException(
                status_code=502,
                detail=build_model_error_detail(str(exc), selection, runtime),
            ) from exc

        return {
            "model": answer["model"],
            "answer": answer["answer"],
            "usage": answer["usage"],
            "selection": selection.model_dump(),
            "runtime_status": runtime.status,
            "runtime_ready": runtime.ready,
        }

    @app.post(f"{settings.api_prefix}/search")
    async def search(
        payload: SearchRequest,
        current_settings: Annotated[Settings, Depends(get_settings)],
    ) -> dict[str, object]:
        provider = build_search_provider(current_settings)
        try:
            results = await provider.search(payload.query, payload.limit)
        except ProviderError as exc:
            raise HTTPException(status_code=502, detail={"message": str(exc), "provider": "search"}) from exc
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
            raise HTTPException(status_code=502, detail={"message": str(exc), "provider": "fetch"}) from exc
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
                preferred_domains=current_settings.search_preferred_domains,
                preferred_domain_boost=current_settings.search_preferred_domain_boost,
            )
        except ProviderError as exc:
            raise HTTPException(status_code=502, detail={"message": str(exc), "provider": "grounding"}) from exc

        return grounding.model_dump()

    @app.post(f"{settings.api_prefix}/grounding/answer")
    async def grounded_answer(
        payload: GroundingRequest,
        current_settings: Annotated[Settings, Depends(get_settings)],
    ) -> dict[str, object]:
        search_provider = build_search_provider(current_settings)
        fetch_client = build_fetcher_client(current_settings)
        model_provider = build_model_provider(current_settings)
        runtime = await model_provider.probe_runtime()

        try:
            selection = model_provider.select_model(requested_model=payload.selected_model, runtime_status=runtime)
        except UnsupportedModelError as exc:
            raise HTTPException(
                status_code=400,
                detail=build_model_error_detail(
                    str(exc),
                    build_model_selection_preview(current_settings.model_name, payload.selected_model),
                    runtime,
                ),
            ) from exc

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
                preferred_domains=current_settings.search_preferred_domains,
                preferred_domain_boost=current_settings.search_preferred_domain_boost,
            )
        except ProviderError as exc:
            raise HTTPException(status_code=502, detail={"message": str(exc), "provider": "grounding"}) from exc

        if grounding.summary.context_mode == "none" or not grounding_context.strip():
            return {
                "answer_status": "insufficient_sources",
                "answer": None,
                "model": None,
                "usage": {},
                "model_error": None,
                "selection": selection.model_dump(),
                "runtime_status": runtime.status,
                "runtime_ready": runtime.ready,
                "grounding": grounding.model_dump(),
            }

        grounded_request = build_grounded_model_request(
            query=payload.query,
            grounding_context=grounding_context,
            temperature=current_settings.grounding_model_temperature,
            context_mode=grounding.summary.context_mode,
            additional_system_prompt=payload.system_prompt,
        )

        try:
            answer = await model_provider.chat(
                prompt=grounded_request.prompt,
                system_prompt=grounded_request.system_prompt,
                temperature=grounded_request.temperature,
                model_name=selection.selected_model,
            )
            normalized_answer = normalize_grounded_answer(answer["answer"])
            answer_status = "grounded"
            if grounding.summary.context_mode == "search_snippets":
                answer_status = "snippet_grounded"
            return {
                "answer_status": answer_status,
                "answer": normalized_answer,
                "model": answer["model"],
                "usage": answer["usage"],
                "model_error": None,
                "selection": selection.model_dump(),
                "runtime_status": runtime.status,
                "runtime_ready": runtime.ready,
                "grounding": grounding.model_dump(),
            }
        except ProviderError as exc:
            return {
                "answer_status": "model_error",
                "answer": None,
                "model": selection.selected_model,
                "usage": {},
                "model_error": str(exc),
                "selection": selection.model_dump(),
                "runtime_status": runtime.status,
                "runtime_ready": runtime.ready,
                "grounding": grounding.model_dump(),
            }

    return app


app = create_app()
