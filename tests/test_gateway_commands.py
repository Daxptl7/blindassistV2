import unittest

from gateway.errors import GatewayError
from gateway.ipc_client import IpcClient
from gateway.operation_state import OperationState
from gateway_support import GatewayFixture


class CommandTests(GatewayFixture, unittest.TestCase):
    def test_acceptance_execution_completion_and_duplicate_after_gateway_restart(self):
        self.assertEqual(self.submit()["state"], "PENDING")
        self.assertEqual(self.submit()["state"], "PENDING")
        request = self.broker.take_next()
        self.assertEqual(request.request_id, f"gw:{self.principal}:request-1")
        self.assertIsNone(self.broker.take_next())
        self.broker.finish(request.request_id)
        self.ipc = IpcClient(self.settings)
        self.assertEqual(self.submit()["state"], "COMPLETED")
        self.assertIsNone(self.broker.take_next())
        self.assertEqual(self.ipc.request("OPERATION", self.principal, {"request_id": "request-1"})["request_id"], "request-1")

    def test_conflict_busy_disabled_and_unknown_modes(self):
        self.submit()
        self.assertEqual(self.submit(mode="2")["error_code"], "REQUEST_ID_CONFLICT")
        request = self.broker.take_next()
        self.assertEqual(self.submit("busy")["error_code"], "TERMINAL_BUSY")
        self.broker.finish(request.request_id)
        self.assertEqual(self.submit("disabled", "9")["error_code"], "MODE_DISABLED")
        self.assertEqual(self.submit("unknown", "7")["error_code"], "UNKNOWN_MODE")

    def cancel(self, identifier="cancel-1", target="request-1"):
        return self.submit(identifier, command_type="CANCEL_OPERATION", parameters={"target_request_id": target})

    def test_pending_cancel_forwarded_and_never_executed(self):
        self.submit()
        result = self.cancel()
        self.assertEqual(result["state"], "COMPLETED")
        self.assertEqual(result["data"], {"target_request_id": "request-1", "target_state": "CANCELLED"})
        self.assertIsNone(self.broker.take_next())

    def test_active_cancel_is_honestly_unsupported(self):
        self.submit()
        request = self.broker.take_next()
        result = self.cancel()
        self.assertEqual(result["error_code"], "CANCELLATION_UNSUPPORTED")
        self.assertEqual(self.broker.get_operation(request.request_id).state, OperationState.RUNNING)
        self.broker.finish(request.request_id)

    def test_other_principal_cannot_query_or_cancel_and_ids_are_redacted(self):
        self.submit()
        request = self.broker.take_next()
        stranger = "0" * 16 if self.principal != "0" * 16 else "1" * 16
        with self.assertRaises(GatewayError) as error:
            self.ipc.request("OPERATION", stranger, {"request_id": "request-1"})
        self.assertEqual(error.exception.code, "UNKNOWN_OPERATION")
        status = self.ipc.request("STATUS", stranger)
        self.assertIsNone(status["active_request_id"])
        result = self.ipc.request("SUBMIT", stranger, {"request_id": "cancel", "command_type": "CANCEL_OPERATION",
                                                       "parameters": {"target_request_id": "request-1"}})
        self.assertEqual(result["error_code"], "UNKNOWN_OPERATION")
        self.broker.finish(request.request_id)

    def test_failed_handler_has_no_private_result(self):
        self.submit()
        request = self.broker.take_next()
        self.broker.finish(request.request_id, OperationState.FAILED, error_code="MODE_EXECUTION_FAILED")
        result = self.ipc.request("OPERATION", self.principal, {"request_id": "request-1"})
        self.assertEqual(result["state"], "FAILED")
        self.assertEqual(result["data"], {})

    def test_closed_terminal_unavailable(self):
        self.broker.close()
        with self.assertRaises(GatewayError) as error:
            self.ipc.request("STATUS", self.principal)
        self.assertEqual(error.exception.status, 503)


if __name__ == "__main__":
    unittest.main()
