"""Process-wide conservative pacing for managed Kite REST and recovery work."""

from collections.abc import Callable
from functools import wraps
from threading import Lock, RLock
from time import monotonic, sleep
from typing import ParamSpec, TypeVar

P = ParamSpec("P")
T = TypeVar("T")


class RequestCoordinator:
    """Serialize request starts, including retries, with a shared cooldown.

    The 0.4 second interval is an application policy, not a broker entitlement.
    Blocking I/O must run off the event loop. Coordination is process-local.
    """

    def __init__(
        self,
        *,
        clock: Callable[[], float] = monotonic,
        sleeper: Callable[[float], None] = sleep,
    ) -> None:
        self._clock = clock
        self._sleep = sleeper
        self._lock = RLock()
        self._next = 0.0

    def call(self, operation: Callable[[], T]) -> T:
        with self._lock:
            delay = self._next - self._clock()
            while delay > 0:
                self._sleep(delay)
                delay = self._next - self._clock()
            self._next = self._clock() + 0.4
            return operation()

    def defer(self, seconds: float) -> None:
        with self._lock:
            self._next = max(self._next, self._clock() + seconds)


managed_rest = RequestCoordinator()
_recovery_lock = Lock()


class RecoveryBusyError(RuntimeError):
    """Another managed recovery is active; caller must retry later."""


def single_recovery(operation: Callable[P, T]) -> Callable[P, T]:
    @wraps(operation)
    def guarded(*args: P.args, **kwargs: P.kwargs) -> T:
        if not _recovery_lock.acquire(blocking=False):
            raise RecoveryBusyError(
                "A managed recovery is already running; retry later."
            )
        try:
            return operation(*args, **kwargs)
        finally:
            _recovery_lock.release()

    return guarded
