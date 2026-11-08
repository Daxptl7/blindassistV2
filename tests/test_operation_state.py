import unittest

from gateway.command_models import (CommandRequest, CommandSource, CommandType,
                                    CommandValidationError)
from gateway.operation_state import (InvalidTransition, OperationState as State,
                                     TERMINAL_STATES, transition)


class OperationStateTests(unittest.TestCase):
    def test_all_required_transitions(self):
        paths = {
            State.IDLE: [State.PENDING],
            State.PENDING: [State.RUNNING, State.REJECTED, State.CANCELLED],
            State.RUNNING: [State.COMPLETED, State.FAILED, State.CANCEL_REQUESTED],
            State.CANCEL_REQUESTED: [State.CANCELLED, State.COMPLETED, State.FAILED],
        }
        for before, targets in paths.items():
            for after in targets:
                with self.subTest(before=before, after=after):
                    self.assertEqual(transition(before, after), after)

    def test_terminal_states_cannot_be_overwritten(self):
        for before in TERMINAL_STATES:
            for after in State:
                with self.assertRaises(InvalidTransition):
                    transition(before, after)

    def test_acceptance_and_cancellation_request_are_not_completion(self):
        self.assertNotIn(State.PENDING, TERMINAL_STATES)
        self.assertNotIn(State.CANCEL_REQUESTED, TERMINAL_STATES)
        with self.assertRaises(InvalidTransition):
            transition(State.RUNNING, State.CANCELLED)
        with self.assertRaises(InvalidTransition):
            transition(State.PENDING, State.COMPLETED)
        with self.assertRaises(InvalidTransition):
            transition("RUNNING", State.COMPLETED)


class CommandModelTests(unittest.TestCase):
    def test_request_snapshots_and_freezes_parameters(self):
        parameters = {"mode": "1"}
        request = CommandRequest("request-1", CommandType.START_MODE,
                                 CommandSource.FUTURE_MOBILE_REQUEST, parameters)
        parameters["mode"] = "6"
        self.assertEqual(request.parameters["mode"], "1")
        with self.assertRaises(TypeError):
            request.parameters["mode"] = "6"

    def test_invalid_commands_sources_and_sensitive_parameters_are_rejected(self):
        examples = [
            ("bad id", CommandType.GET_STATUS, CommandSource.PHYSICAL_INPUT, {}),
            ("id", "SHELL", CommandSource.PHYSICAL_INPUT, {}),
            ("id", CommandType.GET_STATUS, "phone", {}),
            ("id", CommandType.GET_STATUS, CommandSource.PHYSICAL_INPUT, {"text": "PRIVATE_SENTINEL"}),
            ("id", CommandType.START_MODE, CommandSource.PHYSICAL_INPUT, {"mode": 1}),
            ("id", CommandType.START_MODE, CommandSource.PHYSICAL_INPUT, {"mode": "1", "allow_cloud": True}),
            ("id", CommandType.CANCEL_OPERATION, CommandSource.PHYSICAL_INPUT, {"target_request_id": ""}),
        ]
        for args in examples:
            with self.subTest(args=args), self.assertRaises(CommandValidationError) as caught:
                CommandRequest(*args)
            self.assertNotIn("PRIVATE_SENTINEL", str(caught.exception))
