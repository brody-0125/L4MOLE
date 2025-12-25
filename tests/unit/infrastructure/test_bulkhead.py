
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

import pytest

from src.infrastructure.resilience.bulkhead import (
    Bulkhead,
    BulkheadConfig,
    BulkheadFullError,
    BulkheadRegistry,
    BulkheadState,
    BulkheadStats,
)

class TestBulkheadBasics:

    def test_default_config(self):
        bulkhead = Bulkhead()
        assert bulkhead.config.max_concurrent == 4
        assert bulkhead.config.max_wait_time == 30.0

    def test_custom_config(self):
        config = BulkheadConfig(
            name="test",
            max_concurrent=2,
            max_wait_time=5.0,
        )
        bulkhead = Bulkhead(config)
        assert bulkhead.name == "test"
        assert bulkhead.config.max_concurrent == 2
        assert bulkhead.config.max_wait_time == 5.0

    def test_successful_call(self):
        bulkhead = Bulkhead(BulkheadConfig(max_concurrent=2))
        result = bulkhead.call(lambda: 42)
        assert result == 42

    def test_exception_propagation(self):
        bulkhead = Bulkhead()

        def failing_func():
            raise ValueError("test error")

        with pytest.raises(ValueError, match="test error"):
            bulkhead.call(failing_func)

    def test_available_slots(self):
        bulkhead = Bulkhead(BulkheadConfig(max_concurrent=2))
        assert bulkhead.available_slots == 2
        assert bulkhead.active_count == 0

class TestBulkheadConcurrency:

    def test_limits_concurrent_calls(self):
        max_concurrent = 2
        bulkhead = Bulkhead(BulkheadConfig(
            max_concurrent=max_concurrent,
            max_wait_time=10.0,
        ))

        active_count_during_execution = []
        lock = threading.Lock()

        def slow_task():
            with lock:
                active_count_during_execution.append(bulkhead.active_count)
            time.sleep(0.1)
            return True

        with ThreadPoolExecutor(max_workers=5) as executor:
            futures = [executor.submit(bulkhead.call, slow_task) for _ in range(5)]
            for future in as_completed(futures):
                future.result()

        assert all(c <= max_concurrent for c in active_count_during_execution)

    def test_concurrent_calls_complete(self):
        bulkhead = Bulkhead(BulkheadConfig(
            max_concurrent=2,
            max_wait_time=10.0,
        ))

        results = []
        lock = threading.Lock()

        def task(n):
            time.sleep(0.05)
            with lock:
                results.append(n)
            return n

        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = [
                executor.submit(bulkhead.call, lambda n=i: task(n))
                for i in range(10)
            ]
            for future in as_completed(futures):
                future.result()

        assert len(results) == 10
        assert set(results) == set(range(10))

class TestBulkheadTimeout:

    def test_no_wait_rejects_immediately(self):
        bulkhead = Bulkhead(BulkheadConfig(
            max_concurrent=1,
            max_wait_time=0,
        ))

        started = threading.Event()
        can_finish = threading.Event()

        def blocking_task():
            started.set()
            can_finish.wait(timeout=5.0)
            return True

        executor = ThreadPoolExecutor(max_workers=2)
        future1 = executor.submit(bulkhead.call, blocking_task)
        started.wait(timeout=1.0)

        with pytest.raises(BulkheadFullError):
            bulkhead.call(lambda: True)

        can_finish.set()
        future1.result()
        executor.shutdown(wait=True)

    def test_wait_timeout_raises_error(self):
        bulkhead = Bulkhead(BulkheadConfig(
            max_concurrent=1,
            max_wait_time=0.1,
        ))

        started = threading.Event()
        can_finish = threading.Event()

        def blocking_task():
            started.set()
            can_finish.wait(timeout=5.0)
            return True

        executor = ThreadPoolExecutor(max_workers=2)
        future1 = executor.submit(bulkhead.call, blocking_task)
        started.wait(timeout=1.0)

        start_time = time.monotonic()
        with pytest.raises(BulkheadFullError) as exc_info:
            bulkhead.call(lambda: True)
        elapsed = time.monotonic() - start_time

        assert exc_info.value.wait_time is not None
        assert elapsed >= 0.1
        assert elapsed < 0.5

        can_finish.set()
        future1.result()
        executor.shutdown(wait=True)

class TestBulkheadContextManager:

    def test_context_manager_success(self):
        bulkhead = Bulkhead(BulkheadConfig(max_concurrent=2))

        with bulkhead:
            result = 42

        assert result == 42
        assert bulkhead.stats.successful_calls == 1

    def test_context_manager_exception(self):
        bulkhead = Bulkhead(BulkheadConfig(max_concurrent=2))

        with pytest.raises(ValueError):
            with bulkhead:
                raise ValueError("test")

        assert bulkhead.stats.failed_calls == 1

    def test_context_manager_releases_slot(self):
        bulkhead = Bulkhead(BulkheadConfig(max_concurrent=1))

        try:
            with bulkhead:
                raise ValueError("test")
        except ValueError:
            pass

        assert bulkhead.available_slots == 1

class TestBulkheadDecorator:

    def test_decorator_wraps_function(self):
        bulkhead = Bulkhead()

        @bulkhead.decorator
        def my_func(x, y):
            return x + y

        result = my_func(2, 3)
        assert result == 5

    def test_decorator_tracks_calls(self):
        bulkhead = Bulkhead()

        @bulkhead.decorator
        def my_func():
            return True

        my_func()
        my_func()

        assert bulkhead.stats.successful_calls == 2

class TestBulkheadStats:

    def test_stats_initial_values(self):
        stats = BulkheadStats()
        assert stats.total_calls == 0
        assert stats.successful_calls == 0
        assert stats.rejected_calls == 0
        assert stats.timed_out_calls == 0
        assert stats.failed_calls == 0

    def test_stats_success_tracking(self):
        bulkhead = Bulkhead()
        bulkhead.call(lambda: True)
        bulkhead.call(lambda: True)

        assert bulkhead.stats.total_calls == 2
        assert bulkhead.stats.successful_calls == 2
        assert bulkhead.stats.success_rate == 1.0

    def test_stats_failure_tracking(self):
        bulkhead = Bulkhead()

        for _ in range(3):
            try:
                bulkhead.call(lambda: 1 / 0)
            except ZeroDivisionError:
                pass

        assert bulkhead.stats.total_calls == 3
        assert bulkhead.stats.failed_calls == 3
        assert bulkhead.stats.success_rate == 0.0

    def test_stats_wait_time_tracking(self):
        bulkhead = Bulkhead(BulkheadConfig(
            max_concurrent=1,
            max_wait_time=10.0,
        ))

        started = threading.Event()
        can_finish = threading.Event()

        def blocking_task():
            started.set()
            time.sleep(0.1)
            return True

        def waiting_task():
            return True

        with ThreadPoolExecutor(max_workers=3) as executor:
            future1 = executor.submit(bulkhead.call, blocking_task)
            started.wait(timeout=1.0)
            future2 = executor.submit(bulkhead.call, waiting_task)

            future1.result()
            future2.result()

        assert bulkhead.stats.total_calls == 2
        assert bulkhead.stats.max_wait_time > 0

    def test_stats_reset(self):
        bulkhead = Bulkhead()
        bulkhead.call(lambda: True)

        bulkhead.reset_stats()

        assert bulkhead.stats.total_calls == 0

    def test_stats_to_dict(self):
        bulkhead = Bulkhead()
        bulkhead.call(lambda: True)

        stats_dict = bulkhead.stats.to_dict()

        assert "total_calls" in stats_dict
        assert "successful_calls" in stats_dict
        assert "success_rate" in stats_dict
        assert stats_dict["total_calls"] == 1

class TestBulkheadState:

    def test_initial_state_accepting(self):
        bulkhead = Bulkhead(BulkheadConfig(max_concurrent=2))
        assert bulkhead.state == BulkheadState.ACCEPTING

    def test_state_saturated_when_full(self):
        bulkhead = Bulkhead(BulkheadConfig(
            max_concurrent=1,
            max_wait_time=10.0,
        ))

        started = threading.Event()
        can_finish = threading.Event()

        def blocking_task():
            started.set()
            can_finish.wait(timeout=5.0)

        executor = ThreadPoolExecutor(max_workers=1)
        future = executor.submit(bulkhead.call, blocking_task)
        started.wait(timeout=1.0)

        assert bulkhead.state == BulkheadState.SATURATED
        assert bulkhead.active_count == 1

        can_finish.set()
        future.result()
        executor.shutdown(wait=True)

class TestBulkheadRegistry:

    def setup_method(self):
        BulkheadRegistry().clear()

    def test_get_or_create(self):
        registry = BulkheadRegistry()
        bulkhead = registry.get_or_create("test")
        assert bulkhead is not None
        assert bulkhead.name == "test"

    def test_get_or_create_returns_same_instance(self):
        registry = BulkheadRegistry()
        b1 = registry.get_or_create("test")
        b2 = registry.get_or_create("test")
        assert b1 is b2

    def test_get_returns_none_if_not_exists(self):
        registry = BulkheadRegistry()
        assert registry.get("nonexistent") is None

    def test_get_all_stats(self):
        registry = BulkheadRegistry()
        b1 = registry.get_or_create("test1")
        b2 = registry.get_or_create("test2")

        b1.call(lambda: True)
        b2.call(lambda: True)

        stats = registry.get_all_stats()
        assert "test1" in stats
        assert "test2" in stats
        assert stats["test1"]["total_calls"] == 1

    def test_reset_all(self):
        registry = BulkheadRegistry()
        b1 = registry.get_or_create("test1")
        b1.call(lambda: True)

        registry.reset_all()

        assert b1.stats.total_calls == 0

class TestBulkheadThreadSafety:

    def test_concurrent_calls_are_thread_safe(self):
        bulkhead = Bulkhead(BulkheadConfig(
            max_concurrent=4,
            max_wait_time=30.0,
        ))

        num_calls = 100
        results = []
        lock = threading.Lock()

        def task(n):
            time.sleep(0.01)
            with lock:
                results.append(n)
            return n

        with ThreadPoolExecutor(max_workers=20) as executor:
            futures = [
                executor.submit(bulkhead.call, lambda n=i: task(n))
                for i in range(num_calls)
            ]
            for future in as_completed(futures):
                future.result()

        assert len(results) == num_calls
        assert bulkhead.stats.total_calls == num_calls
        assert bulkhead.stats.successful_calls == num_calls
        assert bulkhead.active_count == 0

class TestBulkheadManualControl:

    def test_try_acquire_success(self):
        bulkhead = Bulkhead(BulkheadConfig(max_concurrent=2))

        acquired = bulkhead.try_acquire()
        assert acquired is True
        assert bulkhead.active_count == 1

        bulkhead.release()
        assert bulkhead.active_count == 0

    def test_try_acquire_fails_when_full(self):
        bulkhead = Bulkhead(BulkheadConfig(max_concurrent=1))

        assert bulkhead.try_acquire() is True
        assert bulkhead.try_acquire() is False

        bulkhead.release()
