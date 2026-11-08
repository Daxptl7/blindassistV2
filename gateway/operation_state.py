"""Request lifecycle, distinct from terminal-wide resource availability."""
from enum import Enum


class OperationState(str, Enum):
    IDLE = "IDLE"
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCEL_REQUESTED = "CANCEL_REQUESTED"
    CANCELLED = "CANCELLED"
    REJECTED = "REJECTED"


TERMINAL_STATES = frozenset({OperationState.COMPLETED, OperationState.FAILED,
                             OperationState.CANCELLED, OperationState.REJECTED})
_TRANSITIONS = {
    OperationState.IDLE: {OperationState.PENDING},
    OperationState.PENDING: {OperationState.RUNNING, OperationState.REJECTED,
                             OperationState.CANCELLED},
    OperationState.RUNNING: {OperationState.COMPLETED, OperationState.FAILED,
                             OperationState.CANCEL_REQUESTED},
    OperationState.CANCEL_REQUESTED: {OperationState.CANCELLED,
                                     OperationState.COMPLETED, OperationState.FAILED},
}


class InvalidTransition(ValueError):
    pass


def transition(current: OperationState, target: OperationState) -> OperationState:
    """Validate a transition; the caller must serialize its record mutation."""
    if (not isinstance(current, OperationState) or not isinstance(target, OperationState)
            or target not in _TRANSITIONS.get(current, ())):
        raise InvalidTransition("Invalid operation state transition")
    return target
