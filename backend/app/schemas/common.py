from typing import Generic, TypeVar
from uuid import UUID

from pydantic import BaseModel, ConfigDict

T = TypeVar("T")


class PaginatedResponse(BaseModel, Generic[T]):
    """Cursor-based pagination response."""

    items: list[T]
    cursor: str | None = None
    has_more: bool = False


class CursorParams(BaseModel):
    cursor: str | None = None
    limit: int = 25


class ErrorResponse(BaseModel):
    code: str
    message: str
    details: dict | None = None


class SuccessResponse(BaseModel):
    message: str


class IDResponse(BaseModel):
    id: UUID


class BaseSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)
