import pytest
import asyncio
from unittest.mock import MagicMock, AsyncMock
from app.resilience.circuit_breaker import (
    CircuitBreaker,
    CircuitState,
    CircuitOpenError,
    get_circuit,
    _circuits,
)


class TestCircuitBreakerInitialState:
    def test_initial_state_closed(self):
        cb = CircuitBreaker("test")
        assert cb.state == CircuitState.CLOSED
        assert cb._failure_count == 0
        assert cb._last_failure_time is None
        assert cb._half_open_calls == 0

    def test_custom_params(self):
        cb = CircuitBreaker(
            "test", failure_threshold=3, recovery_timeout=10, half_open_max_calls=2
        )
        assert cb.failure_threshold == 3
        assert cb.recovery_timeout == 10
        assert cb.half_open_max_calls == 2


class TestCircuitBreakerCall:
    @pytest.mark.asyncio
    async def test_call_sync_success(self):
        cb = CircuitBreaker("test")
        fn = MagicMock(return_value="ok")
        result = await cb.call(fn)
        assert result == "ok"
        assert cb._failure_count == 0
        assert cb.state == CircuitState.CLOSED

    @pytest.mark.asyncio
    async def test_call_async_success(self):
        cb = CircuitBreaker("test")
        fn = AsyncMock(return_value="ok")
        result = await cb.call(fn)
        assert result == "ok"

    @pytest.mark.asyncio
    async def test_call_sync_failure(self):
        cb = CircuitBreaker("test", failure_threshold=2)
        fn = MagicMock(side_effect=ValueError("fail"))
        with pytest.raises(ValueError):
            await cb.call(fn)
        assert cb._failure_count == 1
        assert cb._last_failure_time is not None

    @pytest.mark.asyncio
    async def test_call_async_failure(self):
        cb = CircuitBreaker("test", failure_threshold=2)
        fn = AsyncMock(side_effect=ValueError("fail"))
        with pytest.raises(ValueError):
            await cb.call(fn)
        assert cb._failure_count == 1

    @pytest.mark.asyncio
    async def test_circuit_opens_at_threshold(self):
        cb = CircuitBreaker("test", failure_threshold=3)
        fn = MagicMock(side_effect=ValueError("fail"))
        for _ in range(3):
            with pytest.raises(ValueError):
                await cb.call(fn)
        assert cb.state == CircuitState.OPEN
        assert cb._failure_count == 3

    @pytest.mark.asyncio
    async def test_open_circuit_raises_immediately(self):
        cb = CircuitBreaker("test", failure_threshold=1)
        fn = MagicMock(side_effect=ValueError("fail"))
        with pytest.raises(ValueError):
            await cb.call(fn)
        assert cb.state == CircuitState.OPEN
        with pytest.raises(CircuitOpenError):
            await cb.call(fn)

    @pytest.mark.asyncio
    async def test_success_after_failures_resets_counter(self):
        cb = CircuitBreaker("test", failure_threshold=3)
        fail_fn = MagicMock(side_effect=ValueError("fail"))
        with pytest.raises(ValueError):
            await cb.call(fail_fn)
        assert cb._failure_count == 1
        success_fn = MagicMock(return_value="ok")
        result = await cb.call(success_fn)
        assert result == "ok"
        assert cb._failure_count == 0


class TestCircuitBreakerHalfOpen:
    @pytest.mark.asyncio
    async def test_transitions_to_half_open_after_timeout(self):
        cb = CircuitBreaker("test", failure_threshold=1, recovery_timeout=0)
        fn = MagicMock(side_effect=ValueError("fail"))
        with pytest.raises(ValueError):
            await cb.call(fn)
        assert cb._state == CircuitState.OPEN
        await asyncio.sleep(0.01)
        assert cb.state == CircuitState.HALF_OPEN

    @pytest.mark.asyncio
    async def test_half_open_success_closes_circuit(self):
        cb = CircuitBreaker("test", failure_threshold=1, recovery_timeout=0)
        fail_fn = MagicMock(side_effect=ValueError("fail"))
        with pytest.raises(ValueError):
            await cb.call(fail_fn)
        await asyncio.sleep(0.01)
        assert cb.state == CircuitState.HALF_OPEN
        success_fn = MagicMock(return_value="ok")
        result = await cb.call(success_fn)
        assert result == "ok"
        assert cb.state == CircuitState.CLOSED
        assert cb._failure_count == 0

    @pytest.mark.asyncio
    async def test_half_open_failure_reopens(self):
        cb = CircuitBreaker("test", failure_threshold=1, recovery_timeout=0)
        fail_fn = MagicMock(side_effect=ValueError("fail"))
        with pytest.raises(ValueError):
            await cb.call(fail_fn)
        await asyncio.sleep(0.01)
        assert cb.state == CircuitState.HALF_OPEN
        with pytest.raises(ValueError):
            await cb.call(fail_fn)
        assert cb.state == CircuitState.OPEN

    @pytest.mark.asyncio
    async def test_half_open_max_calls_limited(self):
        cb = CircuitBreaker(
            "test", failure_threshold=1, recovery_timeout=0, half_open_max_calls=2
        )
        fail_fn = MagicMock(side_effect=ValueError("fail"))
        with pytest.raises(ValueError):
            await cb.call(fail_fn)
        await asyncio.sleep(0.01)
        success_fn = MagicMock(return_value="ok")
        result1 = await cb.call(success_fn)
        assert result1 == "ok"
        assert cb.state == CircuitState.CLOSED

    @pytest.mark.asyncio
    async def test_half_open_max_calls_exceeded(self):
        cb = CircuitBreaker(
            "test", failure_threshold=2, recovery_timeout=0, half_open_max_calls=1
        )
        fail_fn = MagicMock(side_effect=ValueError("fail"))
        for _ in range(2):
            with pytest.raises(ValueError):
                await cb.call(fail_fn)
        await asyncio.sleep(0.01)
        success_fn = MagicMock(return_value="ok")
        result = await cb.call(success_fn)
        assert result == "ok"
        assert cb.state == CircuitState.CLOSED


class TestCircuitsRegistry:
    def test_get_circuit_singleton(self):
        cb1 = get_circuit("test-singleton")
        cb2 = get_circuit("test-singleton")
        assert cb1 is cb2

    def test_get_circuit_different_names(self):
        cb1 = get_circuit("alpha")
        cb2 = get_circuit("beta")
        assert cb1 is not cb2

    def test_circuits_dict_is_shared(self):
        _circuits.clear()
        cb = get_circuit("shared-test")
        assert "shared-test" in _circuits
        assert _circuits["shared-test"] is cb


class TestCircuitOpenError:
    def test_is_exception_subclass(self):
        assert issubclass(CircuitOpenError, Exception)

    def test_has_message(self):
        err = CircuitOpenError("test message")
        assert str(err) == "test message"
