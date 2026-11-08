"""Small, content-free internal commands. Source labels are not authentication."""
from dataclasses import dataclass, field
from enum import Enum
import re
from types import MappingProxyType
from typing import Mapping

from .operation_state import OperationState


class CommandType(str, Enum):
    GET_STATUS = "GET_STATUS"
    GET_CAPABILITIES = "GET_CAPABILITIES"
    START_MODE = "START_MODE"
    CANCEL_OPERATION = "CANCEL_OPERATION"


class CommandSource(str, Enum):
    PHYSICAL_INPUT = "PHYSICAL_INPUT"
    FUTURE_MOBILE_REQUEST = "FUTURE_MOBILE_REQUEST"


class CommandValidationError(ValueError):
    """A safe error code, without caller-supplied payload in its message."""

    def __init__(self, code):
        self.code = code
        super().__init__(code)


def valid_request_id(value):
    return isinstance(value, str) and re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._:-]{0,95}", value) is not None


@dataclass(frozen=True)
class CommandRequest:
    request_id: str
    command_type: CommandType
    source: CommandSource
    parameters: Mapping[str, str] = field(default_factory=dict, repr=False)

    def __post_init__(self):
        if not valid_request_id(self.request_id):
            raise CommandValidationError("INVALID_REQUEST_ID")
        if not isinstance(self.command_type, CommandType):
            raise CommandValidationError("INVALID_COMMAND")
        if not isinstance(self.source, CommandSource):
            raise CommandValidationError("INVALID_SOURCE")
        if not isinstance(self.parameters, Mapping):
            raise CommandValidationError("INVALID_PARAMETERS")
        parameters = dict(self.parameters)
        keys = {
            CommandType.GET_STATUS: set(), CommandType.GET_CAPABILITIES: set(),
            CommandType.START_MODE: {"mode"}, CommandType.CANCEL_OPERATION: {"target_request_id"},
        }[self.command_type]
        if parameters.keys() != keys:
            raise CommandValidationError("INVALID_PARAMETERS")
        if self.command_type == CommandType.START_MODE:
            if not isinstance(parameters["mode"], str) or len(parameters["mode"]) != 1:
                raise CommandValidationError("INVALID_MODE")
        if self.command_type == CommandType.CANCEL_OPERATION:
            if not valid_request_id(parameters["target_request_id"]):
                raise CommandValidationError("INVALID_TARGET")
        object.__setattr__(self, "parameters", MappingProxyType(parameters))


@dataclass(frozen=True)
class ModeCapability:
    mode: str
    enabled: bool
    module_loaded: bool | None = None
    dependencies_available: bool | None = None
    hardware_available: bool | None = None
    hardware_validated: bool | None = None
    interactive_input_required: bool = True
    cancellation_supported: bool = False


@dataclass(frozen=True)
class CommandReceipt:
    request_id: str
    state: OperationState
    error_code: str | None = None
    mode: str | None = None
    # Detached metadata only; never a mode handler's return value or exception.
    data: dict = field(default_factory=dict, repr=False)
