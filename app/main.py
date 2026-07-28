from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1 import auth, builds, repos, tests, security, performance
from app.core.config import settings

app = FastAPI(
    title=settings.APP_NAME,
    version="0.1.0",
    docs_url="/api/docs",
    openapi_url="/api/openapi.json",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router, prefix=settings.API_V1_PREFIX)
app.include_router(repos.router, prefix=settings.API_V1_PREFIX)
app.include_router(builds.router, prefix=settings.API_V1_PREFIX)
app.include_router(tests.router, prefix=settings.API_V1_PREFIX)
app.include_router(security.router, prefix=settings.API_V1_PREFIX)
app.include_router(performance.router, prefix=settings.API_V1_PREFIX)

# Phase 2 routers coming:
#   /api/reports       -> app.api.v1.reports (AI-generated readiness report PDF/HTML)
#   /api/notifications   -> app.api.v1.notifications (Slack, Teams, email alerts)


@app.get("/api/health", tags=["health"])
async def health() -> dict:
    return {"status": "ok", "service": settings.APP_NAME}
