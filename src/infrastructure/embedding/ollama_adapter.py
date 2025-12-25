
import logging
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Callable, List, Optional, Tuple

from ...domain.ports.embedding_port import EmbeddingPort
from ...domain.value_objects.embedding_vector import EmbeddingVector
from ..resilience.bulkhead import Bulkhead, BulkheadConfig, BulkheadFullError
from ..resilience.circuit_breaker import (
    CircuitBreaker,
    CircuitBreakerConfig,
    CircuitBreakerError,
)

logger = logging.getLogger(__name__)

class OllamaEmbeddingAdapter(EmbeddingPort):

    DEFAULT_MODEL = "nomic-embed-text"
    DEFAULT_DIMENSION = 768
    MAX_RETRIES = 3
    RETRY_DELAY = 2.0
    DEFAULT_MAX_CONCURRENT = 4

    CB_FAILURE_THRESHOLD = 5
    CB_RECOVERY_TIMEOUT = 30.0
    CB_SUCCESS_THRESHOLD = 2

    BH_MAX_WAIT_TIME = 60.0

    def __init__(
        self,
        model_name: str = DEFAULT_MODEL,
        dimension: int = DEFAULT_DIMENSION,
        max_retries: int = MAX_RETRIES,
        retry_delay: float = RETRY_DELAY,
        max_concurrent: int = DEFAULT_MAX_CONCURRENT,
        max_wait_time: float = BH_MAX_WAIT_TIME,
        circuit_breaker_config: Optional[CircuitBreakerConfig] = None,
        bulkhead_config: Optional[BulkheadConfig] = None,
    ) -> None:
        self._model_name = model_name
        self._dimension = dimension
        self._max_retries = max_retries
        self._retry_delay = retry_delay
        self._max_concurrent = max_concurrent
        self._ollama = None
        self._initialize_client()

        cb_config = circuit_breaker_config or CircuitBreakerConfig(
            failure_threshold=self.CB_FAILURE_THRESHOLD,
            recovery_timeout=self.CB_RECOVERY_TIMEOUT,
            success_threshold=self.CB_SUCCESS_THRESHOLD,
        )
        self._circuit_breaker = CircuitBreaker(
            name=f"ollama-embedding-{model_name}",
            config=cb_config,
        )

        bh_config = bulkhead_config or BulkheadConfig(
            name=f"ollama-bulkhead-{model_name}",
            max_concurrent=max_concurrent,
            max_wait_time=max_wait_time,
        )
        self._bulkhead = Bulkhead(bh_config)

        logger.debug(
            "OllamaEmbeddingAdapter initialized: model=%s, max_concurrent=%d",
            model_name,
            max_concurrent,
        )

    def _initialize_client(self) -> None:
        try:
            import ollama
            self._ollama = ollama
            logger.debug("Ollama client initialized")
        except ImportError:
            logger.warning("ollama package not installed")
            self._ollama = None

    @property
    def model_name(self) -> str:
        return self._model_name

    @property
    def dimension(self) -> int:
        return self._dimension

    @property
    def circuit_breaker(self) -> CircuitBreaker:
        return self._circuit_breaker

    @property
    def bulkhead(self) -> Bulkhead:
        return self._bulkhead

    def embed(self, text: str) -> Optional[EmbeddingVector]:
        if not text or not text.strip():
            return None

        if self._ollama is None:
            logger.error("Ollama client not available")
            return None

        try:
            return self._bulkhead.call(
                lambda: self._circuit_breaker.call(
                    lambda: self._embed_internal(text)
                )
            )
        except BulkheadFullError as e:
            logger.warning("Embedding skipped - bulkhead full: %s", e)
            return None
        except CircuitBreakerError as e:
            logger.warning("Embedding skipped - circuit breaker open: %s", e)
            return None
        except Exception:
            return None

    def _embed_internal(self, text: str) -> Optional[EmbeddingVector]:
        last_error = None

        for attempt in range(self._max_retries):
            try:
                result = self._ollama.embeddings(
                    model=self._model_name,
                    prompt=text,
                )
                embedding_values = result.get("embedding")

                if embedding_values:
                    return EmbeddingVector(embedding_values)

                logger.warning("Empty embedding returned for text")
                return None

            except Exception as err:
                last_error = err
                logger.warning(
                    "Embedding attempt %d/%d failed: %s",
                    attempt + 1,
                    self._max_retries,
                    err,
                )
                if attempt < self._max_retries - 1:
                    time.sleep(self._retry_delay)

        logger.error("All embedding attempts failed")
        if last_error:
            raise last_error
        return None

    def embed_batch(
        self,
        texts: List[str],
        batch_size: int = 32,
        progress_callback: Optional[Callable[[int, int], None]] = None,
    ) -> List[Optional[EmbeddingVector]]:
        if not texts:
            return []

        if self._ollama is None:
            logger.error("Ollama client not available for batch embedding")
            return [None] * len(texts)

        total = len(texts)
        results: List[Optional[EmbeddingVector]] = [None] * total
        completed = 0

        num_workers = min(batch_size, self._max_concurrent * 2)

        for batch_start in range(0, total, batch_size):
            batch_end = min(batch_start + batch_size, total)
            batch_texts = texts[batch_start:batch_end]
            batch_indices = list(range(batch_start, batch_end))

            with ThreadPoolExecutor(max_workers=num_workers) as executor:
                future_to_index = {
                    executor.submit(self._embed_with_bulkhead, text): idx
                    for idx, text in zip(batch_indices, batch_texts)
                }

                for future in as_completed(future_to_index):
                    idx = future_to_index[future]
                    try:
                        embedding = future.result()
                        results[idx] = embedding
                    except Exception as err:
                        logger.error(
                            "Unexpected error embedding text at index %d: %s",
                            idx,
                            err,
                        )
                        results[idx] = None

                    completed += 1
                    if progress_callback:
                        progress_callback(completed, total)

        success_count = sum(1 for r in results if r is not None)
        logger.info(
            "Batch embedding completed: %d/%d successful (bulkhead stats: %s)",
            success_count,
            total,
            self._bulkhead.stats.to_dict(),
        )

        return results

    def _embed_with_bulkhead(self, text: str) -> Optional[EmbeddingVector]:
        if not text or not text.strip():
            return None

        try:
            return self._bulkhead.call(
                lambda: self._circuit_breaker.call(
                    lambda: self._embed_single_attempt(text)
                )
            )
        except BulkheadFullError:
            return None
        except CircuitBreakerError:
            return None

    def _embed_single_attempt(self, text: str) -> Optional[EmbeddingVector]:
        last_error = None

        for attempt in range(self._max_retries):
            try:
                result = self._ollama.embeddings(
                    model=self._model_name,
                    prompt=text,
                )
                embedding_values = result.get("embedding")

                if embedding_values:
                    return EmbeddingVector(embedding_values)

                logger.warning("Empty embedding returned")
                return None

            except Exception as err:
                last_error = err
                if attempt < self._max_retries - 1:
                    logger.debug(
                        "Embedding attempt %d/%d failed, retrying: %s",
                        attempt + 1,
                        self._max_retries,
                        err,
                    )
                    time.sleep(self._retry_delay)

        if last_error:
            logger.warning(
                "All %d embedding attempts failed: %s",
                self._max_retries,
                last_error,
            )
            raise last_error
        return None

    def is_available(self) -> bool:
        if self._ollama is None:
            return False

        try:
            models = self._ollama.list()
            model_names = [m.get("name", "") for m in models.get("models", [])]

            model_available = any(
                self._model_name in name for name in model_names
            )

            if not model_available:
                logger.warning(
                    "Model %s not found. Available: %s",
                    self._model_name,
                    model_names,
                )

            return model_available

        except Exception as err:
            logger.error("Failed to check Ollama availability: %s", err)
            return False
