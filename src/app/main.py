from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from uuid import UUID

import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.ext.asyncio import AsyncEngine
from starlette.middleware.trustedhost import TrustedHostMiddleware

from app import __version__
from app.bootstrap.errors import install_exception_handlers
from app.bootstrap.router import create_api_router
from app.container import Container
from app.core.config import Settings, get_settings
from app.core.logging.logging import configure_logging
from app.core.observability.observability import RequestContextMiddleware, metrics_response
from app.modules.user.domain.authorization import AuthorizationContext, RoleName
from app.utilities.local_auth import LocalAuthorizationMiddleware


def create_app(
        settings: Settings | None = None,
        engine: AsyncEngine | None = None
    ) -> FastAPI:
    app_settings = settings or get_settings()
    configure_logging(app_settings)

    container = Container.build(app_settings, engine)
    logger = structlog.get_logger("application")

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncGenerator[None, None]:

        try:
            await container.start()

            logger.info(
                "application_started",
                service=app_settings.service_name,
                environment=app_settings.environment,
            )

            yield
        finally:
            await container.close()

            logger.info(
                "application_stopped",
                service=app_settings.service_name,
            )

    docs_url = "/docs" if app_settings.docs_enabled else None

    application = FastAPI(
        title=app_settings.service_name,
        version=__version__,
        docs_url=docs_url,
        redoc_url="/redoc",
        openapi_url=f"{app_settings.api_prefix}/openapi.json" if docs_url else None,
        lifespan=lifespan,
    )
    application.state.container = container

    application.add_middleware(
        TrustedHostMiddleware,
        allowed_hosts=app_settings.trusted_hosts,
    )

    if app_settings.local_auth_bypass_enabled:
        application.add_middleware(
            LocalAuthorizationMiddleware,
            authorization_context=AuthorizationContext(
                user_id=UUID("00000000-0000-0000-0000-000000000001"),
                roles=frozenset({RoleName.READ_ONLY_ANALYST, RoleName.OPERATIONS_MANAGER}),
                # site_codes=frozenset({"LOCAL"}),
                global_scope=True,
            ),
        )

    if app_settings.cors_origins:
        application.add_middleware(
            CORSMiddleware,
            allow_origins=app_settings.cors_origins,
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )
    application.add_middleware(RequestContextMiddleware)

    install_exception_handlers(application)
    application.add_api_route("/metrics", metrics_response, include_in_schema=False)
    application.include_router(create_api_router(), prefix=app_settings.api_prefix)
    return application


app = create_app()
