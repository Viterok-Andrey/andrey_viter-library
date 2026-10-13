"""Тела запросов. При неверных данных FastAPI сам отвечает кодом 422."""
from pydantic import BaseModel, Field


class LoginRequest(BaseModel):
    username: str
    password: str


class IssueRequest(BaseModel):
    reader_id: int = Field(ge=1)
    copy_id: int = Field(ge=1)
