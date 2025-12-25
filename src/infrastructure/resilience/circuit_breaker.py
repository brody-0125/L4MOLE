
import logging
import threading
import time
from dataclasses import dataclass, field
from enum import Enum
from functools import wraps
from typing import Any, Callable, Optional, TypeVar

logger = logging.getLogger(__name__)

T = TypeVar("T")

class CircuitState(Enum):

    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"

class CircuitBreakerError(Exception):

    def __init__(self, message: str, recovery_time: float):
        super().__init__(message)
        self.recovery_time = recovery_time

@dataclass
class CircuitBreakerConfig:

    failure_threshold: int = 5

    recovery_timeout: float = 30.0

    success_threshold: int = 2

    call_timeout: Optional[float] = None

    expected_exceptions: tuple = field(default_factory=lambda: (Exception,))

@dataclass
class CircuitBreakerStats:

    total_calls: int = 0
    successful_calls: int = 0
    failed_calls: int = 0
    rejected_calls: int = 0
    state_changes: int = 0
    last_failure_time: Optional[float] = None
    last_success_time: Optional[float] = None

    @property
    def failure_rate(self) -> float:
        if self.total_calls == 0:
            return 0.0
        return (self.failed_calls / self.total_calls) * 100

class CircuitBreaker:

    def __init__(
        self,
        name: str,
        config: Optional[CircuitBreakerConfig] = None,
    ) -> None:
        self._name = name
        self._config = config or CircuitBreakerConfig()
        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._success_count = 0
        self._last_failure_time: Optional[float] = None
        self._lock = threading.RLock()
        self._stats = CircuitBreakerStats()

    @property
    def name(self) -> str:
        return self._name

    @property
    def state(self) -> CircuitState:
        with self._lock:
            self._check_state_transition()
            return self._state

    @property
    def stats(self) -> CircuitBreakerStats:
        return self._stats

    @property
    def is_closed(self) -> bool:
        return self.state == CircuitState.CLOSED

    @property
    def is_open(self) -> bool:
        return self.state == CircuitState.OPEN

    def _check_state_transition(self) -> None:
        if self._state == CircuitState.OPEN:
            if self._last_failure_time is not None:
                elapsed = time.time() - self._last_failure_time
                if elapsed >= self._config.recovery_timeout:
                    self._transition_to(CircuitState.HALF_OPEN)

    def _transition_to(self, new_state: CircuitState) -> None:
        old_state = self._state
        self._state = new_state
        self._stats.state_changes += 1

        if new_state == CircuitState.CLOSED:
            self._failure_count = 0
            self._success_count = 0
        elif new_state == CircuitState.HALF_OPEN:
            self._success_count = 0

        logger.info(
            "Circuit breaker '%s': %s -> %s",
            self._name,
            old_state.value,
            new_state.value,
        )

    def _record_success(self) -> None:
        with self._lock:
            self._stats.total_calls += 1
            self._stats.successful_calls += 1
            self._stats.last_success_time = time.time()

            if self._state == CircuitState.HALF_OPEN:
                self._success_count += 1
                if self._success_count >= self._config.success_threshold:
                    self._transition_to(CircuitState.CLOSED)
            elif self._state == CircuitState.CLOSED:
                self._failure_count = 0

    def _record_failure(self, error: Exception) -> None:
        with self._lock:
            self._stats.total_calls += 1
            self._stats.failed_calls += 1
            self._last_failure_time = time.time()
            self._stats.last_failure_time = self._last_failure_time

            if self._state == CircuitState.HALF_OPEN:
                self._transition_to(CircuitState.OPEN)
            elif self._state == CircuitState.CLOSED:
                self._failure_count += 1
                if self._failure_count >= self._config.failure_threshold:
                    self._transition_to(CircuitState.OPEN)
                    logger.warning(
                        "Circuit breaker '%s' opened after %d failures: %s",
                        self._name,
                        self._failure_count,
                        error,
                    )

    def _should_allow_request(self) -> bool:
        with self._lock:
            self._check_state_transition()

            if self._state == CircuitState.CLOSED:
                return True
            elif self._state == CircuitState.HALF_OPEN:
                return True
            else:
                self._stats.rejected_calls += 1
                return False

    def _get_recovery_time(self) -> float:
        if self._last_failure_time is None:
            return 0.0
        elapsed = time.time() - self._last_failure_time
        return max(0.0, self._config.recovery_timeout - elapsed)

    def call(self, func: Callable[[], T]) -> T:
        if not self._should_allow_request():
            recovery_time = self._get_recovery_time()
            raise CircuitBreakerError(
                f"Circuit breaker '{self._name}' is open. "
                f"Recovery in {recovery_time:.1f}s",
                recovery_time=recovery_time,
            )

        try:
            result = func()
            self._record_success()
            return result

        except self._config.expected_exceptions as e:
            self._record_failure(e)
            raise

    def __call__(self, func: Callable) -> Callable:

        @wraps(func)
        def wrapper(*args, **kwargs):
            return self.call(lambda: func(*args, **kwargs))

        return wrapper

    def __enter__(self) -> "CircuitBreaker":
        if not self._should_allow_request():
            recovery_time = self._get_recovery_time()
            raise CircuitBreakerError(
                f"Circuit breaker '{self._name}' is open",
                recovery_time=recovery_time,
            )
        return self

    def __exit__(self, exc_type, exc_val, _exc_tb) -> bool:
        if exc_type is None:
            self._record_success()
        elif issubclass(exc_type, self._config.expected_exceptions):
            self._record_failure(exc_val)
        return False

    def reset(self) -> None:
        with self._lock:
            self._transition_to(CircuitState.CLOSED)
            logger.info("Circuit breaker '%s' manually reset", self._name)

    def force_open(self) -> None:
        with self._lock:
            self._transition_to(CircuitState.OPEN)
            self._last_failure_time = time.time()
            logger.info("Circuit breaker '%s' manually opened", self._name)

class CircuitBreakerRegistry:

    _instance: Optional["CircuitBreakerRegistry"] = None
    _lock = threading.Lock()

    def __new__(cls) -> "CircuitBreakerRegistry":
        with cls._lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
                cls._instance._breakers = {}
                cls._instance._registry_lock = threading.RLock()
            return cls._instance

    def get_or_create(
        self,
        name: str,
        config: Optional[CircuitBreakerConfig] = None,
    ) -> CircuitBreaker:
        with self._registry_lock:
            if name not in self._breakers:
                self._breakers[name] = CircuitBreaker(name, config)
            return self._breakers[name]

    def get(self, name: str) -> Optional[CircuitBreaker]:
        return self._breakers.get(name)

    def get_all_stats(self) -> dict:
        return {
            name: {
                "state": breaker.state.value,
                "total_calls": breaker.stats.total_calls,
                "successful_calls": breaker.stats.successful_calls,
                "failed_calls": breaker.stats.failed_calls,
                "rejected_calls": breaker.stats.rejected_calls,
                "failure_rate": breaker.stats.failure_rate,
            }
            for name, breaker in self._breakers.items()
        }

    def reset_all(self) -> None:
        for breaker in self._breakers.values():
            breaker.reset()

def get_circuit_breaker_registry() -> CircuitBreakerRegistry:
    return CircuitBreakerRegistry()
