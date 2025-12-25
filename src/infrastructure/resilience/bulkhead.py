
import logging
import threading
import time
from dataclasses import dataclass, field
from enum import Enum
from functools import wraps
from typing import Any, Callable, Optional, TypeVar

logger = logging.getLogger(__name__)

T = TypeVar("T")

class BulkheadFullError(Exception):

    def __init__(
        self,
        name: str,
        max_concurrent: int,
        queue_size: int,
        wait_time: Optional[float] = None,
    ) -> None:
        self.name = name
        self.max_concurrent = max_concurrent
        self.queue_size = queue_size
        self.wait_time = wait_time

        if wait_time is not None:
            message = (
                f"Bulkhead '{name}' timed out after {wait_time:.2f}s. "
                f"Max concurrent: {max_concurrent}, queue size: {queue_size}"
            )
        else:
            message = (
                f"Bulkhead '{name}' is full. "
                f"Max concurrent: {max_concurrent}, queue size: {queue_size}"
            )
        super().__init__(message)

class BulkheadState(Enum):

    ACCEPTING = "accepting"
    SATURATED = "saturated"
    REJECTING = "rejecting"

@dataclass
class BulkheadConfig:

    max_concurrent: int = 4
    """Maximum number of concurrent executions."""

    max_wait_time: float = 30.0
    """Maximum time to wait for a slot (seconds). 0 means no waiting."""

    name: str = "default"
    """Name for logging and monitoring."""

@dataclass
class BulkheadStats:

    total_calls: int = 0
    """Total number of calls attempted."""

    successful_calls: int = 0
    """Number of calls that completed successfully."""

    rejected_calls: int = 0
    """Number of calls rejected due to full bulkhead."""

    timed_out_calls: int = 0
    """Number of calls that timed out waiting for a slot."""

    failed_calls: int = 0
    """Number of calls that failed during execution."""

    total_wait_time: float = 0.0
    """Total time spent waiting for slots (seconds)."""

    max_wait_time: float = 0.0
    """Maximum observed wait time (seconds)."""

    _lock: threading.Lock = field(default_factory=threading.Lock)

    @property
    def average_wait_time(self) -> float:
        if self.total_calls == 0:
            return 0.0
        return self.total_wait_time / self.total_calls

    @property
    def rejection_rate(self) -> float:
        if self.total_calls == 0:
            return 0.0
        return (self.rejected_calls + self.timed_out_calls) / self.total_calls

    @property
    def success_rate(self) -> float:
        if self.total_calls == 0:
            return 0.0
        return self.successful_calls / self.total_calls

    def record_success(self, wait_time: float) -> None:
        with self._lock:
            self.total_calls += 1
            self.successful_calls += 1
            self.total_wait_time += wait_time
            self.max_wait_time = max(self.max_wait_time, wait_time)

    def record_failure(self, wait_time: float) -> None:
        with self._lock:
            self.total_calls += 1
            self.failed_calls += 1
            self.total_wait_time += wait_time
            self.max_wait_time = max(self.max_wait_time, wait_time)

    def record_rejection(self) -> None:
        with self._lock:
            self.total_calls += 1
            self.rejected_calls += 1

    def record_timeout(self, wait_time: float) -> None:
        with self._lock:
            self.total_calls += 1
            self.timed_out_calls += 1
            self.total_wait_time += wait_time
            self.max_wait_time = max(self.max_wait_time, wait_time)

    def reset(self) -> None:
        with self._lock:
            self.total_calls = 0
            self.successful_calls = 0
            self.rejected_calls = 0
            self.timed_out_calls = 0
            self.failed_calls = 0
            self.total_wait_time = 0.0
            self.max_wait_time = 0.0

    def to_dict(self) -> dict:
        return {
            "total_calls": self.total_calls,
            "successful_calls": self.successful_calls,
            "rejected_calls": self.rejected_calls,
            "timed_out_calls": self.timed_out_calls,
            "failed_calls": self.failed_calls,
            "average_wait_time": self.average_wait_time,
            "max_wait_time": self.max_wait_time,
            "rejection_rate": self.rejection_rate,
            "success_rate": self.success_rate,
        }

class Bulkhead:

    def __init__(self, config: Optional[BulkheadConfig] = None) -> None:
        self._config = config or BulkheadConfig()
        self._semaphore = threading.Semaphore(self._config.max_concurrent)
        self._active_count = 0
        self._waiting_count = 0
        self._count_lock = threading.Lock()
        self._stats = BulkheadStats()

        logger.debug(
            "Bulkhead '%s' initialized: max_concurrent=%d, max_wait_time=%.1fs",
            self._config.name,
            self._config.max_concurrent,
            self._config.max_wait_time,
        )

    @property
    def name(self) -> str:
        return self._config.name

    @property
    def config(self) -> BulkheadConfig:
        return self._config

    @property
    def stats(self) -> BulkheadStats:
        return self._stats

    @property
    def active_count(self) -> int:
        with self._count_lock:
            return self._active_count

    @property
    def waiting_count(self) -> int:
        with self._count_lock:
            return self._waiting_count

    @property
    def available_slots(self) -> int:
        with self._count_lock:
            return self._config.max_concurrent - self._active_count

    @property
    def state(self) -> BulkheadState:
        with self._count_lock:
            if self._active_count < self._config.max_concurrent:
                return BulkheadState.ACCEPTING
            elif self._waiting_count > 0:
                return BulkheadState.SATURATED
            else:
                return BulkheadState.SATURATED

    def _acquire(self) -> float:
        start_time = time.monotonic()

        with self._count_lock:
            self._waiting_count += 1

        try:
            if self._config.max_wait_time <= 0:
                acquired = self._semaphore.acquire(blocking=False)
                if not acquired:
                    self._stats.record_rejection()
                    raise BulkheadFullError(
                        self._config.name,
                        self._config.max_concurrent,
                        0,
                    )
            else:
                acquired = self._semaphore.acquire(
                    blocking=True,
                    timeout=self._config.max_wait_time,
                )
                if not acquired:
                    wait_time = time.monotonic() - start_time
                    self._stats.record_timeout(wait_time)
                    raise BulkheadFullError(
                        self._config.name,
                        self._config.max_concurrent,
                        0,
                        wait_time=wait_time,
                    )

            wait_time = time.monotonic() - start_time

            with self._count_lock:
                self._active_count += 1

            return wait_time

        finally:
            with self._count_lock:
                self._waiting_count -= 1

    def _release(self) -> None:
        with self._count_lock:
            self._active_count -= 1
        self._semaphore.release()

    def call(self, func: Callable[[], T]) -> T:
        wait_time = self._acquire()

        try:
            result = func()
            self._stats.record_success(wait_time)
            return result
        except Exception:
            self._stats.record_failure(wait_time)
            raise
        finally:
            self._release()

    def __enter__(self) -> "Bulkhead":
        self._current_wait_time = self._acquire()
        return self

    def __exit__(self, exc_type, exc_val, _exc_tb) -> bool:
        if exc_type is None:
            self._stats.record_success(self._current_wait_time)
        else:
            self._stats.record_failure(self._current_wait_time)
        self._release()
        return False

    def decorator(
        self,
        func: Optional[Callable[..., T]] = None,
    ) -> Callable[..., T]:
        def decorator_inner(fn: Callable[..., T]) -> Callable[..., T]:
            @wraps(fn)
            def wrapper(*args: Any, **kwargs: Any) -> T:
                return self.call(lambda: fn(*args, **kwargs))
            return wrapper

        if func is not None:
            return decorator_inner(func)
        return decorator_inner

    def try_acquire(self) -> bool:
        acquired = self._semaphore.acquire(blocking=False)
        if acquired:
            with self._count_lock:
                self._active_count += 1
        return acquired

    def release(self) -> None:
        self._release()

    def reset_stats(self) -> None:
        self._stats.reset()

class BulkheadRegistry:

    _instance: Optional["BulkheadRegistry"] = None
    _lock = threading.Lock()

    def __new__(cls) -> "BulkheadRegistry":
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._bulkheads = {}
                    cls._instance._registry_lock = threading.Lock()
        return cls._instance

    def get_or_create(
        self,
        name: str,
        config: Optional[BulkheadConfig] = None,
    ) -> Bulkhead:
        with self._registry_lock:
            if name not in self._bulkheads:
                cfg = config or BulkheadConfig(name=name)
                if cfg.name != name:
                    cfg = BulkheadConfig(
                        name=name,
                        max_concurrent=cfg.max_concurrent,
                        max_wait_time=cfg.max_wait_time,
                    )
                self._bulkheads[name] = Bulkhead(cfg)
                logger.debug("Created bulkhead: %s", name)
            return self._bulkheads[name]

    def get(self, name: str) -> Optional[Bulkhead]:
        with self._registry_lock:
            return self._bulkheads.get(name)

    def get_all_stats(self) -> dict[str, dict]:
        with self._registry_lock:
            return {
                name: bh.stats.to_dict()
                for name, bh in self._bulkheads.items()
            }

    def reset_all(self) -> None:
        with self._registry_lock:
            for bh in self._bulkheads.values():
                bh.reset_stats()

    def clear(self) -> None:
        with self._registry_lock:
            self._bulkheads.clear()
