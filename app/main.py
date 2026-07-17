from contextlib import asynccontextmanager
from fastapi import APIRouter, Depends, FastAPI
from app.db.base import Base
from app.db.session import engine
from app.core.config import get_settings
from app.core.exceptions import AppError, app_error_handler, EvaluationNotFound, ExperimentNotFound
from app.security.api_key import require_api_key
from app.services.evaluation_service import EvaluationNotFoundError, ExperimentNotFoundError
from app.core.logging import configure_logging
from app.api.routes.diagnostics import router
from app.api.routes.knowledge import router as knowledge_router
from app.api.routes.learning import router as learning_router
from app.api.routes.tutor import router as tutor_router
from app.api.routes.dashboard import router as dashboard_router
from app.api.routes.evaluation import router as evaluation_router
from app.middleware.request_context import RequestContextMiddleware

settings = get_settings()
configure_logging(settings.log_level)

@asynccontextmanager
async def lifespan(_: FastAPI):
    # Local convenience only. Production deployments run `alembic upgrade head`.
    if settings.environment in {"development", "test"}:
        Base.metadata.create_all(bind=engine)
    yield

app = FastAPI(
    title=settings.app_name,
    version="6.0.0",
    description="Production-style SAT Math Coach with diagnostics, learner modeling, personalized learning, Socratic tutoring, and role-aware dashboards, and a measurable continuous-improvement loop.",
    lifespan=lifespan,
)
app.add_middleware(RequestContextMiddleware)
app.add_exception_handler(AppError, app_error_handler)

@app.exception_handler(EvaluationNotFoundError)
async def evaluation_not_found_handler(request, exc):
    return await app_error_handler(request, EvaluationNotFound(str(exc)))

@app.exception_handler(ExperimentNotFoundError)
async def experiment_not_found_handler(request, exc):
    return await app_error_handler(request, ExperimentNotFound(str(exc)))
# All /api/v1 endpoints require an API key (when REQUIRE_API_KEY=true). New
# routers must be registered on this aggregator, not directly on `app`, to
# inherit protection automatically. tests/test_api_key_protection.py enforces
# this invariant against the live route table, independent of how routers are wired.
protected_api_router = APIRouter(dependencies=[Depends(require_api_key)])
protected_api_router.include_router(router)
protected_api_router.include_router(knowledge_router)
protected_api_router.include_router(learning_router)
protected_api_router.include_router(tutor_router)
protected_api_router.include_router(dashboard_router)
protected_api_router.include_router(evaluation_router)
app.include_router(protected_api_router)

@app.get("/health", tags=["system"])
def health() -> dict:
    return {"status": "ok", "service": "diagnostic-engine", "version": "6.0.0"}

@app.get("/ready", tags=["system"])
def ready() -> dict:
    with engine.connect() as connection:
        connection.exec_driver_sql("SELECT 1")
    return {"status": "ready"}
