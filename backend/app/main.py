from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.health import router as health_router
from app.api.projects import router as projects_router
from app.database.database import engine
from app.database.models import Base


@asynccontextmanager
async def lifespan(_app: FastAPI):
    # Development-only bootstrap: create tables when Alembic migrations are not applied yet.
    # Production environments should run `alembic upgrade head`.
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield

app = FastAPI(
    title="PLC Agent Optimizer API",
    version="0.1.0",
    description="Backend foundation for the PLC Agent Optimizer frontend MVP.",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health_router, prefix="/api")
app.include_router(projects_router, prefix="/api")


@app.exception_handler(RequestValidationError)
async def request_validation_exception_handler(_request, exc: RequestValidationError) -> JSONResponse:
    return JSONResponse(
        status_code=400,
        content={
            "detail": jsonable_encoder(exc.errors()),
        },
    )
