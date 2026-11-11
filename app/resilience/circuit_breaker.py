import asyncio
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

    async def call(self, func: Callable, *args, **kwargs) -> Any:
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

        try:
            result = func(*args, **kwargs)
            if asyncio.iscoroutine(result):
                result = await result

            await self._on_success()
            return result

        except Exception:
            await self._on_failure()
            raise

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
