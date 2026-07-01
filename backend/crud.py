import logging
from typing import Optional
from sqlalchemy.orm import Session
from sqlalchemy import asc, func
from . import models, schemas

logger = logging.getLogger("neotask.crud")

# ── List CRUD ─────────────────────────────────────────────────────

def get_list(db: Session, list_id: int):
    return db.query(models.List).filter(models.List.id == list_id).first()

def get_list_by_name(db: Session, name: str):
    """Case-insensitive name lookup to prevent confusing near-duplicates."""
    return db.query(models.List).filter(
        func.lower(models.List.name) == name.lower()
    ).first()

def get_lists(db: Session, skip: int = 0, limit: int = 100):
    return db.query(models.List).order_by(asc(models.List.id)).offset(skip).limit(limit).all()

def create_list(db: Session, list_schema: schemas.ListCreate):
    # Strip whitespace from name for consistent uniqueness checks
    db_list = models.List(name=list_schema.name.strip())
    db.add(db_list)
    try:
        db.commit()
        db.refresh(db_list)
    except Exception:
        db.rollback()
        logger.exception("Failed to create list: %s", list_schema.name)
        raise
    return db_list

def update_list(db: Session, list_id: int, list_schema: schemas.ListUpdate):
    db_list = db.query(models.List).filter(models.List.id == list_id).first()
    if not db_list:
        return None
    db_list.name = list_schema.name.strip()
    try:
        db.commit()
        db.refresh(db_list)
    except Exception:
        db.rollback()
        logger.exception("Failed to update list %d", list_id)
        raise
    return db_list

def delete_list(db: Session, list_id: int):
    db_list = db.query(models.List).filter(models.List.id == list_id).first()
    if db_list:
        db.delete(db_list)
        try:
            db.commit()
        except Exception:
            db.rollback()
            logger.exception("Failed to delete list %d", list_id)
            raise
        return True
    return False


# ── Task CRUD ─────────────────────────────────────────────────────

def get_task(db: Session, task_id: int):
    return db.query(models.Task).filter(models.Task.id == task_id).first()

def get_tasks(
    db: Session,
    list_id: Optional[int] = None,
    is_completed: Optional[bool] = None,
    skip: int = 0,
    limit: int = 100
):
    query = db.query(models.Task)
    if list_id is not None:
        query = query.filter(models.Task.list_id == list_id)
    if is_completed is not None:
        query = query.filter(models.Task.is_completed == is_completed)
    
    # Order by completion status (active first), then by due date, then by ID
    query = query.order_by(
        asc(models.Task.is_completed),
        asc(models.Task.due_date),
        asc(models.Task.id)
    )
    return query.offset(skip).limit(limit).all()

def create_task(db: Session, task_schema: schemas.TaskCreate):
    db_task = models.Task(
        title=task_schema.title.strip(),
        description=task_schema.description.strip() if task_schema.description else None,
        due_date=task_schema.due_date,
        list_id=task_schema.list_id,
        is_completed=False
    )
    db.add(db_task)
    try:
        db.commit()
        db.refresh(db_task)
    except Exception:
        db.rollback()
        logger.exception("Failed to create task: %s", task_schema.title)
        raise
    return db_task

def update_task(db: Session, task_id: int, task_schema: schemas.TaskUpdate):
    db_task = db.query(models.Task).filter(models.Task.id == task_id).first()
    if not db_task:
        return None
    
    # Update fields that were explicitly set
    update_data = task_schema.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        # Strip whitespace from string fields
        if isinstance(value, str):
            value = value.strip()
        setattr(db_task, key, value)
    
    try:
        db.commit()
        db.refresh(db_task)
    except Exception:
        db.rollback()
        logger.exception("Failed to update task %d", task_id)
        raise
    return db_task

def delete_task(db: Session, task_id: int):
    db_task = db.query(models.Task).filter(models.Task.id == task_id).first()
    if db_task:
        db.delete(db_task)
        try:
            db.commit()
        except Exception:
            db.rollback()
            logger.exception("Failed to delete task %d", task_id)
            raise
        return True
    return False
