"""Bounded, in-memory admission and tracking. This module never executes modes."""
from collections import deque
from copy import deepcopy
from dataclasses import asdict, dataclass, field
import math
import threading
import time
from typing import Mapping

from .command_models import (CommandReceipt, CommandRequest, CommandSource,
                             CommandType, CommandValidationError, ModeCapability)
from .operation_state import OperationState as State, TERMINAL_STATES, transition


@dataclass
class _Record:
    request: CommandRequest
    created: float
    state: State = State.PENDING
    finished: float | None = None
    error_code: str | None = None
    data: dict = field(default_factory=dict)
    cancel_event: threading.Event = field(default_factory=threading.Event)


class CommandBroker:
    """One execution owner; thread-safe submission/status from internal clients.

    Limits are fail-closed: unexpired history is never evicted to admit more
    requests. At-most-once applies only while an ID is retained in this process.
    No handler, hardware object, policy or confidential result is stored here.
    """

    def __init__(self, capabilities: Mapping[str, ModeCapability], *, max_pending=4,
                 max_records=128, pending_timeout=15.0, retention_seconds=300.0,
                 clock=time.monotonic):
        if (type(max_pending) is not int or type(max_records) is not int
                or not 1 <= max_pending <= max_records):
            raise ValueError("Invalid broker capacity")
        for value in (pending_timeout, retention_seconds):
            if isinstance(value, bool) or not math.isfinite(value) or value <= 0:
                raise ValueError("Invalid broker deadline")
        self._lock = threading.Lock()
        self._owner = threading.current_thread()
        self._clock = clock
        self._max_pending = max_pending
        self._max_records = max_records
        self._pending_timeout = pending_timeout
        self._retention = retention_seconds
        self._records = {}
        self._pending = deque()
        self._active = None
        self._closed = False
        self._last_operation_status = None
        self._work = threading.Event()
        self._capabilities = self._validate_capabilities(capabilities)

    @staticmethod
    def _validate_capabilities(capabilities):
        result = dict(capabilities)
        if any(not isinstance(key, str) or not isinstance(value, ModeCapability)
               or key != value.mode for key, value in result.items()):
            raise ValueError("Invalid mode capability registry")
        return result

    def _assert_owner(self):
        if threading.current_thread() is not self._owner:
            raise RuntimeError("Only the designated execution owner may advance modes")

    def update_capabilities(self, capabilities):
        self._assert_owner()
        checked = self._validate_capabilities(capabilities)
        with self._lock:
            self._capabilities = checked

    def _change(self, record, state, error_code=None):
        record.state = transition(record.state, state)
        record.error_code = error_code
        if state in TERMINAL_STATES:
            record.finished = self._clock()
        if record.request.command_type == CommandType.START_MODE:
            self._last_operation_status = state.value

    def _sweep(self):
        now = self._clock()
        for record in self._records.values():
            if record.state == State.PENDING and now - record.created >= self._pending_timeout:
                self._change(record, State.REJECTED, "REQUEST_TIMEOUT")
        expired = [key for key, value in self._records.items()
                   if value.finished is not None and now - value.finished >= self._retention]
        for key in expired:
            del self._records[key]
        self._pending = deque(key for key in self._pending if key in self._records
                              and self._records[key].state == State.PENDING)
        if not self._pending:
            self._work.clear()

    @staticmethod
    def _receipt(record):
        return CommandReceipt(record.request.request_id, record.state, record.error_code,
                              record.request.parameters.get("mode"), deepcopy(record.data))

    @staticmethod
    def _refuse(request, code):
        return CommandReceipt(request.request_id, State.REJECTED, code,
                              request.parameters.get("mode"))

    def _mode_error(self, mode):
        capability = self._capabilities.get(mode)
        if capability is None:
            return "UNKNOWN_MODE"
        if not capability.enabled:
            return "MODE_DISABLED"
        return None

    def submit(self, request: CommandRequest) -> CommandReceipt:
        if not isinstance(request, CommandRequest):
            raise CommandValidationError("INVALID_REQUEST")
        with self._lock:
            self._sweep()
            existing = self._records.get(request.request_id)
            if existing is not None:
                return (self._receipt(existing) if existing.request == request else
                        self._refuse(request, "REQUEST_ID_CONFLICT"))
            if self._closed:
                return self._refuse(request, "BROKER_CLOSED")
            if len(self._records) >= self._max_records:
                return self._refuse(request, "HISTORY_FULL")
            record = _Record(request, self._clock())
            self._records[request.request_id] = record
            if request.command_type == CommandType.START_MODE:
                error = self._mode_error(request.parameters["mode"])
                if error is None and self._active is not None:
                    error = "TERMINAL_BUSY"
                if error is None and len(self._pending) >= self._max_pending:
                    # A physical selection may displace a pending simulated request.
                    displaced = next((key for key in self._pending if
                                      self._records[key].request.source == CommandSource.FUTURE_MOBILE_REQUEST), None)
                    if request.source == CommandSource.PHYSICAL_INPUT and displaced is not None:
                        self._change(self._records[displaced], State.REJECTED, "PHYSICAL_PRIORITY")
                        self._pending.remove(displaced)
                    else:
                        error = "QUEUE_FULL"
                if error:
                    self._change(record, State.REJECTED, error)
                else:
                    self._pending.append(request.request_id)
                    self._work.set()
            elif request.command_type == CommandType.CANCEL_OPERATION:
                error, data = self._cancel(request.parameters["target_request_id"])
                record.data = data
                if error:
                    self._change(record, State.REJECTED, error)
                else:
                    self._change(record, State.RUNNING)
                    self._change(record, State.COMPLETED)
            else:
                self._change(record, State.RUNNING)
                record.data = (self._status() if request.command_type == CommandType.GET_STATUS
                               else self._capabilities_data())
                self._change(record, State.COMPLETED)
            return self._receipt(record)

    def _cancel(self, target_id):
        target = self._records.get(target_id)
        if target is None or target.request.command_type != CommandType.START_MODE:
            return "UNKNOWN_OPERATION", {}
        if target.state == State.PENDING:
            self._change(target, State.CANCELLED)
            self._pending.remove(target_id)
            target.cancel_event.set()
        elif target.state == State.RUNNING:
            capability = self._capabilities.get(target.request.parameters["mode"])
            if capability is None or not capability.cancellation_supported:
                return "CANCELLATION_UNSUPPORTED", {"target_state": target.state.value}
            self._change(target, State.CANCEL_REQUESTED)
            target.cancel_event.set()
        # Repeated cancellation never overwrites a terminal state.
        return None, {"target_request_id": target_id, "target_state": target.state.value}

    def take_next(self, *, allow_dispatch=True) -> CommandRequest | None:
        self._assert_owner()
        with self._lock:
            self._sweep()
            if self._closed or self._active is not None or not allow_dispatch:
                return None
            ordered = sorted(self._pending, key=lambda key:
                             self._records[key].request.source != CommandSource.PHYSICAL_INPUT)
            for key in ordered:
                record = self._records[key]
                error = self._mode_error(record.request.parameters["mode"])
                self._pending.remove(key)
                if error:
                    self._change(record, State.REJECTED, error)
                    continue
                self._change(record, State.RUNNING)
                self._active = key
                # No mode request waits behind a long interactive operation.
                for other in self._pending:
                    reason = ("PHYSICAL_PRIORITY" if record.request.source == CommandSource.PHYSICAL_INPUT
                              else "TERMINAL_BUSY")
                    self._change(self._records[other], State.REJECTED, reason)
                self._pending.clear()
                self._work.clear()
                return record.request
            self._work.clear()
            return None

    def cancellation_event(self, request_id):
        """Only an execution adapter may consume a supported cancellation signal."""
        self._assert_owner()
        with self._lock:
            if self._active != request_id:
                raise ValueError("No matching active operation")
            return self._records[request_id].cancel_event

    def finish(self, request_id, state=State.COMPLETED, *, error_code=None):
        self._assert_owner()
        if state not in (State.COMPLETED, State.FAILED, State.CANCELLED):
            raise ValueError("Invalid completion state")
        if error_code not in (None, "MODE_EXECUTION_FAILED", "INTERRUPTED", "MODE_DISABLED", "UNKNOWN_MODE"):
            raise ValueError("Invalid completion code")
        with self._lock:
            if self._active != request_id:
                raise ValueError("No matching active operation")
            record = self._records[request_id]
            # transition() forbids RUNNING -> CANCELLED without a request.
            self._change(record, state, error_code)
            self._active = None
            return self._receipt(record)

    def get_operation(self, request_id):
        with self._lock:
            self._sweep()
            record = self._records.get(request_id)
            return self._receipt(record) if record is not None else None

    def _status(self):
        record = self._records.get(self._active)
        return {
            "terminal_state": ("SHUTTING_DOWN" if record else "CLOSED") if self._closed else
                              ("BUSY" if record else "IDLE"),
            "active_mode": record.request.parameters["mode"] if record else None,
            "active_request_id": self._active,
            "pending_request_count": len(self._pending),
            "last_operation_status": self._last_operation_status,
            "retained_request_count": len(self._records),
        }

    def get_status(self):
        with self._lock:
            self._sweep()
            return self._status()

    def _capabilities_data(self):
        return {"modes": [dict(exists=True, **asdict(value)) for value in self._capabilities.values()],
                "authentication": "NOT_IMPLEMENTED_INTERNAL_ONLY",
                "max_pending": self._max_pending, "max_records": self._max_records,
                "pending_timeout_seconds": self._pending_timeout,
                "retention_seconds": self._retention}

    def get_capabilities(self):
        with self._lock:
            return self._capabilities_data()

    def wait_for_work(self, timeout):
        """A bounded wait for non-hardware clients; creates no thread."""
        if isinstance(timeout, bool) or not math.isfinite(timeout) or timeout < 0:
            raise ValueError("A finite wait is required")
        self._work.wait(timeout)
        with self._lock:
            self._sweep()
            return bool(self._pending) and not self._closed

    def close(self):
        """Cancel pending work; active cleanup remains the execution owner's job."""
        with self._lock:
            if self._closed:
                return
            self._closed = True
            for key in self._pending:
                self._change(self._records[key], State.CANCELLED, "BROKER_CLOSED")
                self._records[key].cancel_event.set()
            self._pending.clear()
            if self._active is not None:
                active = self._records[self._active]
                if active.state == State.RUNNING:
                    self._change(active, State.CANCEL_REQUESTED)
                active.cancel_event.set()
            self._work.set()
