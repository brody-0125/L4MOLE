
import pytest
from unittest.mock import MagicMock, patch, PropertyMock

from src.domain.ports.vector_store_port import VectorSearchHit
from src.domain.value_objects.embedding_vector import EmbeddingVector

try:
    import pymilvus
    PYMILVUS_AVAILABLE = True
except ImportError:
    PYMILVUS_AVAILABLE = False

@pytest.fixture
def mock_milvus_client():
    client = MagicMock()
    client.has_collection.return_value = False
    client.create_collection.return_value = None
    client.drop_collection.return_value = None
    client.upsert.return_value = None
    client.delete.return_value = None
    client.get_collection_stats.return_value = {"row_count": 0}
    return client

@pytest.fixture
def milvus_store(mock_milvus_client):
    with patch.dict("sys.modules", {"pymilvus": MagicMock()}):
        with patch(
            "src.infrastructure.persistence.vector.milvus_store.MilvusVectorStore._initialize_client"
        ):
            from src.infrastructure.persistence.vector.milvus_store import (
                MilvusVectorStore,
            )

            store = MilvusVectorStore(use_lite=True, lite_path="./test_milvus.db")
            store._client = mock_milvus_client
            store._milvus_module = {
                "Collection": MagicMock(),
                "CollectionSchema": MagicMock(),
                "DataType": MagicMock(),
                "FieldSchema": MagicMock(),
                "MilvusClient": MagicMock(),
                "connections": MagicMock(),
                "utility": MagicMock(),
            }
            return store

class TestMilvusVectorStoreBasics:

    def test_create_collection(self, milvus_store, mock_milvus_client):
        mock_milvus_client.has_collection.return_value = False

        result = milvus_store.create_collection("test_collection", 768, "cosine")

        assert result is True
        mock_milvus_client.create_collection.assert_called_once()

    def test_create_collection_already_exists(self, milvus_store, mock_milvus_client):
        mock_milvus_client.has_collection.return_value = True

        result = milvus_store.create_collection("test_collection", 768, "cosine")

        assert result is True
        mock_milvus_client.create_collection.assert_not_called()

    def test_collection_exists(self, milvus_store, mock_milvus_client):
        mock_milvus_client.has_collection.return_value = True

        assert milvus_store.collection_exists("test_collection") is True

        mock_milvus_client.has_collection.return_value = False
        assert milvus_store.collection_exists("test_collection") is False

    def test_drop_collection(self, milvus_store, mock_milvus_client):
        result = milvus_store.drop_collection("test_collection")

        assert result is True
        mock_milvus_client.drop_collection.assert_called_once_with("test_collection")

class TestMilvusVectorStoreInsert:

    def test_insert_single_vector(self, milvus_store, mock_milvus_client):
        vector = EmbeddingVector([0.1, 0.2, 0.3])
        metadata = {"file_path": "/test/file.txt"}

        result = milvus_store.insert(
            "test_collection",
            "vec_1",
            vector,
            metadata,
        )

        assert result is True
        mock_milvus_client.upsert.assert_called_once()

    def test_insert_single_vector_no_metadata(self, milvus_store, mock_milvus_client):
        vector = EmbeddingVector([0.1, 0.2, 0.3])

        result = milvus_store.insert("test_collection", "vec_1", vector)

        assert result is True

    def test_insert_batch(self, milvus_store, mock_milvus_client):
        ids = ["vec_1", "vec_2", "vec_3"]
        vectors = [
            EmbeddingVector([0.1, 0.2, 0.3]),
            EmbeddingVector([0.4, 0.5, 0.6]),
            EmbeddingVector([0.7, 0.8, 0.9]),
        ]
        metadatas = [
            {"file_path": "/test/file1.txt"},
            {"file_path": "/test/file2.txt"},
            {"file_path": "/test/file3.txt"},
        ]

        result = milvus_store.insert_batch(
            "test_collection",
            ids,
            vectors,
            metadatas,
        )

        assert result == 3
        mock_milvus_client.upsert.assert_called_once()

    def test_insert_batch_empty(self, milvus_store, mock_milvus_client):
        result = milvus_store.insert_batch("test_collection", [], [])

        assert result == 0
        mock_milvus_client.upsert.assert_not_called()

    def test_insert_auto_creates_collection(self, milvus_store, mock_milvus_client):
        mock_milvus_client.has_collection.return_value = False
        vector = EmbeddingVector([0.1, 0.2, 0.3])

        result = milvus_store.insert("new_collection", "vec_1", vector)

        assert result is True
        mock_milvus_client.has_collection.assert_called()
        mock_milvus_client.create_collection.assert_called()

    def test_insert_batch_auto_creates_collection(self, milvus_store, mock_milvus_client):
        mock_milvus_client.has_collection.return_value = False
        vectors = [EmbeddingVector([0.1, 0.2, 0.3])]

        result = milvus_store.insert_batch("new_collection", ["vec_1"], vectors)

        assert result == 1
        mock_milvus_client.has_collection.assert_called()
        mock_milvus_client.create_collection.assert_called()

class TestMilvusVectorStoreSearch:

    def test_search(self, milvus_store, mock_milvus_client):
        query_vector = EmbeddingVector([0.1, 0.2, 0.3])

        mock_milvus_client.search.return_value = [
            [
                {
                    "id": "vec_1",
                    "distance": 0.9,
                    "entity": {"file_path": "/test/file.txt"},
                },
                {
                    "id": "vec_2",
                    "distance": 0.8,
                    "entity": {"file_path": "/test/file2.txt"},
                },
            ]
        ]

        results = milvus_store.search(
            "test_collection",
            query_vector,
            top_k=10,
        )

        assert len(results) == 2
        assert results[0].id == "vec_1"
        assert results[1].id == "vec_2"

    def test_search_with_filter(self, milvus_store, mock_milvus_client):
        query_vector = EmbeddingVector([0.1, 0.2, 0.3])
        filter_expr = "file_type == 'pdf'"

        mock_milvus_client.search.return_value = [[]]

        results = milvus_store.search(
            "test_collection",
            query_vector,
            top_k=10,
            filter_expr=filter_expr,
        )

        assert isinstance(results, list)

    def test_search_empty_results(self, milvus_store, mock_milvus_client):
        query_vector = EmbeddingVector([0.1, 0.2, 0.3])
        mock_milvus_client.search.return_value = [[]]

        results = milvus_store.search("test_collection", query_vector)

        assert results == []

class TestMilvusVectorStoreDelete:

    def test_delete_vectors(self, milvus_store, mock_milvus_client):
        ids = ["vec_1", "vec_2", "vec_3"]

        result = milvus_store.delete("test_collection", ids)

        assert result == 3
        mock_milvus_client.delete.assert_called_once()

    def test_delete_empty_list(self, milvus_store, mock_milvus_client):
        result = milvus_store.delete("test_collection", [])

        assert result == 0
        mock_milvus_client.delete.assert_not_called()

class TestMilvusVectorStoreGet:

    def test_get_vectors(self, milvus_store, mock_milvus_client):
        mock_milvus_client.get.return_value = [
            {
                "id": "vec_1",
                "vector": [0.1, 0.2, 0.3],
                "file_path": "/test/file.txt",
            },
        ]

        results = milvus_store.get("test_collection", ["vec_1"])

        assert len(results) == 1
        assert results[0]["id"] == "vec_1"

    def test_get_empty_list(self, milvus_store, mock_milvus_client):
        results = milvus_store.get("test_collection", [])

        assert results == []
        mock_milvus_client.get.assert_not_called()

class TestMilvusVectorStoreCount:

    def test_count(self, milvus_store, mock_milvus_client):
        mock_milvus_client.get_collection_stats.return_value = {"row_count": 42}

        count = milvus_store.count("test_collection")

        assert count == 42

class TestMilvusVectorStoreClose:

    def test_close(self, milvus_store, mock_milvus_client):
        milvus_store.close()

        mock_milvus_client.close.assert_called_once()

class TestMilvusMetricConversion:

    def test_get_metric_type_cosine(self, milvus_store):
        assert milvus_store._get_metric_type("cosine") == "COSINE"
        assert milvus_store._get_metric_type("COSINE") == "COSINE"

    def test_get_metric_type_l2(self, milvus_store):
        assert milvus_store._get_metric_type("l2") == "L2"
        assert milvus_store._get_metric_type("euclidean") == "L2"

    def test_get_metric_type_ip(self, milvus_store):
        assert milvus_store._get_metric_type("ip") == "IP"

    def test_get_metric_type_default(self, milvus_store):
        assert milvus_store._get_metric_type("unknown") == "COSINE"

@pytest.mark.skipif(not PYMILVUS_AVAILABLE, reason="pymilvus not installed")
class TestMilvusVectorStoreIntegration:

    def test_import_milvus_store(self):
        from src.infrastructure.persistence.vector.milvus_store import (
            MilvusVectorStore,
        )

        assert MilvusVectorStore is not None

    def test_milvus_lite_initialization(self, tmp_path):
        from src.infrastructure.persistence.vector.milvus_store import (
            MilvusVectorStore,
        )

        lite_path = str(tmp_path / "test_milvus.db")

        try:
            store = MilvusVectorStore(use_lite=True, lite_path=lite_path)
            assert store is not None
            store.close()
        except Exception as e:
            pytest.skip(f"Milvus Lite not available: {e}")
