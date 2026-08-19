from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional, TypeVar, Union

from pydantic import BaseModel, ConfigDict

T = TypeVar("T", bound="DocBase")


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class DocBase(BaseModel):
    """Base for MongoDB documents (no _id stored on our side)."""

    model_config = ConfigDict(extra="ignore")

    @classmethod
    def from_doc(cls: type[T], doc: Optional[dict[str, Any]]) -> Optional[T]:
        if not doc:
            return None
        return cls(**{k: v for k, v in doc.items() if k != "_id"})