from datetime import datetime
from typing import List as ListType, Optional
from pydantic import BaseModel, Field

# Task Schemas
class TaskBase(BaseModel):
    title: str = Field(..., min_length=1, max_length=500)
    description: Optional[str] = Field(None, max_length=2000)
    is_completed: Optional[bool] = False
    due_date: Optional[datetime] = None
    list_id: int = Field(..., gt=0)

class TaskCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=500)
    description: Optional[str] = Field(None, max_length=2000)
    due_date: Optional[datetime] = None
    list_id: int = Field(..., gt=0)

class TaskUpdate(BaseModel):
    title: Optional[str] = Field(None, min_length=1, max_length=500)
    description: Optional[str] = Field(None, max_length=2000)
    is_completed: Optional[bool] = None
    due_date: Optional[datetime] = None
    list_id: Optional[int] = Field(None, gt=0)

class Task(TaskBase):
    id: int

    class Config:
        from_attributes = True

# List Schemas
class ListBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=50)

class ListCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=50)

class ListUpdate(BaseModel):
    name: str = Field(..., min_length=1, max_length=50)

class List(ListBase):
    id: int
    tasks: ListType[Task] = []

    class Config:
        from_attributes = True
