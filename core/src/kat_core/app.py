"""Authenticated loopback HTTP boundary for KAT's desktop and development UI."""

import hmac
import logging
import time
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Annotated, Any
from uuid import uuid4

from fastapi import Depends, FastAPI, Header, HTTPException, Query, Request
from fastapi.exception_handlers import request_validation_exception_handler
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.middleware.trustedhost import TrustedHostMiddleware

from kat_core import __version__
from kat_core.capability_api import capability_router
from kat_core.capability_schemas import CapabilityFailure
from kat_core.capability_store import CapabilityStore
from kat_core.capability_tools import BoundedCapabilities
from kat_core.config import CoreConfig
from kat_core.errors import ProviderFailure
from kat_core.memory_api import memory_router
from kat_core.memory_store import MemoryError
from kat_core.provider import ModelRuntime
from kat_core.providers import ProviderRegistry, SelectedRuntime
from kat_core.schemas import (
    Approval,
    ApprovalDecision,
    AuditEntry,
    ChatResponse,
    Message,
    MessageCreate,
    ProviderDescriptor,
    ProviderStatus,
    Session,
    SessionCreate,
    Settings,
    SettingsUpdate,
)
from kat_core.service import ApprovalConflictError, ChatService, SessionBusyError
from kat_core.storage import Store
from kat_core.tools import ToolRegistry, build_tool_registry

logger = logging.getLogger("kat_core.api")
ALLOWED_ORIGINS = (
    "http://localhost:1420",
    "http://127.0.0.1:1420",
    "tauri://localhost",
    "http://tauri.localhost",
    "https://tauri.localhost",
)


def create_app(
    config: CoreConfig, *, runtime: ModelRuntime | None = None, registry: ToolRegistry | None = None
) -> FastAPI:
    store = Store(config.data_dir / "kat.sqlite3", config.default_model)
    providers = ProviderRegistry(config.openai_api_key)
    model = runtime or SelectedRuntime(providers, store.settings)
    tools = registry or build_tool_registry()
    capabilities = BoundedCapabilities(CapabilityStore(store))
    capabilities.register(tools)
    service = ChatService(store, model, tools)

    @asynccontextmanager
    async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
        logger.info("core_started version=%s provider_ready=%s", __version__, model.ready)
        yield
        store.close()
        logger.info("core_stopped")

    async def require_auth(authorization: Annotated[str | None, Header()] = None) -> None:
        prefix = "Bearer "
        if (
            not authorization
            or not authorization.startswith(prefix)
            or not hmac.compare_digest(
                authorization[len(prefix) :].encode("utf-8"), config.api_token.encode("utf-8")
            )
        ):
            raise HTTPException(
                status_code=401,
                detail="A valid KAT bearer token is required",
                headers={"WWW-Authenticate": "Bearer"},
            )

    app = FastAPI(
        title="KAT Core",
        version=__version__,
        lifespan=lifespan,
        dependencies=[Depends(require_auth)],
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
    )
    app.state.store, app.state.service = store, service
    app.include_router(memory_router(store, service))
    app.include_router(capability_router(capabilities.store, capabilities.weather))

    @app.exception_handler(CapabilityFailure)
    async def capability_failure(_request: Request, error: CapabilityFailure) -> JSONResponse:
        return JSONResponse(
            status_code=400, content={"error": {"code": error.code, "message": str(error)}}
        )

    @app.middleware("http")
    async def observe_request(request: Request, call_next: Any) -> Any:
        origin = request.headers.get("origin")
        if origin and origin not in ALLOWED_ORIGINS:
            return JSONResponse(status_code=403, content={"detail": "Origin is not allowed"})
        request_id = str(uuid4())
        start = time.monotonic()
        response = await call_next(request)
        route = request.scope.get("route")
        logger.info(
            "request_complete request_id=%s method=%s route=%s status=%s duration_ms=%d",
            request_id,
            request.method,
            getattr(route, "path", "unmatched"),
            response.status_code,
            (time.monotonic() - start) * 1000,
        )
        response.headers["X-Request-ID"] = request_id
        return response

    app.add_middleware(
        CORSMiddleware,
        allow_origins=list(ALLOWED_ORIGINS),
        allow_credentials=False,
        allow_methods=["GET", "POST", "PUT"],
        allow_headers=["Authorization", "Content-Type"],
        expose_headers=["X-Request-ID"],
    )
    app.add_middleware(
        TrustedHostMiddleware, allowed_hosts=["127.0.0.1", "localhost"], www_redirect=False
    )

    @app.exception_handler(Exception)
    async def unexpected_error(_request: Request, error: Exception) -> JSONResponse:
        logger.error("unexpected_request_error exception_type=%s", type(error).__name__)
        return JSONResponse(status_code=500, content={"detail": "An internal Core error occurred"})

    @app.exception_handler(MemoryError)
    async def memory_error(_request: Request, error: MemoryError) -> JSONResponse:
        return JSONResponse(status_code=error.status, content={"detail": str(error)})

    @app.exception_handler(RequestValidationError)
    async def invalid_request(request: Request, error: RequestValidationError) -> Any:
        if request.url.path.startswith(("/memories", "/memory/", "/projects")):
            # Default validation errors echo rejected input, including secrets.
            return JSONResponse(
                status_code=422,
                content={
                    "detail": (
                        "Memory fields are invalid. Use normal information, never credentials; "
                        "review wording, scope, confirmation and timezone-aware dates."
                    )
                },
            )
        return await request_validation_exception_handler(request, error)

    def require_session(session_id: str) -> Session:
        session = store.session(session_id)
        if not session:
            raise HTTPException(status_code=404, detail="Conversation not found")
        return session

    def public_settings() -> Settings:
        return Settings(
            **store.settings().model_dump(),
            api_key_configured=runtime.ready if runtime else providers.openai.ready,
            application_allowlist=tools.public_applications(),
        )

    @app.get("/health")
    def health() -> dict[str, Any]:
        return {"status": "ok", "version": __version__, "provider_ready": model.ready}

    @app.get("/openapi.json", include_in_schema=False)
    def openapi_schema() -> dict[str, Any]:
        return app.openapi()

    @app.get("/sessions", response_model=list[Session])
    def sessions() -> list[Session]:
        return store.sessions()

    @app.post("/sessions", response_model=Session, status_code=201)
    def create_session(body: SessionCreate) -> Session:
        title = body.title.strip()
        if not title:
            raise HTTPException(status_code=422, detail="Conversation title cannot be blank")
        return store.create_session(title)

    @app.get("/sessions/{session_id}/messages", response_model=list[Message])
    def messages(session_id: str) -> list[Message]:
        require_session(session_id)
        return store.messages(session_id)

    @app.post("/sessions/{session_id}/messages", response_model=ChatResponse)
    async def chat(session_id: str, body: MessageCreate) -> ChatResponse | JSONResponse:
        require_session(session_id)
        if not body.content.strip():
            raise HTTPException(status_code=422, detail="Message cannot be blank")
        try:
            return await service.chat(session_id, body.content)
        except SessionBusyError as error:
            raise HTTPException(status_code=409, detail=str(error)) from None
        except ProviderFailure as error:
            return JSONResponse(
                status_code=error.status_code,
                content={
                    "error": {"code": error.code.value, "message": str(error)},
                    "detail": str(error),
                },
            )

    @app.get("/approvals", response_model=list[Approval])
    def approvals(session_id: str | None = None) -> list[Approval]:
        if session_id is not None:
            require_session(session_id)
        return store.approvals(session_id)

    @app.post("/approvals/{approval_id}/decision", response_model=Approval)
    async def decide(approval_id: str, body: ApprovalDecision) -> Approval:
        approval = store.approval(approval_id)
        if not approval:
            raise HTTPException(status_code=404, detail="Approval not found")
        try:
            return await service.decide(approval, body.approved)
        except (SessionBusyError, ApprovalConflictError) as error:
            raise HTTPException(status_code=409, detail=str(error)) from None

    @app.get("/settings", response_model=Settings)
    def settings() -> Settings:
        return public_settings()

    @app.get("/providers", response_model=list[ProviderDescriptor])
    def provider_descriptors() -> list[ProviderDescriptor]:
        return providers.descriptors()

    @app.post("/providers/probe", response_model=ProviderStatus)
    async def provider_probe(body: SettingsUpdate) -> ProviderStatus:
        return await providers.probe(body)

    @app.put("/settings", response_model=Settings)
    def update_settings(body: SettingsUpdate) -> Settings:
        store.save_settings(body)
        store.add_audit("settings_updated", details=body.model_dump())
        return public_settings()

    @app.get("/audit", response_model=list[AuditEntry])
    def audit(limit: Annotated[int, Query(ge=1, le=1000)] = 100) -> list[AuditEntry]:
        return store.audit(limit)

    return app
