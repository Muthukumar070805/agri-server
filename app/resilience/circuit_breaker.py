import asyncio
import inspect
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from enum import Enum
from typing import Any

from app.core.logger import get_logger

logger = get_logger(__name__)


class CircuitState(Enum):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


class CircuitBreaker:
    def __init__(
        self,
        name: str,
        failure_threshold: int = 5,
        recovery_timeout: int = 60,
        half_open_max_calls: int = 3,
    ):
        self.name = name
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.half_open_max_calls = half_open_max_calls

        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._last_failure_time: datetime | None = None
        self._opened_at: datetime | None = None
        self._half_open_calls = 0
        self._lock = asyncio.Lock()

    @property
    def state(self) -> CircuitState:
        if (
            self._state == CircuitState.OPEN
            and self._opened_at
            and datetime.now(UTC) - self._opened_at
            > timedelta(seconds=self.recovery_timeout)
        ):
            return CircuitState.HALF_OPEN
        return self._state

    def snapshot(self) -> dict[str, Any]:
        """Return public snapshot of circuit breaker state."""
        return {
            "name": self.name,
            "state": self.state.value,
            "failures": self._failure_count,
            "last_failure": self._last_failure_time.isoformat()
            if self._last_failure_time
            else None,
            "opened_at": self._opened_at.isoformat() if self._opened_at else None,
            "half_open_calls": self._half_open_calls,
        }

    async def call(self, func: Callable, *args, **kwargs) -> Any:
        is_probe = False
        async with self._lock:
            current_state = self.state

            if current_state == CircuitState.OPEN:
                raise CircuitOpenError(f"Circuit {self.name} is OPEN")

            if current_state == CircuitState.HALF_OPEN:
                if self._half_open_calls >= self.half_open_max_calls:
                    raise CircuitOpenError(
                        f"Circuit {self.name} is HALF_OPEN (max calls reached)"
                    )
                self._state = CircuitState.HALF_OPEN
                self._half_open_calls += 1
                is_probe = True

        completed = False
        try:
            result = func(*args, **kwargs)
            if inspect.isawaitable(result):
                result = await result

            await self._on_success()
            completed = True
            return result

        except Exception:
            await self._on_failure()
            completed = True
            raise
        finally:
            if not completed and is_probe:
                async with self._lock:
                    if self._state == CircuitState.HALF_OPEN:
                        self._half_open_calls = max(0, self._half_open_calls - 1)

    async def _on_success(self):
        async with self._lock:
            self._failure_count = 0
            self._half_open_calls = 0
            if self._state != CircuitState.CLOSED:
                self._state = CircuitState.CLOSED
                self._opened_at = None
                logger.info(f"Circuit {self.name} CLOSED (recovered)")

    async def _on_failure(self):
        async with self._lock:
            self._failure_count += 1
            self._last_failure_time = datetime.now(UTC)

            if self._state == CircuitState.HALF_OPEN:
                self._state = CircuitState.OPEN
                self._opened_at = datetime.now(UTC)
                self._half_open_calls = 0
                logger.warning(f"Circuit {self.name} OPEN (half-open test failed)")
            elif self._failure_count >= self.failure_threshold:
                self._state = CircuitState.OPEN
                self._opened_at = datetime.now(UTC)
                self._half_open_calls = 0
                logger.warning(
                    "Circuit %s OPEN (threshold: %s failures)",
                    self.name,
                    self._failure_count,
                )


class CircuitOpenError(Exception):
    pass


_circuits: dict[str, CircuitBreaker] = {}


def get_circuit(name: str) -> CircuitBreaker:
    if name not in _circuits:
        _circuits[name] = CircuitBreaker(name=name)
    return _circuits[name]
