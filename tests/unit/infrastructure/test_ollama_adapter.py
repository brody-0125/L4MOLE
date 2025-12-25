
import time
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import MagicMock, patch

import pytest

from src.domain.value_objects.embedding_vector import EmbeddingVector
from src.infrastructure.embedding.ollama_adapter import OllamaEmbeddingAdapter

class TestOllamaEmbeddingAdapter:

    @pytest.fixture
    def mock_ollama(self):
        mock = MagicMock()
        mock.embeddings.return_value = {"embedding": [0.1] * 768}
        return mock

    @pytest.fixture
    def adapter(self, mock_ollama):
        with patch.dict("sys.modules", {"ollama": mock_ollama}):
            adapter = OllamaEmbeddingAdapter(
                model_name="test-model",
                dimension=768,
                max_retries=2,
                retry_delay=0.01,
                max_concurrent=4,
            )
            adapter._ollama = mock_ollama
            return adapter

    def test_embed_single_text(self, adapter, mock_ollama):
        result = adapter.embed("test text")

        assert result is not None
        assert isinstance(result, EmbeddingVector)
        assert len(result) == 768
        mock_ollama.embeddings.assert_called_once()

    def test_embed_empty_text_returns_none(self, adapter):
        assert adapter.embed("") is None
        assert adapter.embed("   ") is None
        assert adapter.embed(None) is None

    def test_embed_with_retry_on_failure(self, adapter, mock_ollama):
        mock_ollama.embeddings.side_effect = [
            Exception("Connection error"),
            {"embedding": [0.1] * 768},
        ]

        result = adapter.embed("test text")

        assert result is not None
        assert mock_ollama.embeddings.call_count == 2

    def test_embed_all_retries_exhausted(self, adapter, mock_ollama):
        mock_ollama.embeddings.side_effect = Exception("Persistent error")

        result = adapter.embed("test text")

        assert result is None
        assert mock_ollama.embeddings.call_count == 2

class TestParallelBatchEmbedding:

    @pytest.fixture
    def mock_ollama(self):
        mock = MagicMock()
        mock.embeddings.return_value = {"embedding": [0.1] * 768}
        return mock

    @pytest.fixture
    def adapter(self, mock_ollama):
        with patch.dict("sys.modules", {"ollama": mock_ollama}):
            adapter = OllamaEmbeddingAdapter(
                model_name="test-model",
                dimension=768,
                max_retries=1,
                retry_delay=0.01,
                max_concurrent=4,
            )
            adapter._ollama = mock_ollama
            return adapter

    def test_embed_batch_returns_correct_count(self, adapter):
        texts = ["text1", "text2", "text3", "text4", "text5"]

        results = adapter.embed_batch(texts)

        assert len(results) == 5
        assert all(r is not None for r in results)

    def test_embed_batch_preserves_order(self, adapter, mock_ollama):
        def unique_embedding(model, prompt):
            hash_val = hash(prompt) % 1000
            return {"embedding": [hash_val / 1000] * 768}

        mock_ollama.embeddings.side_effect = unique_embedding

        texts = ["first", "second", "third", "fourth"]
        results = adapter.embed_batch(texts)

        result_values = [r.to_list()[0] for r in results]
        assert len(set(result_values)) == 4

    def test_embed_batch_empty_list(self, adapter):
        results = adapter.embed_batch([])
        assert results == []

    def test_embed_batch_with_some_failures(self, adapter, mock_ollama):
        call_count = [0]

        def sometimes_fail(model, prompt):
            call_count[0] += 1
            if "fail" in prompt:
                raise Exception("Simulated failure")
            return {"embedding": [0.1] * 768}

        mock_ollama.embeddings.side_effect = sometimes_fail

        texts = ["good1", "fail_this", "good2", "fail_that", "good3"]
        results = adapter.embed_batch(texts)

        assert len(results) == 5
        assert results[0] is not None
        assert results[1] is None
        assert results[2] is not None
        assert results[3] is None
        assert results[4] is not None

    def test_embed_batch_progress_callback(self, adapter):
        texts = ["text1", "text2", "text3"]
        progress_calls = []

        def progress_callback(completed, total):
            progress_calls.append((completed, total))

        adapter.embed_batch(texts, progress_callback=progress_callback)

        assert len(progress_calls) == 3
        totals = [call[1] for call in progress_calls]
        assert all(t == 3 for t in totals)
        completeds = sorted([call[0] for call in progress_calls])
        assert completeds == [1, 2, 3]

    def test_embed_batch_respects_batch_size(self, adapter, mock_ollama):
        texts = ["text" + str(i) for i in range(10)]

        results = adapter.embed_batch(texts, batch_size=5)

        assert len(results) == 10
        assert all(r is not None for r in results)

    def test_embed_batch_with_empty_strings(self, adapter):
        texts = ["valid", "", "also_valid", "   ", "last"]
        results = adapter.embed_batch(texts)

        assert len(results) == 5
        assert results[0] is not None
        assert results[1] is None
        assert results[2] is not None
        assert results[3] is None
        assert results[4] is not None

    def test_embed_batch_parallelism_performance(self, adapter, mock_ollama):
        def slow_embedding(model, prompt):
            time.sleep(0.01)
            return {"embedding": [0.1] * 768}

        mock_ollama.embeddings.side_effect = slow_embedding

        texts = ["text" + str(i) for i in range(8)]

        start = time.time()
        results = adapter.embed_batch(texts, batch_size=8)
        elapsed = time.time() - start

        assert len(results) == 8
        assert elapsed < 0.08

class TestOllamaAvailability:

    @pytest.fixture
    def mock_ollama(self):
        mock = MagicMock()
        return mock

    @pytest.fixture
    def adapter(self, mock_ollama):
        with patch.dict("sys.modules", {"ollama": mock_ollama}):
            adapter = OllamaEmbeddingAdapter()
            adapter._ollama = mock_ollama
            return adapter

    def test_is_available_when_model_exists(self, adapter, mock_ollama):
        mock_ollama.list.return_value = {
            "models": [{"name": "nomic-embed-text:latest"}]
        }

        assert adapter.is_available() is True

    def test_is_available_when_model_not_found(self, adapter, mock_ollama):
        mock_ollama.list.return_value = {
            "models": [{"name": "other-model:latest"}]
        }

        assert adapter.is_available() is False

    def test_is_available_when_connection_fails(self, adapter, mock_ollama):
        mock_ollama.list.side_effect = Exception("Connection refused")

        assert adapter.is_available() is False

    def test_is_available_no_ollama_client(self, adapter):
        adapter._ollama = None

        assert adapter.is_available() is False
