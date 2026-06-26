from __future__ import annotations

from pydantic import BaseModel


class SceneSpatialError(Exception):
    code = "INTERNAL_ERROR"

    def __init__(self, message: str, code: str | None = None) -> None:
        super().__init__(message)
        if code is not None:
            self.code = code


class ErrorResponse(BaseModel):
    code: str
    message: str
