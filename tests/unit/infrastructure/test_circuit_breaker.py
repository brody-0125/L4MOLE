
import time
import threading
import pytest

from src.infrastructure.resilience.circuit_breaker import (
    CircuitBreaker,
    CircuitBreakerConfig,
    CircuitBreakerError,
    CircuitBreakerRegistry,
    CircuitState,
    get_circuit_breaker_registry,
)

class TestCircuitBreakerStates:

    def test_initial_state_is_closed(self):
        breaker = CircuitBreaker("test")
        assert breaker.state == CircuitState.CLOSED
        assert breaker.is_closed

    def test_successful_calls_keep_circuit_closed(self):
        breaker = CircuitBreaker("test")

        for _ in range(10):
            result = breaker.call(lambda: "success")
            assert result == "success"

        assert breaker.state == CircuitState.CLOSED
        assert breaker.stats.successful_calls == 10
        assert breaker.stats.failed_calls == 0

    def test_failures_open_circuit_after_threshold(self):
        config = CircuitBreakerConfig(failure_threshold=3)
        breaker = CircuitBreaker("test", config)

        for i in range(2):
            with pytest.raises(ValueError):
                breaker.call(lambda: (_ for _ in ()).throw(ValueError("fail")))

        assert breaker.state == CircuitState.CLOSED

        with pytest.raises(ValueError):
            breaker.call(lambda: (_ for _ in ()).throw(ValueError("fail")))

        assert breaker.state == CircuitState.OPEN
        assert breaker.is_open

    def test_open_circuit_rejects_requests(self):
        config = CircuitBreakerConfig(failure_threshold=1, recovery_timeout=60.0)
        breaker = CircuitBreaker("test", config)

        with pytest.raises(ValueError):
            breaker.call(lambda: (_ for _ in ()).throw(ValueError("fail")))

        assert breaker.state == CircuitState.OPEN

        with pytest.raises(CircuitBreakerError) as exc_info:
            breaker.call(lambda: "should not execute")

        assert "open" in str(exc_info.value).lower()
        assert breaker.stats.rejected_calls == 1

    def test_circuit_transitions_to_half_open_after_timeout(self):
        config = CircuitBreakerConfig(
            failure_threshold=1,
            recovery_timeout=0.1,
        )
        breaker = CircuitBreaker("test", config)

        with pytest.raises(ValueError):
            breaker.call(lambda: (_ for _ in ()).throw(ValueError("fail")))

        assert breaker.state == CircuitState.OPEN

        time.sleep(0.15)

        assert breaker.state == CircuitState.HALF_OPEN

    def test_half_open_success_closes_circuit(self):
        config = CircuitBreakerConfig(
            failure_threshold=1,
            recovery_timeout=0.1,
            success_threshold=1,
        )
        breaker = CircuitBreaker("test", config)

        with pytest.raises(ValueError):
            breaker.call(lambda: (_ for _ in ()).throw(ValueError("fail")))

        time.sleep(0.15)
        assert breaker.state == CircuitState.HALF_OPEN

        result = breaker.call(lambda: "success")
        assert result == "success"
        assert breaker.state == CircuitState.CLOSED

    def test_half_open_failure_reopens_circuit(self):
        config = CircuitBreakerConfig(
            failure_threshold=1,
            recovery_timeout=0.1,
        )
        breaker = CircuitBreaker("test", config)

        with pytest.raises(ValueError):
            breaker.call(lambda: (_ for _ in ()).throw(ValueError("fail")))

        time.sleep(0.15)
        assert breaker.state == CircuitState.HALF_OPEN

        with pytest.raises(ValueError):
            breaker.call(lambda: (_ for _ in ()).throw(ValueError("fail again")))

        assert breaker.state == CircuitState.OPEN

    def test_success_threshold_for_closing(self):
        config = CircuitBreakerConfig(
            failure_threshold=1,
            recovery_timeout=0.1,
            success_threshold=3,
        )
        breaker = CircuitBreaker("test", config)

        with pytest.raises(ValueError):
            breaker.call(lambda: (_ for _ in ()).throw(ValueError("fail")))

        time.sleep(0.15)
        assert breaker.state == CircuitState.HALF_OPEN

        for _ in range(2):
            breaker.call(lambda: "success")
            assert breaker.state == CircuitState.HALF_OPEN

        breaker.call(lambda: "success")
        assert breaker.state == CircuitState.CLOSED

class TestCircuitBreakerDecorator:

    def test_decorator_wraps_function(self):
        breaker = CircuitBreaker("test")

        @breaker
        def my_function(x, y):
            return x + y

        result = my_function(2, 3)
        assert result == 5
        assert breaker.stats.successful_calls == 1

    def test_decorator_tracks_failures(self):
        config = CircuitBreakerConfig(failure_threshold=2)
        breaker = CircuitBreaker("test", config)

        @breaker
        def failing_function():
            raise RuntimeError("fail")

        with pytest.raises(RuntimeError):
            failing_function()

        assert breaker.stats.failed_calls == 1
        assert breaker.state == CircuitState.CLOSED

        with pytest.raises(RuntimeError):
            failing_function()

        assert breaker.stats.failed_calls == 2
        assert breaker.state == CircuitState.OPEN

class TestCircuitBreakerContextManager:

    def test_context_manager_success(self):
        breaker = CircuitBreaker("test")

        with breaker:
            result = "success"

        assert result == "success"
        assert breaker.stats.successful_calls == 1

    def test_context_manager_failure(self):
        config = CircuitBreakerConfig(failure_threshold=1)
        breaker = CircuitBreaker("test", config)

        with pytest.raises(ValueError):
            with breaker:
                raise ValueError("fail")

        assert breaker.stats.failed_calls == 1
        assert breaker.state == CircuitState.OPEN

    def test_context_manager_rejects_when_open(self):
        config = CircuitBreakerConfig(failure_threshold=1, recovery_timeout=60.0)
        breaker = CircuitBreaker("test", config)

        with pytest.raises(ValueError):
            with breaker:
                raise ValueError("fail")

        with pytest.raises(CircuitBreakerError):
            with breaker:
                pass

class TestCircuitBreakerStats:

    def test_stats_tracking(self):
        config = CircuitBreakerConfig(failure_threshold=3)
        breaker = CircuitBreaker("test", config)

        for _ in range(5):
            breaker.call(lambda: "ok")

        for _ in range(2):
            try:
                breaker.call(lambda: (_ for _ in ()).throw(ValueError()))
            except ValueError:
                pass

        stats = breaker.stats
        assert stats.total_calls == 7
        assert stats.successful_calls == 5
        assert stats.failed_calls == 2
        assert stats.rejected_calls == 0

    def test_failure_rate_calculation(self):
        config = CircuitBreakerConfig(failure_threshold=10)
        breaker = CircuitBreaker("test", config)

        for _ in range(8):
            breaker.call(lambda: "ok")
        for _ in range(2):
            try:
                breaker.call(lambda: (_ for _ in ()).throw(ValueError()))
            except ValueError:
                pass

        assert breaker.stats.failure_rate == 20.0

class TestCircuitBreakerManualControl:

    def test_manual_reset(self):
        config = CircuitBreakerConfig(failure_threshold=1, recovery_timeout=60.0)
        breaker = CircuitBreaker("test", config)

        with pytest.raises(ValueError):
            breaker.call(lambda: (_ for _ in ()).throw(ValueError()))

        assert breaker.state == CircuitState.OPEN

        breaker.reset()
        assert breaker.state == CircuitState.CLOSED

    def test_force_open(self):
        breaker = CircuitBreaker("test")
        assert breaker.state == CircuitState.CLOSED

        breaker.force_open()
        assert breaker.state == CircuitState.OPEN

class TestCircuitBreakerThreadSafety:

    def test_concurrent_calls(self):
        config = CircuitBreakerConfig(failure_threshold=100)
        breaker = CircuitBreaker("test", config)

        call_count = 0
        lock = threading.Lock()

        def increment():
            nonlocal call_count
            with lock:
                call_count += 1
            return call_count

        threads = []
        for _ in range(50):
            t = threading.Thread(target=lambda: breaker.call(increment))
            threads.append(t)
            t.start()

        for t in threads:
            t.join()

        assert call_count == 50
        assert breaker.stats.successful_calls == 50

class TestCircuitBreakerRegistry:

    def test_get_or_create(self):
        registry = CircuitBreakerRegistry()

        breaker1 = registry.get_or_create("service1")
        breaker2 = registry.get_or_create("service2")

        assert breaker1.name == "service1"
        assert breaker2.name == "service2"
        assert breaker1 is not breaker2

    def test_get_or_create_returns_same_instance(self):
        registry = CircuitBreakerRegistry()

        breaker1 = registry.get_or_create("service")
        breaker2 = registry.get_or_create("service")

        assert breaker1 is breaker2

    def test_get_all_stats(self):
        registry = CircuitBreakerRegistry()

        breaker1 = registry.get_or_create("s1")
        breaker2 = registry.get_or_create("s2")

        breaker1.call(lambda: "ok")
        breaker2.call(lambda: "ok")
        breaker2.call(lambda: "ok")

        stats = registry.get_all_stats()

        assert "s1" in stats
        assert "s2" in stats
        assert stats["s1"]["successful_calls"] == 1
        assert stats["s2"]["successful_calls"] == 2

    def test_reset_all(self):
        config = CircuitBreakerConfig(failure_threshold=1, recovery_timeout=60.0)
        registry = CircuitBreakerRegistry()

        breaker1 = registry.get_or_create("s1", config)
        breaker2 = registry.get_or_create("s2", config)

        breaker1.force_open()
        breaker2.force_open()

        assert breaker1.state == CircuitState.OPEN
        assert breaker2.state == CircuitState.OPEN

        registry.reset_all()

        assert breaker1.state == CircuitState.CLOSED
        assert breaker2.state == CircuitState.CLOSED

class TestCircuitBreakerError:

    def test_error_includes_recovery_time(self):
        config = CircuitBreakerConfig(
            failure_threshold=1,
            recovery_timeout=30.0,
        )
        breaker = CircuitBreaker("test", config)

        with pytest.raises(ValueError):
            breaker.call(lambda: (_ for _ in ()).throw(ValueError()))

        with pytest.raises(CircuitBreakerError) as exc_info:
            breaker.call(lambda: "should not run")

        assert exc_info.value.recovery_time > 0
        assert exc_info.value.recovery_time <= 30.0
