import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi import Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.health import router as health_router
from app.api.projects import router as projects_router
from app.api.benchmarks import router as benchmarks_router
from app.database import engine, Base

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    try:
        from app.services.rag_service import get_rag_service

        rag = get_rag_service()
        count = rag.seed()
        if count > 0:
            logger.info(f"[RAG] ✓ Knowledge base ready: {count} patterns")
        else:
            logger.warning("[RAG] ✗ No patterns loaded — check /app/knowledge_base/patterns/")
    except Exception as e:
        logger.error(f"[RAG] ✗ Failed to initialize: {type(e).__name__}: {e}")
    yield


app = FastAPI(
    title="OptPLC API",
    version="0.1.0",
    lifespan=lifespan,
)


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    import logging
    logging.getLogger(__name__).exception(
        f"Unhandled error on {request.method} {request.url}: {exc}"
    )
    return JSONResponse(
        status_code=500,
        content={
            "detail": str(exc),
            "type": type(exc).__name__,
        },
        headers={
            "Access-Control-Allow-Origin": "http://localhost:3000",
            "Access-Control-Allow-Credentials": "true",
        },
    )

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ✅ الصحيح: كل router يُسجَّل بـ prefix="/api" فقط
# لأن كل router عنده prefix خاص: /projects و /benchmarks
app.include_router(health_router, prefix="/api")
app.include_router(projects_router, prefix="/api")
app.include_router(benchmarks_router, prefix="/api")