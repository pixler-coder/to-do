from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import relationship

from .database import Base


class List(Base):
    __tablename__ = "lists"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, index=True, nullable=False)

    # Automatically delete all tasks associated with this list when it is deleted
    tasks = relationship("Task", back_populates="list", cascade="all, delete-orphan")


class Task(Base):
    __tablename__ = "tasks"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, index=True, nullable=False)
    description = Column(String, nullable=True)
    is_completed = Column(Boolean, default=False)
    due_date = Column(DateTime, nullable=True)
    list_id = Column(
        Integer, ForeignKey("lists.id", ondelete="CASCADE"), nullable=False
    )

    list = relationship("List", back_populates="tasks")
