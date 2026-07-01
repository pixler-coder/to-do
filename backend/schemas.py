from datetime import datetime
from typing import List as ListType, Optional
from pydantic import BaseModel, ConfigDict, Field

# Task Schemas
class TaskBase(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)
    title: str = Field(..., min_length=1, max_length=500)
    description: Optional[str] = Field(None, max_length=2000)
    is_completed: Optional[bool] = False
    due_date: Optional[datetime] = None
    list_id: int = Field(..., gt=0)

class TaskCreate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)
    title: str = Field(..., min_length=1, max_length=500)
    description: Optional[str] = Field(None, max_length=2000)
    due_date: Optional[datetime] = None
    list_id: int = Field(..., gt=0)

class TaskUpdate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)
    title: Optional[str] = Field(None, min_length=1, max_length=500)
    description: Optional[str] = Field(None, max_length=2000)
    is_completed: Optional[bool] = None
    due_date: Optional[datetime] = None
    list_id: Optional[int] = Field(None, gt=0)

class Task(TaskBase):
    id: int

    model_config = ConfigDict(from_attributes=True, str_strip_whitespace=True)

# List Schemas
class ListBase(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)
    name: str = Field(..., min_length=1, max_length=50)

class ListCreate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)
    name: str = Field(..., min_length=1, max_length=50)

class ListUpdate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)
    name: str = Field(..., min_length=1, max_length=50)

class List(ListBase):
    id: int
    tasks: ListType[Task] = []

    model_config = ConfigDict(from_attributes=True, str_strip_whitespace=True)
