"""Execute the actual controller functions with initialization removed by AST.

This harness intentionally does not import main: imports there open serial and
probe optional devices. Handlers and hardware are doubles; dispatcher/main-loop
function bodies below are compiled directly from the repository source.
"""
import ast
from collections import deque
import concurrent.futures
from pathlib import Path
import sys
import threading
import types
import unittest
from unittest import mock

from gateway.command_broker import CommandBroker
from gateway.command_models import (CommandRequest, CommandSource as Source,
                                    CommandType as Type, CommandValidationError)
from gateway.operation_state import OperationState as State
from modules.privacy_policy import PUBLIC, PRIVATE, current_policy, processing_session


ROOT = Path(__file__).resolve().parents[1]


class Clock:
    def __init__(self):
        self.now = 0.0

    def monotonic(self):
        return self.now

    time = monotonic

    def sleep(self, delay):
        self.now += delay


class SerialDouble:
    def __init__(self, clock, events=()):
        self.clock = clock
        self.events = deque(events)
        self.readers = []
        self.read_menu_digit = mock.Mock(return_value="6")
        self.wait_for_confirm = mock.Mock(return_value=True)
        self.close = mock.Mock()

    def get_message(self, timeout=None):
        self.readers.append(threading.current_thread())
        if self.events and self.events[0][0] > self.clock.now:
            self.clock.now = min(self.events[0][0], self.clock.now + (timeout or 0))
        if self.events and self.events[0][0] <= self.clock.now:
            return self.events.popleft()[1]
        self.clock.now += timeout or 0
        return None


def controller():
    names = {"_command_capabilities", "_initialize_command_dispatcher", "_disable_command_dispatcher",
             "_execute_broker_request", "_physical_mode_request", "run_mode", "_run_mode",
             "_cooperative_menu_choice", "_get_menu_choice", "_has_any_input_device", "main",
             "shutdown", "_has", "_object_detection_stop_requested"}
    tree = ast.parse((ROOT / "main.py").read_text())
    selected = [node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name in names]
    assert {node.name for node in selected} == names
    module = types.ModuleType("isolated_controller")
    clock = Clock()
    module.__dict__.update({
        "threading": threading, "time": clock, "sys": sys, "BASE_DIR": ROOT,
        "PUBLIC": PUBLIC, "current_policy": current_policy, "processing_session": processing_session,
        "_command_broker": None, "_mode_execution_thread": threading.current_thread(),
        "_mode_execution_depth": 0, "_dispatching_request_id": None, "_mode_failed": False,
        "_shutdown_done": False, "_settings": {"enabled_modes": list("12345689")},
        "_modules": {name: mock.Mock() for name in ("ocr", "voice", "ai_query", "morse", "tts",
                     "translator", "gesture", "objdetect", "gps", "privacy", "mathsolver")},
        "MODE_MAP": {mode: mock.Mock(return_value=None) for mode in "123456789"},
        "BANNER": "test terminal", "logger": mock.Mock(), "_speak": mock.Mock(),
        "_keyboard_input": mock.Mock(return_value="1"), "_STDIN_IS_TTY": False,
        "_morse_serial_singleton": SerialDouble(clock), "print": mock.Mock(),
    })
    exec(compile(ast.Module(body=selected, type_ignores=[]), str(ROOT / "main.py"), "exec"), module.__dict__)
    return module


def mobile(identifier="mobile-1", mode="1"):
    return CommandRequest(identifier, Type.START_MODE, Source.FUTURE_MOBILE_REQUEST, {"mode": mode})


class MobileDispatchRegressionTests(unittest.TestCase):
    def setUp(self):
        self.main = controller()
        self.broker = self.main._initialize_command_dispatcher()

    def test_standalone_without_mobile_preserves_handler_and_cleanup(self):
        self.main.run_mode("1")
        self.main.MODE_MAP["1"].assert_called_once_with()
        self.main._modules["voice"].clear_private_recordings.assert_called_once_with()
        self.assertEqual(self.broker.get_status()["terminal_state"], "IDLE")

    def test_idle_mobile_executes_on_menu_owner_and_none_is_successful_lifecycle(self):
        owner = threading.current_thread()
        self.main.MODE_MAP["1"].side_effect = lambda: self.assertIs(threading.current_thread(), owner)
        self.broker.submit(mobile())
        selected = self.main._get_menu_choice()
        self.assertEqual(selected.request_id, "mobile-1")
        self.assertEqual(self.broker.get_operation("mobile-1").state, State.RUNNING)
        self.assertIsNone(self.main._execute_broker_request(selected))
        self.assertEqual(self.broker.get_operation("mobile-1").state, State.COMPLETED)
        self.assertEqual(set(self.main._morse_serial_singleton.readers), {owner})

    def test_partial_morse_then_physical_choice_preempts_waiting_mobile(self):
        serial = self.main._morse_serial_singleton
        serial.events.extend([(0, "RAW:1"), (1, "LETTER:E"), (2, "RAW:2"),
                              (3, "RAW:2"), (4, "RAW:2"), (5, "RAW:2")])
        self.broker.submit(mobile("waiting", "6"))
        self.assertEqual(self.main._get_menu_choice(), "1")
        self.assertEqual(self.broker.get_operation("waiting").state, State.PENDING)
        self.main.run_mode("1")
        self.assertEqual(self.broker.get_operation("waiting").error_code, "PHYSICAL_PRIORITY")
        self.main.MODE_MAP["1"].assert_called_once()
        self.main.MODE_MAP["6"].assert_not_called()
        serial.read_menu_digit.assert_not_called()

    def test_expired_partial_does_not_hold_mobile_indefinitely(self):
        self.main._morse_serial_singleton.events.append((0, "RAW:1"))
        self.broker.submit(mobile())
        self.assertEqual(self.main._get_menu_choice().request_id, "mobile-1")
        self.assertGreater(self.main.time.now, 5)

    def test_already_arrived_physical_digit_wins_over_mobile(self):
        self.broker.submit(mobile())
        self.main._morse_serial_singleton.events.append((0, "LETTER:6"))
        self.assertEqual(self.main._get_menu_choice(), "6")
        self.assertEqual(self.broker.get_operation("mobile-1").state, State.PENDING)

    def test_handler_retains_input_ownership_and_broker_rejects_conflict(self):
        serial = self.main._morse_serial_singleton
        def handler():
            serial.events.append((self.main.time.now, "CONFIRM"))
            self.assertEqual(serial.get_message(timeout=.1), "CONFIRM")
            result = self.broker.submit(mobile("conflict", "6"))
            self.assertEqual(result.error_code, "TERMINAL_BUSY")
        self.main.MODE_MAP["1"].side_effect = handler
        self.main.run_mode("1")
        self.assertEqual(len(serial.readers), 1)
        self.main.MODE_MAP["6"].assert_not_called()

    def test_duplicate_mobile_request_never_repeats_execution(self):
        self.broker.submit(mobile())
        self.main._execute_broker_request(self.broker.take_next())
        self.assertEqual(self.broker.submit(mobile()).state, State.COMPLETED)
        self.assertIsNone(self.broker.take_next())
        self.main.MODE_MAP["1"].assert_called_once()

    def test_disabled_mode_and_last_moment_restriction_are_enforced(self):
        self.assertEqual(self.broker.submit(mobile("gps", "7")).error_code, "MODE_DISABLED")
        self.broker.submit(mobile())
        selected = self.broker.take_next()
        self.main._settings["enabled_modes"] = ["6"]
        self.main._execute_broker_request(selected)
        self.assertEqual(self.broker.get_operation("mobile-1").error_code, "MODE_DISABLED")
        self.main.MODE_MAP["1"].assert_not_called()
        self.main.MODE_MAP["7"].assert_not_called()

    def test_private_policy_and_sensitive_returns_never_enter_status(self):
        def handler():
            self.assertIs(current_policy(), PRIVATE)
            return "PRIVATE_DOCUMENT_SENTINEL"
        self.main.MODE_MAP["1"].side_effect = handler
        self.broker.submit(mobile())
        selected = self.broker.take_next()
        with processing_session(PRIVATE):
            self.assertEqual(self.main._execute_broker_request(selected), "PRIVATE_DOCUMENT_SENTINEL")
            self.assertIs(current_policy(), PRIVATE)
        self.assertIs(current_policy(), PUBLIC)
        receipt = self.broker.get_operation("mobile-1")
        self.assertEqual(receipt.state, State.COMPLETED)
        self.assertNotIn("SENTINEL", repr(receipt.data) + repr(self.broker.get_status()))
        self.main._speak.assert_not_called()

    def test_failed_handler_is_recorded_without_exception_text_and_terminal_recovers(self):
        self.main.MODE_MAP["1"].side_effect = ValueError("PRIVATE_SENTINEL")
        self.broker.submit(mobile())
        self.main._execute_broker_request(self.broker.take_next())
        receipt = self.broker.get_operation("mobile-1")
        self.assertEqual(receipt.state, State.FAILED)
        self.assertEqual(receipt.error_code, "MODE_EXECUTION_FAILED")
        self.assertNotIn("PRIVATE_SENTINEL", str(self.main.logger.mock_calls) + str(receipt))
        self.main.run_mode("6")
        self.main.MODE_MAP["6"].assert_called_once()

    def test_nested_gesture_dispatch_inherits_policy_and_single_operation(self):
        self.main.MODE_MAP["5"].side_effect = lambda: self.main.run_mode("1")
        self.main.MODE_MAP["1"].side_effect = lambda: self.assertIs(current_policy(), PRIVATE)
        with processing_session(PRIVATE):
            self.main.run_mode("5")
        self.main.MODE_MAP["1"].assert_called_once()
        self.assertEqual(self.broker.get_status()["retained_request_count"], 1)

    def test_worker_cannot_execute_even_when_no_mode_is_running(self):
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
            with self.assertRaises(RuntimeError):
                pool.submit(self.main.run_mode, "1").result()
        self.main.MODE_MAP["1"].assert_not_called()

    def test_pending_cancel_prevents_mode_and_active_cancel_reports_unsupported(self):
        self.broker.submit(mobile())
        cancel = lambda identifier: CommandRequest(identifier, Type.CANCEL_OPERATION,
                       Source.FUTURE_MOBILE_REQUEST, {"target_request_id": "mobile-1"})
        self.broker.submit(cancel("cancel"))
        self.assertIsNone(self.broker.take_next())
        self.main.MODE_MAP["1"].assert_not_called()
        self.broker.submit(mobile("running", "6"))
        selected = self.broker.take_next()
        active_cancel = CommandRequest("cancel-active", Type.CANCEL_OPERATION,
                       Source.FUTURE_MOBILE_REQUEST, {"target_request_id": "running"})
        self.assertEqual(self.broker.submit(active_cancel).error_code, "CANCELLATION_UNSUPPORTED")
        self.main._execute_broker_request(selected)
        self.assertEqual(self.broker.get_operation("running").state, State.COMPLETED)
        self.assertTrue(self.main._object_detection_stop_requested(3))
        self.assertFalse(self.main._object_detection_stop_requested(1))

    def test_broker_init_failure_keeps_original_morse_path(self):
        with mock.patch("gateway.command_broker.CommandBroker", side_effect=RuntimeError("failure")):
            self.assertIsNone(self.main._initialize_command_dispatcher())
        self.assertEqual(self.main._get_menu_choice(), "6")
        self.main._morse_serial_singleton.read_menu_digit.assert_called_once_with(timeout=120)
        self.main.run_mode("1")
        self.main.MODE_MAP["1"].assert_called_once()

    def test_broker_failure_during_partial_entry_keeps_the_partial_digit(self):
        serial = self.main._morse_serial_singleton
        serial.events.extend([(0, "RAW:1"), (.5, "RAW:2"), (1, "RAW:2"),
                              (1.5, "RAW:2"), (2, "RAW:2")])
        with mock.patch.object(self.broker, "take_next", side_effect=RuntimeError("failure")):
            self.assertEqual(self.main._get_menu_choice(), "1")
        self.assertIsNone(self.main._command_broker)
        serial.read_menu_digit.assert_not_called()

    def test_full_history_falls_back_to_physical_without_repeating_handler(self):
        self.main._command_broker = CommandBroker(self.main._command_capabilities(), max_pending=1, max_records=1)
        self.main.run_mode("1")
        self.main.run_mode("6")
        self.main.MODE_MAP["1"].assert_called_once()
        self.main.MODE_MAP["6"].assert_called_once()
        self.assertIsNone(self.main._command_broker)

    def test_tty_line_has_priority_and_no_second_stdin_reader(self):
        self.main._morse_serial_singleton = None
        self.main._STDIN_IS_TTY = True
        self.broker.submit(mobile("waiting", "6"))
        with mock.patch("select.select", return_value=([sys.stdin], [], [])):
            self.assertEqual(self.main._get_menu_choice(), "1")
        self.assertEqual(self.broker.get_operation("waiting").state, State.PENDING)

    def test_status_capabilities_are_internal_and_uncertainty_is_explicit(self):
        caps = self.broker.get_capabilities()["modes"]
        self.assertEqual({item["mode"] for item in caps}, set(self.main.MODE_MAP))
        self.assertFalse(next(item for item in caps if item["mode"] == "7")["enabled"])
        self.assertTrue(all(item["hardware_available"] is None and item["hardware_validated"] is None
                            and item["dependencies_available"] is None for item in caps))
        self.assertTrue(all(not item["cancellation_supported"] for item in caps))
        with self.assertRaises(CommandValidationError):
            CommandRequest("unsafe", Type.START_MODE, Source.FUTURE_MOBILE_REQUEST,
                           {"mode": "1", "function": "shutdown"})

    def test_main_loop_and_confirmed_shutdown_work_without_android(self):
        with mock.patch("modules.config_loader.load_settings", return_value=self.main._settings), \
                mock.patch.object(self.main, "_get_menu_choice", side_effect=["1", "0"]):
            self.assertEqual(self.main.main(), 0)
        self.main.MODE_MAP["1"].assert_called_once()
        self.main._morse_serial_singleton.wait_for_confirm.assert_called_once_with(timeout=5)
        self.main._morse_serial_singleton.close.assert_called_once()
        self.assertEqual(self.main._command_broker.get_status()["terminal_state"], "CLOSED")

    def test_shutdown_winning_before_handler_start_does_not_execute(self):
        self.broker.submit(mobile())
        selected = self.broker.take_next()
        self.broker.close()
        self.main._execute_broker_request(selected)
        self.main.MODE_MAP["1"].assert_not_called()
        self.assertEqual(self.broker.get_operation("mobile-1").state, State.CANCELLED)

    def test_forged_lease_and_unsupported_commands_do_not_execute(self):
        self.broker.submit(mobile())
        self.broker.take_next()
        self.main._execute_broker_request(mobile(mode="6"))
        self.main.MODE_MAP["6"].assert_not_called()
        with self.assertRaises(CommandValidationError):
            CommandRequest("shell", "EXECUTE", Source.FUTURE_MOBILE_REQUEST, {})

    def test_admission_failure_before_execution_keeps_terminal_operational(self):
        self.broker.submit(mobile())
        selected = self.broker.take_next()
        with mock.patch.object(self.broker, "get_status", side_effect=RuntimeError("failure")):
            self.main._execute_broker_request(selected)
        self.assertEqual(self.broker.get_operation("mobile-1").state, State.FAILED)
        self.main.MODE_MAP["1"].assert_not_called()
        self.assertIsNone(self.main._command_broker)
        self.main.run_mode("6")
        self.main.MODE_MAP["6"].assert_called_once()

    def test_completion_tracking_failure_never_replays_a_handler(self):
        self.broker.submit(mobile())
        selected = self.broker.take_next()
        with mock.patch.object(self.broker, "finish", side_effect=RuntimeError("failure")):
            self.main._execute_broker_request(selected)
        self.main.MODE_MAP["1"].assert_called_once()
        self.assertIsNone(self.main._command_broker)
        self.main.run_mode("6")
        self.main.MODE_MAP["6"].assert_called_once()

    def test_private_handler_exception_after_capacity_fallback_is_not_retried(self):
        self.main._command_broker = CommandBroker(self.main._command_capabilities(), max_pending=1, max_records=1)
        self.main.run_mode("1")
        self.main.MODE_MAP["6"].side_effect = ValueError("PRIVATE_SENTINEL")
        with processing_session(PRIVATE), self.assertRaises(ValueError):
            self.main.run_mode("6")
        self.main.MODE_MAP["6"].assert_called_once()

    def test_failure_to_speak_an_error_does_not_crash_mobile_dispatch(self):
        self.main.MODE_MAP["1"].side_effect = ValueError("PRIVATE_SENTINEL")
        self.main._speak.side_effect = RuntimeError("audio unavailable")
        self.broker.submit(mobile())
        self.main._execute_broker_request(self.broker.take_next())
        self.assertEqual(self.broker.get_operation("mobile-1").state, State.FAILED)
        self.assertEqual(self.broker.get_status()["terminal_state"], "IDLE")
        self.assertNotIn("PRIVATE_SENTINEL", str(self.main.logger.mock_calls))
