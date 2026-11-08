"""Public error codes never contain exception text or submitted content."""


class GatewayError(Exception):
    def __init__(self, code, status=400):
        self.code, self.status = code, status
        super().__init__(code)


def broker_status(code):
    if code in {"BROKER_CLOSED"}:
        return 503
    if code in {"HISTORY_FULL", "QUEUE_FULL"}:
        return 503
    if code == "UNKNOWN_OPERATION":
        return 404
    if code == "REQUEST_TIMEOUT":
        return 504
    if code in {"TERMINAL_BUSY", "REQUEST_ID_CONFLICT", "PHYSICAL_PRIORITY",
                "CANCELLATION_UNSUPPORTED"}:
        return 409
    return 422
