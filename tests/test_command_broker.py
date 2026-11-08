import concurrent.futures
import threading
import unittest

from gateway.command_broker import CommandBroker
from gateway.command_models import (CommandRequest, CommandSource as Source,
                                    CommandType as Type, CommandValidationError,
                                    ModeCapability)
from gateway.operation_state import InvalidTransition, OperationState as State


class Clock:
    now = 0.0

    def __call__(self):
        return self.now


def request(identifier="mobile-1", mode="1", source=Source.FUTURE_MOBILE_REQUEST):
    return CommandRequest(identifier, Type.START_MODE, source, {"mode": mode})


class CommandBrokerTests(unittest.TestCase):
    def setUp(self):
        self.clock = Clock()
        self.capabilities = {"1": ModeCapability("1", True),
                             "6": ModeCapability("6", True),
                             "7": ModeCapability("7", False)}
        self.broker = CommandBroker(self.capabilities, clock=self.clock)

    def test_submission_is_pending_and_only_owner_can_start_and_complete(self):
        self.assertEqual(self.broker.submit(request()).state, State.PENDING)
        self.assertEqual(self.broker.get_status()["terminal_state"], "IDLE")
        selected = self.broker.take_next()
        self.assertEqual(selected.parameters["mode"], "1")
        self.assertEqual(self.broker.get_operation(selected.request_id).state, State.RUNNING)
        self.assertEqual(self.broker.get_status()["active_mode"], "1")
        self.broker.finish(selected.request_id)
        self.assertEqual(self.broker.get_operation(selected.request_id).state, State.COMPLETED)
        self.assertEqual(self.broker.get_status()["terminal_state"], "IDLE")

    def test_invalid_request_unknown_and_disabled_modes(self):
        with self.assertRaises(CommandValidationError):
            self.broker.submit({"command_type": "SHELL"})
        self.assertEqual(self.broker.submit(request("unknown", "0")).error_code, "UNKNOWN_MODE")
        self.assertEqual(self.broker.submit(request("disabled", "7")).error_code, "MODE_DISABLED")
        self.assertIsNone(self.broker.take_next())

    def test_busy_rejects_second_mode_without_changing_active_operation(self):
        self.broker.submit(request())
        self.broker.take_next()
        self.assertEqual(self.broker.submit(request("second", "6")).error_code, "TERMINAL_BUSY")
        self.assertEqual(self.broker.get_operation("mobile-1").state, State.RUNNING)
        self.assertEqual(self.broker.get_status()["terminal_state"], "BUSY")

    def test_retained_duplicate_never_executes_again_and_conflict_does_not_replace_it(self):
        self.broker.submit(request())
        self.assertEqual(self.broker.submit(request()).state, State.PENDING)
        conflict = self.broker.submit(request(mode="6"))
        self.assertEqual(conflict.error_code, "REQUEST_ID_CONFLICT")
        self.assertEqual(self.broker.take_next().parameters["mode"], "1")
        self.broker.finish("mobile-1")
        self.assertEqual(self.broker.submit(request()).state, State.COMPLETED)
        self.assertIsNone(self.broker.take_next())
        changed_source = request(source=Source.PHYSICAL_INPUT)
        self.assertEqual(self.broker.submit(changed_source).error_code, "REQUEST_ID_CONFLICT")

    def test_pending_queue_is_bounded_and_physical_selection_can_displace_mobile(self):
        broker = CommandBroker(self.capabilities, max_pending=1)
        broker.submit(request())
        self.assertEqual(broker.submit(request("full")).error_code, "QUEUE_FULL")
        self.assertEqual(broker.submit(request("physical", "6", Source.PHYSICAL_INPUT)).state,
                         State.PENDING)
        self.assertEqual(broker.take_next().request_id, "physical")
        self.assertEqual(broker.get_operation("mobile-1").error_code, "PHYSICAL_PRIORITY")

    def test_physical_first_and_no_waiting_mode_behind_active_mode(self):
        self.broker.submit(request())
        self.broker.submit(request("other", "6"))
        self.broker.submit(request("physical", "1", Source.PHYSICAL_INPUT))
        self.assertEqual(self.broker.take_next().request_id, "physical")
        self.assertEqual(self.broker.get_status()["pending_request_count"], 0)
        self.assertEqual(self.broker.get_operation("other").error_code, "PHYSICAL_PRIORITY")

    def test_pending_requests_expire_even_while_physical_input_prevents_dispatch(self):
        self.broker.submit(request())
        self.clock.now = 15
        self.assertIsNone(self.broker.take_next(allow_dispatch=False))
        self.assertEqual(self.broker.get_operation("mobile-1").error_code, "REQUEST_TIMEOUT")
        self.assertEqual(self.broker.get_status()["pending_request_count"], 0)

    def test_restrictions_are_rechecked_before_start(self):
        self.broker.submit(request())
        self.broker.update_capabilities({"1": ModeCapability("1", False)})
        self.assertIsNone(self.broker.take_next())
        self.assertEqual(self.broker.get_operation("mobile-1").state, State.REJECTED)
        self.assertEqual(self.broker.get_operation("mobile-1").error_code, "MODE_DISABLED")

    def test_failed_handler_state_is_separate_from_terminal_availability(self):
        self.broker.submit(request())
        self.broker.take_next()
        self.broker.finish("mobile-1", State.FAILED, error_code="MODE_EXECUTION_FAILED")
        self.assertEqual(self.broker.get_status()["terminal_state"], "IDLE")
        self.assertEqual(self.broker.get_operation("mobile-1").state, State.FAILED)
        self.assertEqual(self.broker.submit(request("next", "6")).state, State.PENDING)

    def test_pending_cancel_prevents_execution(self):
        self.broker.submit(request())
        cancel = CommandRequest("cancel", Type.CANCEL_OPERATION, Source.FUTURE_MOBILE_REQUEST,
                                {"target_request_id": "mobile-1"})
        result = self.broker.submit(cancel)
        self.assertEqual(result.state, State.COMPLETED)
        self.assertEqual(result.data["target_state"], "CANCELLED")
        self.assertIsNone(self.broker.take_next())
        self.assertEqual(self.broker.submit(request()).state, State.CANCELLED)

    def test_active_terminal_mode_cancel_is_honestly_unsupported(self):
        self.broker.submit(request())
        self.broker.take_next()
        result = self.broker.submit(CommandRequest("cancel", Type.CANCEL_OPERATION,
                                    Source.FUTURE_MOBILE_REQUEST, {"target_request_id": "mobile-1"}))
        self.assertEqual(result.error_code, "CANCELLATION_UNSUPPORTED")
        self.assertEqual(self.broker.get_operation("mobile-1").state, State.RUNNING)
        self.assertFalse(self.broker.cancellation_event("mobile-1").is_set())

    def test_supported_adapter_must_acknowledge_actual_cancellation(self):
        broker = CommandBroker({"1": ModeCapability("1", True, cancellation_supported=True)})
        broker.submit(request())
        broker.take_next()
        with self.assertRaises(InvalidTransition):
            broker.finish("mobile-1", State.CANCELLED)
        broker.submit(CommandRequest("cancel", Type.CANCEL_OPERATION, Source.PHYSICAL_INPUT,
                                     {"target_request_id": "mobile-1"}))
        self.assertEqual(broker.get_operation("mobile-1").state, State.CANCEL_REQUESTED)
        self.assertEqual(broker.get_status()["terminal_state"], "BUSY")
        self.assertTrue(broker.cancellation_event("mobile-1").is_set())
        broker.finish("mobile-1", State.CANCELLED)
        self.assertEqual(broker.get_status()["terminal_state"], "IDLE")

    def test_cancel_request_can_lose_race_to_completion_or_failure(self):
        for outcome in (State.COMPLETED, State.FAILED):
            broker = CommandBroker({"1": ModeCapability("1", True, cancellation_supported=True)})
            broker.submit(request())
            broker.take_next()
            broker.submit(CommandRequest("cancel", Type.CANCEL_OPERATION, Source.PHYSICAL_INPUT,
                                         {"target_request_id": "mobile-1"}))
            broker.finish("mobile-1", outcome)
            self.assertEqual(broker.get_operation("mobile-1").state, outcome)
            with self.assertRaises(ValueError):
                broker.finish("mobile-1", State.CANCELLED)

    def test_unknown_cancel_and_repeated_terminal_cancel(self):
        cancel = lambda identifier, target: CommandRequest(identifier, Type.CANCEL_OPERATION,
                                  Source.FUTURE_MOBILE_REQUEST, {"target_request_id": target})
        self.assertEqual(self.broker.submit(cancel("missing", "absent")).error_code, "UNKNOWN_OPERATION")
        self.broker.submit(request())
        self.broker.take_next()
        self.broker.finish("mobile-1")
        self.assertEqual(self.broker.submit(cancel("late", "mobile-1")).data["target_state"], "COMPLETED")

    def test_bounded_history_does_not_evict_unexpired_ids(self):
        broker = CommandBroker(self.capabilities, max_pending=1, max_records=2, clock=self.clock)
        broker.submit(request())
        broker.take_next()
        broker.finish("mobile-1")
        broker.submit(request("second"))
        self.assertEqual(broker.submit(request("third")).error_code, "HISTORY_FULL")
        self.assertEqual(broker.submit(request()).state, State.COMPLETED)
        self.clock.now = 301
        self.assertEqual(broker.submit(request()).state, State.PENDING)
        self.assertLessEqual(broker.get_status()["retained_request_count"], 2)

    def test_status_and_capabilities_do_not_claim_hardware_or_authentication(self):
        response = self.broker.submit(CommandRequest("status", Type.GET_STATUS, Source.FUTURE_MOBILE_REQUEST))
        response.data["terminal_state"] = "altered by caller"
        self.assertEqual(self.broker.get_status()["terminal_state"], "IDLE")
        capability = self.broker.submit(CommandRequest("caps", Type.GET_CAPABILITIES,
                                        Source.FUTURE_MOBILE_REQUEST)).data
        self.assertIsNone(capability["modes"][0]["hardware_validated"])
        self.assertIsNone(capability["modes"][0]["dependencies_available"])
        self.assertEqual(capability["authentication"], "NOT_IMPLEMENTED_INTERNAL_ONLY")
        capability["modes"][0]["enabled"] = False
        self.assertTrue(self.broker.get_capabilities()["modes"][0]["enabled"])

    def test_cross_thread_submission_deduplicates_and_execution_is_owner_only(self):
        with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
            results = list(pool.map(lambda _: self.broker.submit(request()), range(40)))
            self.assertTrue(all(result.state == State.PENDING for result in results))
            with self.assertRaises(RuntimeError):
                pool.submit(self.broker.take_next).result()
        self.broker.take_next()
        with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
            statuses = list(pool.map(lambda _: self.broker.get_status(), range(40)))
            self.assertTrue(all(item["active_request_id"] == "mobile-1" for item in statuses))
            with self.assertRaises(RuntimeError):
                pool.submit(self.broker.finish, "mobile-1").result()
        self.broker.finish("mobile-1")
        self.assertEqual(self.broker.get_status()["retained_request_count"], 1)

    def test_shutdown_cleans_pending_without_claiming_active_cancellation(self):
        self.broker.submit(request())
        self.broker.close()
        self.broker.close()
        self.assertEqual(self.broker.get_operation("mobile-1").state, State.CANCELLED)
        self.assertEqual(self.broker.submit(request("new")).error_code, "BROKER_CLOSED")
        self.assertIsNone(self.broker.take_next())
        broker = CommandBroker(self.capabilities)
        broker.submit(request())
        broker.take_next()
        broker.close()
        self.assertEqual(broker.get_status()["terminal_state"], "SHUTTING_DOWN")
        self.assertEqual(broker.get_operation("mobile-1").state, State.CANCEL_REQUESTED)
        broker.finish("mobile-1", State.FAILED, error_code="INTERRUPTED")
        self.assertEqual(broker.get_status()["terminal_state"], "CLOSED")

    def test_work_wait_is_bounded_and_pending_only(self):
        self.assertFalse(self.broker.wait_for_work(0))
        self.broker.submit(request())
        self.assertTrue(self.broker.wait_for_work(.1))
        self.broker.take_next()
        self.assertFalse(self.broker.wait_for_work(0))
        with self.assertRaises(ValueError):
            self.broker.wait_for_work(float("inf"))
