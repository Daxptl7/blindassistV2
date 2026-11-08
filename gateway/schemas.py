"""Strict, content-free public request schemas; no mode results enter this API."""
from typing import Any
from pydantic import BaseModel, ConfigDict, Field, model_validator

from .ipc_protocol import public_id, validate_command


class CommandSubmission(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    request_id: str = Field(min_length=1, max_length=64)
    command_type: str
    parameters: dict[str, Any]

    @model_validator(mode="after")
    def approved(self):
        validate_command(self.model_dump())
        return self


class CancellationSubmission(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    request_id: str = Field(min_length=1, max_length=64)

    @model_validator(mode="after")
    def valid_identifier(self):
        if not public_id(self.request_id):
            raise ValueError("INVALID_REQUEST")
        return self
