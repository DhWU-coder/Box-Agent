"""Request-scoped ACP bookkeeping without a connection-long payload archive."""

from typing import Any

from acp.task.state import IncomingMessage, InMemoryMessageStateStore


class RequestStateStore(InMemoryMessageStateStore):
    """Keep the SDK's outgoing reply correlation, not its incoming history.

    The dispatcher owns each incoming record until its request task settles.
    No connection-owned reference is needed, including when cancellation skips
    the SDK's complete/fail callbacks. Conversation state lives in BoxACPAgent
    and SessionLog; these records are not used to restore or route sessions.
    """

    def begin_incoming(self, method: str, params: Any) -> IncomingMessage:
        return IncomingMessage(method=method, params=params)

    def complete_incoming(self, record: IncomingMessage, result: Any) -> None:
        # Connection sends the response before the dispatcher invokes this hook.
        record.status = "completed"
        self._release_payloads(record)

    def fail_incoming(self, record: IncomingMessage, error: Any) -> None:
        # Error delivery/logging belongs to Connection and TaskSupervisor. Keeping
        # the exception here would also retain its traceback and request locals.
        record.status = "failed"
        self._release_payloads(record)

    @staticmethod
    def _release_payloads(record: IncomingMessage) -> None:
        record.params = None
        record.result = None
        record.error = None
