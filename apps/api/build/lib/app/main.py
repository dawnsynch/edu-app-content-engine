from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.errors import register_exception_handlers
from app.api.health import router as health_router
from app.core.settings import get_settings
from app.modules.ai.router import router as ai_router
from app.modules.content.router import router as content_router
from app.modules.courses.router import router as courses_router
from app.modules.ingestion.router import router as ingestion_router
from app.modules.recommendations.router import router as recommendations_router
from app.modules.search.router import router as search_router
from app.modules.sources.router import router as sources_router

settings = get_settings()

app = FastAPI(
    title="Edu DawnSynch API",
    version="0.4.0",
    description=(
        "Approved-source aggregation API for the Edu DawnSynch learning discovery platform."
    ),
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health_router)
app.include_router(sources_router)
app.include_router(content_router)
app.include_router(courses_router)
app.include_router(ingestion_router)
app.include_router(ai_router)
app.include_router(search_router)
app.include_router(recommendations_router)
register_exception_handlers(app)


@app.get("/")
async def root() -> dict[str, str]:
    return {"service": "edu-dawnsynch-api", "status": "ok"}
