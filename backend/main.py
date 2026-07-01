from contextlib import asynccontextmanager
from typing import Optional, List as ListType
from fastapi import FastAPI, Depends, HTTPException, Query, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from .database import engine, SessionLocal, get_db
from . import models, schemas, crud

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Create database tables
    models.Base.metadata.create_all(bind=engine)
    
    # Seed initial lists if none exist
    db = SessionLocal()
    try:
        if db.query(models.List).count() == 0:
            for name in ["Inbox", "Work", "Personal", "Exams"]:
                db.add(models.List(name=name))
            db.commit()
    finally:
        db.close()
    yield

app = FastAPI(
    title="Neo-Minimalist Task Manager API",
    lifespan=lifespan,
    # Disable OpenAPI docs in production to reduce attack surface
    # docs_url=None,
    # redoc_url=None,
)

# CORS: restrict to the same origin. Wildcard "*" with credentials=True
# is both insecure and technically invalid per the Fetch spec.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://127.0.0.1:8000", "http://localhost:8000"],
    allow_credentials=False,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["Content-Type"],
)

# Security headers middleware
@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    return response

# Global exception handler for unexpected errors — avoids leaking stack traces
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    return JSONResponse(
        status_code=500,
        content={"detail": "An internal error occurred."},
    )

# --- List API Routes ---

@app.get("/api/lists", response_model=ListType[schemas.List])
def read_lists(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=200),
    db: Session = Depends(get_db)
):
    lists = crud.get_lists(db, skip=skip, limit=limit)
    return lists

@app.post("/api/lists", response_model=schemas.List, status_code=status.HTTP_201_CREATED)
def create_list(list_schema: schemas.ListCreate, db: Session = Depends(get_db)):
    db_list = crud.get_list_by_name(db, name=list_schema.name.strip())
    if db_list:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A space with this name already exists"
        )
    return crud.create_list(db, list_schema=list_schema)

@app.put("/api/lists/{list_id}", response_model=schemas.List)
def rename_list(list_id: int, list_schema: schemas.ListUpdate, db: Session = Depends(get_db)):
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
def delete_list(list_id: int, db: Session = Depends(get_db)):
    success = crud.delete_list(db, list_id=list_id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="List not found"
        )
    return {"message": "List and associated tasks deleted successfully"}

# --- Task API Routes ---

@app.get("/api/tasks", response_model=ListType[schemas.Task])
def read_tasks(
    list_id: Optional[int] = Query(None, gt=0),
    is_completed: Optional[bool] = None,
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=200),
    db: Session = Depends(get_db)
):
    tasks = crud.get_tasks(db, list_id=list_id, is_completed=is_completed, skip=skip, limit=limit)
    return tasks

@app.post("/api/tasks", response_model=schemas.Task, status_code=status.HTTP_201_CREATED)
def create_task(task_schema: schemas.TaskCreate, db: Session = Depends(get_db)):
    # Verify list exists
    db_list = crud.get_list(db, list_id=task_schema.list_id)
    if not db_list:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Target list does not exist"
        )
    return crud.create_task(db, task_schema=task_schema)

@app.put("/api/tasks/{task_id}", response_model=schemas.Task)
def update_task(task_id: int, task_schema: schemas.TaskUpdate, db: Session = Depends(get_db)):
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
def delete_task(task_id: int, db: Session = Depends(get_db)):
    success = crud.delete_task(db, task_id=task_id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Task not found"
        )
    return {"message": "Task deleted successfully"}

# Mount the static frontend. We mount this LAST so it doesn't shadow /api paths.
app.mount("/", StaticFiles(directory="frontend", html=True), name="frontend")
