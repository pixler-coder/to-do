import logging
import time
from contextlib import asynccontextmanager
from typing import Optional, List as ListType

from fastapi import FastAPI, Depends, HTTPException, Path, Query, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from sqlalchemy import text
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

from .config import settings
from .database import engine, SessionLocal, get_db
from . import models, schemas, crud

# ── Logging Setup ──────────────────────────────────────────────────

logging.basicConfig(
    level=getattr(logging, settings.log_level.upper(), logging.INFO),
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("neotask")


# ── Rate Limiter ──────────────────────────────────────────────────

limiter = Limiter(key_func=get_remote_address)


# ── Application Lifespan ──────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Create database tables
    models.Base.metadata.create_all(bind=engine)
    logger.info("Database tables created / verified")

    # Seed initial lists if none exist
    db = SessionLocal()
    try:
        if db.query(models.List).count() == 0:
            for name in ["Inbox", "Work", "Personal", "Exams"]:
                db.add(models.List(name=name))
            db.commit()
            logger.info("Seeded default spaces: Inbox, Work, Personal, Exams")
    except Exception:
        db.rollback()
        logger.exception("Failed to seed default spaces")
    finally:
        db.close()

    logger.info("NeoTask started (debug=%s)", settings.debug)
    yield
    logger.info("NeoTask shutting down")


# ── FastAPI App ───────────────────────────────────────────────────

app = FastAPI(
    title="Neo-Minimalist Task Manager API",
    lifespan=lifespan,
    # Disable interactive docs AND raw OpenAPI schema in production
    docs_url="/docs" if settings.debug else None,
    redoc_url="/redoc" if settings.debug else None,
    openapi_url="/openapi.json" if settings.debug else None,
)

# Attach rate limiter to app
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# CORS: use configured origins
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=False,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["Content-Type"],
)


# ── Middleware ────────────────────────────────────────────────────

@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    """Inject security headers into every response."""
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
    response.headers["Server"] = "NeoTask"
    # HSTS — only in production (assumes TLS termination by reverse proxy)
    if not settings.debug:
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    return response


@app.middleware("http")
async def log_requests(request: Request, call_next):
    """Log every request with method, path, status code, and duration."""
    start = time.perf_counter()
    response = await call_next(request)
    duration_ms = (time.perf_counter() - start) * 1000
    # Skip logging static asset requests to reduce noise
    if request.url.path.startswith("/api"):
        logger.info(
            "%s %s → %s (%.1fms)",
            request.method,
            request.url.path,
            response.status_code,
            duration_ms,
        )
    return response


# ── Global Exception Handler ─────────────────────────────────────

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Catch unhandled exceptions — log details server-side, return generic error."""
    logger.exception("Unhandled exception on %s %s", request.method, request.url.path)
    return JSONResponse(
        status_code=500,
        content={"detail": "An internal error occurred."},
    )


# ── Health Check ──────────────────────────────────────────────────

@app.get("/api/health", tags=["Health"])
def health_check(db: Session = Depends(get_db)):
    """Health check endpoint for load balancers and container orchestrators."""
    try:
        db.execute(text("SELECT 1"))
        return {"status": "ok"}
    except Exception:
        logger.exception("Health check failed — database unreachable")
        return JSONResponse(
            status_code=503,
            content={"status": "unhealthy", "detail": "Database unreachable"},
        )


# ── List API Routes ──────────────────────────────────────────────

@app.get("/api/lists", response_model=ListType[schemas.List])
@limiter.limit("100/minute")
def read_lists(
    request: Request,
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=200),
    db: Session = Depends(get_db)
):
    lists = crud.get_lists(db, skip=skip, limit=limit)
    return lists

@app.post("/api/lists", response_model=schemas.List, status_code=status.HTTP_201_CREATED)
@limiter.limit("30/minute")
def create_list(
    request: Request,
    list_schema: schemas.ListCreate,
    db: Session = Depends(get_db)
):
    db_list = crud.get_list_by_name(db, name=list_schema.name.strip())
    if db_list:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A space with this name already exists"
        )
    return crud.create_list(db, list_schema=list_schema)

@app.put("/api/lists/{list_id}", response_model=schemas.List)
@limiter.limit("30/minute")
def rename_list(
    request: Request,
    list_id: int = Path(gt=0),
    list_schema: schemas.ListUpdate = ...,
    db: Session = Depends(get_db)
):
    # Check if the new name collides with another list
    existing = crud.get_list_by_name(db, name=list_schema.name.strip())
    if existing and existing.id != list_id:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A space with this name already exists"
        )
    db_list = crud.update_list(db, list_id=list_id, list_schema=list_schema)
    if not db_list:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="List not found"
        )
    return db_list

@app.delete("/api/lists/{list_id}")
@limiter.limit("30/minute")
def delete_list(
    request: Request,
    list_id: int = Path(gt=0),
    db: Session = Depends(get_db)
):
    success = crud.delete_list(db, list_id=list_id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="List not found"
        )
    return {"message": "List and associated tasks deleted successfully"}


# ── Task API Routes ──────────────────────────────────────────────

@app.get("/api/tasks", response_model=ListType[schemas.Task])
@limiter.limit("100/minute")
def read_tasks(
    request: Request,
    list_id: Optional[int] = Query(None, gt=0),
    is_completed: Optional[bool] = None,
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=200),
    db: Session = Depends(get_db)
):
    tasks = crud.get_tasks(db, list_id=list_id, is_completed=is_completed, skip=skip, limit=limit)
    return tasks

@app.post("/api/tasks", response_model=schemas.Task, status_code=status.HTTP_201_CREATED)
@limiter.limit("30/minute")
def create_task(
    request: Request,
    task_schema: schemas.TaskCreate,
    db: Session = Depends(get_db)
):
    # Verify list exists
    db_list = crud.get_list(db, list_id=task_schema.list_id)
    if not db_list:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Target list does not exist"
        )
    return crud.create_task(db, task_schema=task_schema)

@app.put("/api/tasks/{task_id}", response_model=schemas.Task)
@limiter.limit("60/minute")
def update_task(
    request: Request,
    task_id: int = Path(gt=0),
    task_schema: schemas.TaskUpdate = ...,
    db: Session = Depends(get_db)
):
    # If list_id is being updated, verify it exists
    if task_schema.list_id is not None:
        db_list = crud.get_list(db, list_id=task_schema.list_id)
        if not db_list:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Target list does not exist"
            )

    db_task = crud.update_task(db, task_id=task_id, task_schema=task_schema)
    if not db_task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Task not found"
        )
    return db_task

@app.delete("/api/tasks/{task_id}")
@limiter.limit("30/minute")
def delete_task(
    request: Request,
    task_id: int = Path(gt=0),
    db: Session = Depends(get_db)
):
    success = crud.delete_task(db, task_id=task_id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Task not found"
        )
    return {"message": "Task deleted successfully"}


# ── Static Files (Frontend) ──────────────────────────────────────
# Mount LAST so it doesn't shadow /api paths.
app.mount("/", StaticFiles(directory="frontend", html=True), name="frontend")
